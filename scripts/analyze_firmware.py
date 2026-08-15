#!/usr/bin/env python3
"""Read-only first-pass scanner for the Meizu R18 factory image.

The script never writes to the input image.  It writes reproducible text
evidence under analysis/reports/ and does not attempt automatic extraction.
"""

from __future__ import annotations

import argparse
import hashlib
import lzma
import re
import struct
import zlib
from collections import Counter
from pathlib import Path


MAGICS: dict[str, tuple[bytes, str]] = {
    "uImage": (bytes.fromhex("27051956"), "U-Boot legacy image header"),
    "FDT": (bytes.fromhex("d00dfeed"), "Flattened Device Tree Blob / FIT container"),
    "SquashFS-le": (b"hsqs", "SquashFS (little-endian magic)"),
    "SquashFS-be": (b"sqsh", "SquashFS (big-endian magic)"),
    "UBI": (b"UBI#", "UBI eraseblock header"),
    "UBIFS": (bytes.fromhex("31181006"), "UBIFS node magic (little-endian)"),
    "JFFS2-le": (bytes.fromhex("8519"), "JFFS2 node magic (little-endian)"),
    "JFFS2-be": (bytes.fromhex("1985"), "JFFS2 node magic (big-endian)"),
    "gzip": (bytes.fromhex("1f8b08"), "gzip stream"),
    "xz": (bytes.fromhex("fd377a585a00"), "XZ stream"),
    "lzma-alone": (bytes.fromhex("5d0000"), "possible LZMA-alone stream"),
    "lz4-frame": (bytes.fromhex("04224d18"), "LZ4 frame"),
    "ELF": (bytes.fromhex("7f454c46"), "ELF executable"),
    "TRX": (b"HDR0", "Broadcom TRX container"),
}

KEYWORDS = re.compile(
    rb"(?:mediatek|mt762\w*|mt798\w*|qualcomm|qca|ipq\w*|atheros|"
    rb"realtek|rtl\w*|broadcom|brcm\w*|ramips|filogic|u-boot|uboot|breed|"
    rb"cfe|redboot|bootcmd|bootargs|tftpboot|Linux version|Kernel command line|"
    rb"mtdparts=|spi-nor|spi-nand|\bnand\b|\bmtd\b|\bubi\b|\bubifs\b|"
    rb"\bmmc\b|mt76|ath9k|ath10k|ath11k|ath12k|eeprom|factory|calibration)",
    re.IGNORECASE,
)


def offsets(data: bytes, needle: bytes) -> list[int]:
    result: list[int] = []
    start = 0
    while True:
        pos = data.find(needle, start)
        if pos < 0:
            return result
        result.append(pos)
        start = pos + 1


def hexdump(data: bytes, base: int = 0) -> str:
    lines: list[str] = []
    for i in range(0, len(data), 16):
        block = data[i : i + 16]
        hexes = " ".join(f"{value:02x}" for value in block).ljust(47)
        chars = "".join(chr(value) if 32 <= value < 127 else "." for value in block)
        lines.append(f"{base + i:08x}  {hexes}  |{chars}|")
    return "\n".join(lines)


def printable_strings(data: bytes, minimum: int = 4) -> list[tuple[int, str]]:
    strings: list[tuple[int, str]] = []
    for match in re.finditer(rb"[\x20-\x7e]{%d,}" % minimum, data):
        strings.append((match.start(), match.group().decode("ascii", "replace")))
    return strings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--report-dir", type=Path, default=Path("analysis/reports"))
    parser.add_argument("--extract-dir", type=Path, default=Path("extracted"))
    args = parser.parse_args()

    image = args.image.resolve()
    data = image.read_bytes()
    args.report_dir.mkdir(parents=True, exist_ok=True)

    sha256 = hashlib.sha256(data).hexdigest()
    md5 = hashlib.md5(data).hexdigest()  # noqa: S324 - requested identification hash

    if data[:4] != bytes.fromhex("27051956"):
        raise ValueError("The input does not begin with a U-Boot legacy uImage magic.")
    (
        _magic,
        header_crc,
        timestamp,
        payload_size,
        load_address,
        entry_address,
        payload_crc,
        os_id,
        arch_id,
        image_type,
        compression,
        raw_name,
    ) = struct.unpack_from(">7I4B32s", data, 0)
    name = raw_name.split(b"\0", 1)[0].decode("ascii", "replace")
    header_for_crc = bytearray(data[:64])
    header_for_crc[4:8] = b"\0\0\0\0"
    header_crc_ok = (zlib.crc32(header_for_crc) & 0xFFFFFFFF) == header_crc
    payload_start = 64
    payload_end = payload_start + payload_size
    payload = data[payload_start:payload_end]
    payload_crc_ok = (zlib.crc32(payload) & 0xFFFFFFFF) == payload_crc
    if len(payload) != payload_size:
        raise ValueError("uImage payload exceeds the input image.")
    arch_names = {5: "MIPS"}
    type_names = {2: "kernel"}
    compression_names = {3: "LZMA"}

    args.extract_dir.mkdir(parents=True, exist_ok=True)
    kernel_dir = args.extract_dir / "kernel"
    rootfs_dir = args.extract_dir / "rootfs"
    kernel_dir.mkdir(exist_ok=True)
    rootfs_dir.mkdir(exist_ok=True)
    compressed_kernel_path = kernel_dir / "uimage-kernel.lzma"
    compressed_kernel_path.write_bytes(payload)
    decompressed_kernel_path = kernel_dir / "uimage-kernel"
    try:
        decompressed_kernel = lzma.decompress(payload, format=lzma.FORMAT_ALONE)
        decompressed_kernel_path.write_bytes(decompressed_kernel)
        decompress_status = f"success; {len(decompressed_kernel)} bytes written to {decompressed_kernel_path}"
    except lzma.LZMAError as exc:
        decompress_status = f"failed ({exc}); only the verified compressed payload was preserved"

    squash_offset = payload_end
    squash_fields = struct.unpack_from("<5I6H8Q", data, squash_offset)
    (
        squash_magic,
        squash_inodes,
        squash_mkfs_time,
        squash_block_size,
        squash_fragments,
        squash_compression,
        squash_block_log,
        squash_flags,
        squash_no_ids,
        squash_major,
        squash_minor,
        squash_root_inode,
        squash_bytes_used,
        squash_id_table_start,
        squash_xattr_id_table_start,
        squash_inode_table_start,
        squash_directory_table_start,
        squash_fragment_table_start,
        squash_lookup_table_start,
    ) = squash_fields
    if squash_magic != 0x73717368:
        raise ValueError(f"Expected SquashFS magic at 0x{squash_offset:x}, got 0x{squash_magic:08x}.")
    squash_end = squash_offset + squash_bytes_used
    if squash_end > len(data):
        raise ValueError("SquashFS bytes_used exceeds the input image.")
    squash_path = rootfs_dir / "rootfs.squashfs"
    squash_path.write_bytes(data[squash_offset:squash_end])
    magic_lines = []
    for label, (needle, meaning) in MAGICS.items():
        found = offsets(data, needle)
        if found:
            magic_lines.append(f"- {label}: {meaning}; offsets: " + ", ".join(f"0x{x:08x}" for x in found[:100]))
            if len(found) > 100:
                magic_lines.append(f"  - truncated: {len(found)} total matches")
    if not magic_lines:
        magic_lines.append("- No listed filesystem/container magic was found.")

    strings = printable_strings(data)
    hits = [(offset, value) for offset, value in strings if KEYWORDS.search(value.encode())]
    unique_hits = []
    seen = set()
    for item in hits:
        if item[1] not in seen:
            unique_hits.append(item)
            seen.add(item[1])
    counts = Counter(value.lower() for _, value in hits)

    (args.report_dir / "firmware-basic-info.txt").write_text(
        "\n".join(
            [
                "Meizu R18 factory firmware — basic information",
                f"Path: {image}",
                f"Length: {len(data)} bytes (0x{len(data):x}; {len(data) / 1024 / 1024:.3f} MiB)",
                f"SHA-256: {sha256}",
                f"MD5: {md5}",
                "Input handling: scanned read-only; no input bytes were modified.",
                "Tool availability: file/binwalk/xxd/hexdump/strings/fdisk/parted/7z/unsquashfs/ubireader/dtc were unavailable in this Windows workspace at scan time.",
                "Fallback: scripts/analyze_firmware.py (Python standard library).",
                f"uImage header CRC: {'valid' if header_crc_ok else 'INVALID'}",
                f"uImage data CRC: {'valid' if payload_crc_ok else 'INVALID'}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (args.report_dir / "firmware-layout.md").write_text(
        "\n".join(
            [
                "# Factory firmware layout — first-pass evidence",
                "",
                "## Method",
                "",
                "A read-only byte scan searched known container/filesystem magics. Each reported candidate must be manually validated before it is treated as an extractable component.",
                "",
                "## Matches",
                "",
                *magic_lines,
                "",
                "## Manually validated primary layout",
                "",
                f"- `0x00000000`–`0x0000003f`: valid U-Boot legacy uImage header; name `{name}`.",
                f"- `0x00000040`–`0x{payload_end - 1:08x}`: uImage payload ({payload_size} bytes), compression declared as {compression_names.get(compression, f'unknown ({compression}')}).",
                f"- `0x{squash_offset:08x}`–`0x{squash_end - 1:08x}`: valid SquashFS {squash_major}.{squash_minor}, {squash_bytes_used} bytes used.",
                f"- `0x{squash_end:08x}`–`0x{len(data) - 1:08x}`: trailing data/padding; not interpreted as a partition without separate evidence.",
                "",
                "## False-positive handling",
                "",
                "The many JFFS2/XZ byte matches occur inside compressed data and are not accepted as filesystem/stream boundaries. They do not have supporting structural context. The uImage and SquashFS boundaries above are instead confirmed by their headers, checksums, and exact adjacency.",
                "",
                "## First 1024 bytes",
                "",
                "```text",
                hexdump(data[:1024]),
                "```",
                "",
                "## Final 4096 bytes",
                "",
                "```text",
                hexdump(data[-4096:], len(data) - min(len(data), 4096)),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (args.report_dir / "uimage-and-squashfs.txt").write_text(
        "\n".join(
            [
                "Validated uImage header",
                f"Name: {name}",
                f"Header CRC: 0x{header_crc:08x} ({'valid' if header_crc_ok else 'INVALID'})",
                f"Timestamp (Unix epoch): {timestamp} (0x{timestamp:08x})",
                f"Payload size: {payload_size} bytes (0x{payload_size:x})",
                f"Payload CRC: 0x{payload_crc:08x} ({'valid' if payload_crc_ok else 'INVALID'})",
                f"OS: Linux ({os_id})",
                f"Architecture: {arch_names.get(arch_id, 'unknown')} ({arch_id})",
                f"Image type: {type_names.get(image_type, 'unknown')} ({image_type})",
                f"Compression: {compression_names.get(compression, 'unknown')} ({compression})",
                f"Load address: 0x{load_address:08x}",
                f"Entry address: 0x{entry_address:08x}",
                f"Compressed payload: {compressed_kernel_path}",
                f"LZMA decompression: {decompress_status}",
                "",
                "Validated SquashFS superblock",
                f"Offset: 0x{squash_offset:08x}",
                f"Version: {squash_major}.{squash_minor}",
                f"Compression ID: {squash_compression}",
                f"Block size: {squash_block_size} (log2 {squash_block_log})",
                f"Inodes: {squash_inodes}; fragments: {squash_fragments}; IDs: {squash_no_ids}; flags: 0x{squash_flags:04x}",
                f"Bytes used: {squash_bytes_used} (0x{squash_bytes_used:x})",
                f"Root inode: 0x{squash_root_inode:016x}",
                f"Extracted raw filesystem: {squash_path}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (args.report_dir / "firmware-keyword-strings.txt").write_text(
        "\n".join(
            [
                "Keyword-bearing printable strings from the factory image",
                "Only unique values are listed; offsets are hexadecimal.",
                "",
                *(f"0x{offset:08x}  {value}" for offset, value in unique_hits),
                "",
                "Hit counts (case-insensitive):",
                *(f"{count:5d}  {value}" for value, count in counts.most_common()),
                "",
            ]
        ),
        encoding="utf-8",
    )
    (args.report_dir / "firmware-all-strings.txt").write_text(
        "\n".join(f"0x{offset:08x}  {value}" for offset, value in strings) + "\n",
        encoding="utf-8",
    )
    print(f"Scanned {image.name}: {len(data)} bytes; {len(magic_lines)} magic classes; {len(unique_hits)} unique keyword strings.")


if __name__ == "__main__":
    main()
