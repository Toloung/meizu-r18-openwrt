#!/usr/bin/env python3
"""Evidence-oriented inspection of extracted read-only firmware artifacts."""

from __future__ import annotations

import hashlib
import re
import struct
from pathlib import Path


TERMS = re.compile(
    rb"(?:Linux version|Kernel command line|mtdparts=|MT[0-9A-Z_-]+|"
    rb"RT[0-9A-Z_-]+|QCA[0-9A-Z_-]*|IPQ[0-9A-Z_-]*|Atheros|MediaTek|"
    rb"Ralink|Qualcomm|OpenWrt|Meizu|M18|R18|bootargs|bootcmd|"
    rb"spi[-_ ](?:nor|nand)|nand|mtd|ubi|ubifs|squashfs|factory|"
    rb"eeprom|calibration|art|ath[0-9a-z_-]*|mt76|gpio|led|reset|"
    rb"ethernet|gmac|mdio|phy|switch)",
    re.IGNORECASE,
)


def strings(data: bytes) -> list[tuple[int, str]]:
    return [
        (m.start(), m.group().decode("ascii", "replace"))
        for m in re.finditer(rb"[\x20-\x7e]{4,}", data)
    ]


def context(data: bytes, offset: int, span: int = 128) -> str:
    start = max(0, offset - span)
    end = min(len(data), offset + span)
    fragment = data[start:end]
    printable = "".join(chr(x) if 32 <= x < 127 else "." for x in fragment)
    return f"0x{start:08x}..0x{end - 1:08x}  {printable}"


def main() -> None:
    artifact = Path("extracted/kernel/uimage-kernel")
    report = Path("analysis/reports/kernel-strings.txt")
    data = artifact.read_bytes()
    all_strings = strings(data)
    hits = [(off, value) for off, value in all_strings if TERMS.search(value.encode())]
    is_elf = data.startswith(bytes.fromhex("7f454c46"))
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "\n".join(
            [
                "Extracted kernel inspection",
                f"Artifact: {artifact}",
                f"Length: {len(data)} bytes (0x{len(data):x})",
                f"SHA-256: {hashlib.sha256(data).hexdigest()}",
                f"ELF at offset 0: {'yes' if is_elf else 'no'}",
                "",
                "Keyword-bearing strings:",
                *(f"0x{off:08x}  {value}" for off, value in hits),
                "",
                "Context around each keyword-bearing string:",
                *(context(data, off) for off, _ in hits),
                "",
            ]
        ),
        encoding="utf-8",
    )
    Path("analysis/kernel/kernel-all-strings.txt").write_text(
        "\n".join(f"0x{off:08x}  {value}" for off, value in all_strings) + "\n",
        encoding="utf-8",
    )
    dtb_dir = Path("analysis/dtb")
    dtb_dir.mkdir(parents=True, exist_ok=True)
    dtb_matches: list[str] = []
    start = 0
    index = 0
    while True:
        offset = data.find(bytes.fromhex("d00dfeed"), start)
        if offset < 0:
            break
        start = offset + 1
        if offset + 40 > len(data):
            continue
        header = struct.unpack_from(">10I", data, offset)
        magic, total_size, off_struct, off_strings, off_mem, version, last_comp, boot_cpuid, size_strings, size_struct = header
        valid = (
            magic == 0xD00DFEED
            and 40 <= total_size <= len(data) - offset
            and 40 <= off_struct < total_size
            and 40 <= off_strings < total_size
            and off_struct + size_struct <= total_size
            and off_strings + size_strings <= total_size
            and version >= 1
        )
        if not valid:
            continue
        index += 1
        dtb_path = dtb_dir / ("original.dtb" if index == 1 else f"original-{index}.dtb")
        dtb_path.write_bytes(data[offset : offset + total_size])
        dtb_matches.append(
            f"- DTB {index}: kernel offset 0x{offset:08x}, total size {total_size} (0x{total_size:x}), "
            f"version {version}, saved as `{dtb_path}`"
        )
    (dtb_dir / "dtb-scan.txt").write_text(
        "\n".join(
            [
                "DTB scan of extracted, decompressed kernel",
                *(dtb_matches or ["- No structurally valid Flattened Device Tree Blob was found."]),
                "",
                "No DTS was generated because dtc is unavailable. A byte sequence alone is not accepted as a DTB.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"Inspected {artifact}: {len(hits)} relevant strings; {len(dtb_matches)} valid DTB(s).")


if __name__ == "__main__":
    main()
