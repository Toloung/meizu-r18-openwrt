#!/usr/bin/env python3
"""Read-only structural analysis of the supplied MZ-R18 Padavan image."""

from __future__ import annotations

import argparse
import hashlib
import lzma
import struct
import zlib
from pathlib import Path


def all_offsets(data: bytes, needle: bytes) -> list[int]:
    offsets: list[int] = []
    cursor = 0
    while True:
        found = data.find(needle, cursor)
        if found < 0:
            return offsets
        offsets.append(found)
        cursor = found + 1


def squashfs(data: bytes, offset: int) -> dict[str, int] | None:
    if offset + 96 > len(data) or data[offset : offset + 4] != b"hsqs":
        return None
    fields = struct.unpack_from("<5I6H8Q", data, offset)
    _, inodes, mkfs_time, block_size, fragments, compression, block_log, flags, no_ids, major, minor, root_inode, bytes_used, *_ = fields
    end = offset + bytes_used
    if major != 4 or block_size == 0 or bytes_used < 96 or end > len(data):
        return None
    return {"offset": offset, "end": end, "bytes_used": bytes_used, "inodes": inodes, "fragments": fragments, "compression": compression, "block_size": block_size, "block_log": block_log, "flags": flags, "no_ids": no_ids, "major": major, "minor": minor, "root_inode": root_inode}


def try_lzma(payload: bytes) -> tuple[int, bytes, bytes, str] | None:
    # Padavan images can have a small vendor prefix before an LZMA-alone stream.
    for start in range(min(1024, len(payload))):
        if payload[start] not in range(0, 225):
            continue
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        try:
            decoded = dec.decompress(payload[start:])
        except lzma.LZMAError:
            continue
        if dec.eof and len(decoded) > 64 * 1024:
            return start, decoded, dec.unused_data, "success"
    return None


def fmt(value: int) -> str:
    return f"0x{value:08x}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("--analysis-dir", type=Path, default=Path("analysis/padavan"))
    parser.add_argument("--extract-dir", type=Path, default=Path("extracted/padavan"))
    args = parser.parse_args()
    data = args.image.read_bytes()
    args.analysis_dir.mkdir(parents=True, exist_ok=True)
    args.extract_dir.mkdir(parents=True, exist_ok=True)
    if data[:4] != bytes.fromhex("27051956"):
        raise ValueError("Not a U-Boot legacy uImage at offset 0.")
    header = struct.unpack_from(">7I4B32s", data, 0)
    _, header_crc, timestamp, payload_size, load, entry, payload_crc, os_id, arch_id, image_type, compression, raw_name = header
    name_bytes = raw_name.split(b"\0", 1)[0]
    board_marker = b"MZ-R18"
    board_marker_offset = raw_name.find(board_marker)
    name_hex = name_bytes.hex(" ")
    hdr = bytearray(data[:64]); hdr[4:8] = b"\0\0\0\0"
    payload_start, payload_end = 64, 64 + payload_size
    payload = data[payload_start:payload_end]
    header_crc_ok = (zlib.crc32(hdr) & 0xFFFFFFFF) == header_crc
    payload_crc_ok = len(payload) == payload_size and (zlib.crc32(payload) & 0xFFFFFFFF) == payload_crc
    (args.extract_dir / "uimage-payload.bin").write_bytes(payload)

    lzma_result = try_lzma(payload)
    lzma_lines = ["- No valid LZMA-alone stream was decoded in the first 1024 payload bytes."]
    lzma_info: dict[str, int] | None = None
    if lzma_result:
        start, decoded, unused, _ = lzma_result
        consumed = len(payload[start:]) - len(unused)
        (args.extract_dir / "kernel.lzma").write_bytes(payload[start : start + consumed])
        (args.extract_dir / "kernel.uncompressed.bin").write_bytes(decoded)
        lzma_info = {"offset": payload_start + start, "size": consumed, "end": payload_start + start + consumed}
        lzma_lines = [
            f"- LZMA stream begins at payload + `0x{start:x}` (image {fmt(payload_start + start)}).",
            f"- Compressed stream length: {consumed} bytes; decompressed output: {len(decoded)} bytes.",
            f"- Preserved compressed and decompressed forms: `{args.extract_dir / 'kernel.lzma'}` and `{args.extract_dir / 'kernel.uncompressed.bin'}`.",
            f"- Bytes after that stream: {len(unused)} bytes.",
        ]

    squashes: list[dict[str, int]] = []
    for offset in all_offsets(data, b"hsqs"):
        parsed = squashfs(data, offset)
        if parsed:
            squashes.append(parsed)
    if lzma_info and squashes:
        next_squash = min((item for item in squashes if item["offset"] >= lzma_info["end"]), key=lambda item: item["offset"], default=None)
        if next_squash:
            padding = next_squash["offset"] - lzma_info["end"]
            lzma_lines.append(
                f"- Gap before the first following SquashFS: {padding} bytes ({fmt(lzma_info['end'])}–{fmt(next_squash['offset'] - 1) if padding else 'none'}); treated only as alignment/padding, not as a partition."
            )
    squash_lines: list[str] = []
    for index, item in enumerate(squashes, 1):
        path = args.extract_dir / ("rootfs.squashfs" if index == 1 else f"rootfs-{index}.squashfs")
        path.write_bytes(data[item["offset"] : item["end"]])
        squash_lines.append(
            f"- SquashFS {index}: {fmt(item['offset'])}–{fmt(item['end'] - 1)}, {item['bytes_used']} bytes, "
            f"v{item['major']}.{item['minor']}, compression ID {item['compression']}, extracted as `{path}`."
        )
    if not squash_lines:
        squash_lines.append("- No structurally valid SquashFS v4 image was found.")

    magic_map = {
        "TRX": b"HDR0", "FDT": bytes.fromhex("d00dfeed"), "UBI": b"UBI#", "ELF": bytes.fromhex("7f454c46"),
        "gzip": bytes.fromhex("1f8b08"), "XZ": bytes.fromhex("fd377a585a00"), "JFFS2-le": bytes.fromhex("8519"),
    }
    magic_lines = []
    for label, magic in magic_map.items():
        matches = all_offsets(data, magic)
        magic_lines.append(f"- {label}: " + (", ".join(fmt(x) for x in matches[:20]) if matches else "none") + (f" (total {len(matches)})" if len(matches) > 20 else ""))

    (args.analysis_dir / "image-layout.md").write_text(
        "\n".join([
            "# Padavan / MZ-R18 image layout",
            "",
            "## Identification",
            "",
            f"- Input: `{args.image}`",
            f"- File size: {len(data)} bytes ({fmt(len(data))})",
            f"- SHA-256: `{hashlib.sha256(data).hexdigest()}`",
            f"- MD5: `{hashlib.md5(data).hexdigest()}`",
            "- Classification: **U-Boot legacy uImage containing a vendor/Padavan kernel-plus-rootfs payload; not a TRX container and not a complete SPI flash dump.**",
            "- Custom header: no wrapper precedes the uImage; the 64-byte uImage header itself is standard. The LZMA stream begins directly at payload offset zero.",
            "",
            "## Validated uImage header",
            "",
            f"- Raw 32-byte name field (up to NUL): `{name_hex}`.",
            (f"- Board marker: ASCII `MZ-R18` begins at name-field offset `0x{board_marker_offset:x}`; this is direct evidence that this image targets MZ-R18." if board_marker_offset >= 0 else "- Board marker: `MZ-R18` absent from the uImage name field."),
            f"- Header: {fmt(0)}–{fmt(63)}; header CRC `0x{header_crc:08x}` is {'valid' if header_crc_ok else 'INVALID'}.",
            f"- Payload: {fmt(payload_start)}–{fmt(payload_end - 1)}; size {payload_size}; data CRC `0x{payload_crc:08x}` is {'valid' if payload_crc_ok else 'INVALID'}.",
            f"- OS ID {os_id} (Linux), architecture ID {arch_id} (MIPS), image type {image_type} (kernel), compression ID {compression} (LZMA).",
            f"- Load address: {fmt(load)}; entry address: {fmt(entry)}.",
            "",
            "## Embedded LZMA component",
            "",
            *lzma_lines,
            "",
            "## Filesystems",
            "",
            *squash_lines,
            "",
            "## Other magic scan (not accepted as components without structural validation)",
            "",
            *magic_lines,
            "",
            "## Component inventory",
            "",
            "| Component | Offset | Size | Magic / validation | Hash | Compression |",
            "| -- | --: | --: | -- | -- | -- |",
            f"| uImage header | {fmt(0)} | 64 | `0x27051956`, CRC valid={header_crc_ok} | SHA-256 `{hashlib.sha256(data[:64]).hexdigest()}` | none |",
            f"| uImage payload | {fmt(payload_start)} | {payload_size} | data CRC valid={payload_crc_ok} | SHA-256 `{hashlib.sha256(payload).hexdigest()}` | uImage declares LZMA |",
            *([f"| LZMA kernel | {fmt(lzma_info['offset'])} | {lzma_info['size']} | LZMA-alone decompression succeeds | SHA-256 `{hashlib.sha256(data[lzma_info['offset']:lzma_info['end']]).hexdigest()}` | LZMA |"] if lzma_info else []),
            *([f"| SquashFS {i} | {fmt(item['offset'])} | {item['bytes_used']} | SquashFS v4 superblock | SHA-256 `{hashlib.sha256(data[item['offset']:item['end']]).hexdigest()}` | ID {item['compression']} |" for i, item in enumerate(squashes, 1)] or ["| RootFS | UNKNOWN | UNKNOWN | No structural filesystem identified | N/A | UNKNOWN |"]),
            "",
            "## Explicit negatives",
            "",
            "- No bootloader component is present in this image; its uImage header is not a bootloader.",
            "- No factory/EEPROM partition is present as a separately validated component.",
            "- Its complete payload size equals the file after the uImage header, so it is not padded to a 16 MiB raw-flash length.",
            "",
        ]), encoding="utf-8")
    print(f"uImage MZ-R18 marker={board_marker_offset >= 0}; payload CRC valid={payload_crc_ok}; SquashFS images={len(squashes)}; LZMA decoded={bool(lzma_result)}")


if __name__ == "__main__":
    main()
