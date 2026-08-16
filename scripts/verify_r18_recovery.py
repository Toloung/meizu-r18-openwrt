#!/usr/bin/env python3
"""Verify the exact, storage-safe layout of a Meizu R18 TFTP recovery image."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path


FIRMWARE_FLASH_START = 0x00050000
FIRMWARE_SIZE = 0x00F00000
STORAGE_FLASH_START = 0x00F50000
SPI_ERASE_SIZE = 0x00010000
UIMAGE_HEADER_SIZE = 64
UIMAGE_MAGIC = 0x27051956
SQUASHFS_MAGIC = b"hsqs"
JFFS2_EOF_MARKER = b"\xde\xad\xc0\xde"
SCAN_CHUNK_SIZE = 1024 * 1024


class ValidationError(Exception):
    """An image does not meet the R18 clean-recovery format."""


def align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def format_hex(value: int) -> str:
    return f"0x{value:08x}"


def require_ff_padding(image: Path, start: int) -> int:
    """Scan every byte after the JFFS2 marker; sampling is not sufficient."""
    remaining = FIRMWARE_SIZE - start
    checked = 0
    with image.open("rb") as handle:
        handle.seek(start)
        while remaining:
            chunk = handle.read(min(SCAN_CHUNK_SIZE, remaining))
            if not chunk:
                raise ValidationError("unexpected EOF while scanning FF padding")
            first_non_ff = next((index for index, byte in enumerate(chunk) if byte != 0xFF), None)
            if first_non_ff is not None:
                offset = start + checked + first_non_ff
                raise ValidationError(
                    f"non-FF byte 0x{chunk[first_non_ff]:02x} in recovery tail at {format_hex(offset)}"
                )
            checked += len(chunk)
            remaining -= len(chunk)
    return checked


def verify(image: Path) -> dict[str, int]:
    if not image.is_file():
        raise ValidationError(f"image not found: {image}")
    if image.stat().st_size != FIRMWARE_SIZE:
        raise ValidationError(
            f"recovery size is {image.stat().st_size} bytes, expected exactly {FIRMWARE_SIZE} bytes"
        )

    with image.open("rb") as handle:
        header = handle.read(UIMAGE_HEADER_SIZE)
        if len(header) != UIMAGE_HEADER_SIZE:
            raise ValidationError("image is shorter than the legacy uImage header")
        if struct.unpack_from(">I", header, 0)[0] != UIMAGE_MAGIC:
            raise ValidationError("offset 0 is not a legacy uImage (magic 0x27051956)")

        kernel_data_size = struct.unpack_from(">I", header, 12)[0]
        kernel_total = UIMAGE_HEADER_SIZE + kernel_data_size
        if kernel_total + 48 > FIRMWARE_SIZE:
            raise ValidationError("legacy uImage data size extends beyond the recovery image")

        handle.seek(kernel_total)
        superblock = handle.read(48)
        if len(superblock) != 48 or superblock[:4] != SQUASHFS_MAGIC:
            raise ValidationError(f"SquashFS magic 'hsqs' is absent at {format_hex(kernel_total)}")
        bytes_used = struct.unpack_from("<Q", superblock, 40)[0]

        squashfs_end = kernel_total + bytes_used
        rootfs_data_start = align_up(squashfs_end, SPI_ERASE_SIZE)
        if bytes_used == 0 or squashfs_end > FIRMWARE_SIZE:
            raise ValidationError("SquashFS bytes_used is outside the recovery image")
        if rootfs_data_start + len(JFFS2_EOF_MARKER) > FIRMWARE_SIZE:
            raise ValidationError("aligned rootfs_data start leaves no room for its JFFS2 marker")

        handle.seek(rootfs_data_start)
        marker = handle.read(len(JFFS2_EOF_MARKER))
        if marker != JFFS2_EOF_MARKER:
            raise ValidationError(
                f"JFFS2 EOF marker at {format_hex(rootfs_data_start)} is {marker.hex()}, expected deadc0de"
            )

    padding_bytes = require_ff_padding(image, rootfs_data_start + len(JFFS2_EOF_MARKER))
    firmware_end = FIRMWARE_FLASH_START + FIRMWARE_SIZE
    if firmware_end != STORAGE_FLASH_START:
        raise ValidationError("firmware end does not coincide with the R18 storage start")

    return {
        "firmware_end": firmware_end,
        "kernel_total": kernel_total,
        "rootfs_data_start": rootfs_data_start,
        "padding_bytes": padding_bytes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("recovery", type=Path, help="squashfs-recovery.bin to validate")
    args = parser.parse_args()

    try:
        result = verify(args.recovery)
    except ValidationError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Firmware physical start: {format_hex(FIRMWARE_FLASH_START)}")
    print(f"Firmware physical end:   {format_hex(result['firmware_end'])} (exclusive)")
    print(f"Storage physical start:  {format_hex(STORAGE_FLASH_START)}")
    print(f"uImage kernel total:     {format_hex(result['kernel_total'])}")
    print(f"rootfs_data offset:      {format_hex(result['rootfs_data_start'])}")
    print(f"JFFS2 marker offset:     {format_hex(result['rootfs_data_start'])}")
    print(f"FF padding bytes:        {result['padding_bytes']} ({format_hex(result['padding_bytes'])})")
    print(f"Recovery total size:     {FIRMWARE_SIZE} ({format_hex(FIRMWARE_SIZE)})")
    print("R18 recovery verification: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
