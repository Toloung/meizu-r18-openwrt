#!/usr/bin/env python3
"""Minimal read-only SquashFS v4/XZ extractor for this investigation.

Supports the ordinary directory and regular-file inode types used by the
Padavan image. It writes only copies below the output directory and emits a
manifest; it never writes to the input filesystem image.
"""

from __future__ import annotations

import argparse
import lzma
import struct
from dataclasses import dataclass
from pathlib import Path

SQUASHFS_INVALID_FRAG = 0xFFFFFFFF
SQUASHFS_COMPRESSED_BIT = 1 << 24
SQUASHFS_METADATA_UNCOMPRESSED = 1 << 15


@dataclass
class Super:
    block_size: int
    fragments: int
    root_inode: int
    bytes_used: int
    inode_table_start: int
    directory_table_start: int
    fragment_table_start: int


class Reader:
    def __init__(self, image: bytes, sb: Super):
        self.image, self.sb = image, sb

    def block(self, absolute: int, metadata: bool = False) -> tuple[bytes, int]:
        if metadata:
            header = struct.unpack_from("<H", self.image, absolute)[0]
            size = header & 0x7FFF
            raw = self.image[absolute + 2 : absolute + 2 + size]
            data = raw if header & SQUASHFS_METADATA_UNCOMPRESSED else lzma.decompress(raw)
            return data, absolute + 2 + size
        raise NotImplementedError

    def metadata(self, table: int, block_offset: int, offset: int, length: int) -> bytes:
        """Read metadata bytes from a compressed-table physical block offset."""
        current = table + block_offset
        first = True
        output = bytearray()
        while len(output) < length:
            data, current = self.block(current, metadata=True)
            begin = offset if first else 0
            first = False
            if begin >= len(data):
                raise ValueError("metadata offset exceeds decoded block")
            take = min(length - len(output), len(data) - begin)
            output += data[begin : begin + take]
        return bytes(output)

    def inode(self, reference: int) -> tuple[int, bytes]:
        block_offset, offset = reference >> 16, reference & 0xFFFF
        raw = self.metadata(self.sb.inode_table_start, block_offset, offset, 512)
        inode_type = struct.unpack_from("<H", raw, 0)[0]
        return inode_type, raw

    def fragment(self, index: int) -> tuple[int, int]:
        # Fragment index entries are 64-bit physical metadata offsets, 512 entries per block.
        index_offset = self.sb.fragment_table_start + (index // 512) * 8
        metadata_offset = struct.unpack_from("<Q", self.image, index_offset)[0]
        raw = self.metadata(0, metadata_offset, (index % 512) * 16, 16)
        start_block, size, _unused = struct.unpack("<QII", raw)
        return start_block, size

    def data_block(self, start: int, size: int) -> bytes:
        compressed = not bool(size & SQUASHFS_COMPRESSED_BIT)
        length = size & 0xFFFFFF
        raw = self.image[start : start + length]
        return lzma.decompress(raw) if compressed else raw

    def regular_file(self, raw: bytes) -> bytes:
        # squashfs_reg_inode_header follows the 16-byte base inode header.
        start_block, fragment, frag_offset, file_size = struct.unpack_from("<IIII", raw, 16)
        output = bytearray()
        full_blocks = file_size // self.sb.block_size
        block_count = full_blocks if fragment != SQUASHFS_INVALID_FRAG else (file_size + self.sb.block_size - 1) // self.sb.block_size
        sizes = struct.unpack_from("<" + "I" * block_count, raw, 32) if block_count else ()
        current = start_block
        for size in sizes:
            decoded = self.data_block(current, size)
            output += decoded
            current += size & 0xFFFFFF
        if fragment != SQUASHFS_INVALID_FRAG and file_size % self.sb.block_size:
            fragment_start, fragment_size = self.fragment(fragment)
            fragment_data = self.data_block(fragment_start, fragment_size)
            output += fragment_data[frag_offset : frag_offset + (file_size % self.sb.block_size)]
        return bytes(output[:file_size])

    def directory(self, raw: bytes) -> list[tuple[str, int]]:
        start_block, _nlink, file_size, offset, _parent = struct.unpack_from("<IIHHI", raw, 16)
        # On disk file_size is stored as size-3.
        data = self.metadata(self.sb.directory_table_start, start_block, offset, file_size + 3)
        result: list[tuple[str, int]] = []
        pos = 0
        while pos + 12 <= len(data):
            count, inode_start, inode_base = struct.unpack_from("<III", data, pos)
            pos += 12
            for _ in range(count + 1):
                if pos + 8 > len(data):
                    return result
                inode_offset, inode_delta, _type, name_size = struct.unpack_from("<HhHH", data, pos)
                pos += 8
                name_len = name_size + 1
                if pos + name_len > len(data):
                    return result
                name = data[pos : pos + name_len].decode("utf-8", "surrogateescape")
                pos += name_len
                if name not in {".", ".."}:
                    result.append((name, (inode_start << 16) | inode_offset))
        return result


def safe_child(base: Path, name: str) -> Path:
    candidate = (base / name).resolve()
    if base.resolve() not in candidate.parents and candidate != base.resolve():
        raise ValueError(f"unsafe SquashFS name: {name!r}")
    return candidate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--manifest", type=Path, default=Path("analysis/padavan/rootfs-manifest.txt"))
    args = parser.parse_args()
    image = args.image.read_bytes()
    fields = struct.unpack_from("<5I6H8Q", image, 0)
    magic, _inodes, _mkfs_time, block_size, fragments, compression, _block_log, _flags, _no_ids, major, _minor, root_inode, bytes_used, _id_table, _xattr_table, inode_table, directory_table, fragment_table, _lookup_table = fields
    if magic != 0x73717368 or major != 4 or compression != 4:
        raise ValueError("Only SquashFS v4 with XZ compression is supported by this investigation tool.")
    sb = Super(block_size, fragments, root_inode, bytes_used, inode_table, directory_table, fragment_table)
    reader = Reader(image, sb)
    args.output.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest: list[str] = [f"Input: {args.image}", f"Output: {args.output}", ""]
    errors: list[str] = []
    visited: set[int] = set()

    def walk(reference: int, target: Path, display: str) -> None:
        if reference in visited:
            return
        visited.add(reference)
        inode_type, raw = reader.inode(reference)
        if inode_type == 1:  # directory
            target.mkdir(parents=True, exist_ok=True)
            manifest.append(f"DIR  {display}")
            for name, child_ref in reader.directory(raw):
                walk(child_ref, safe_child(target, name), f"{display}/{name}".replace("//", "/"))
        elif inode_type == 2:  # regular file
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(reader.regular_file(raw))
            manifest.append(f"FILE {display} ({target.stat().st_size} bytes)")
        else:
            manifest.append(f"SKIP {display} (inode type {inode_type})")

    try:
        walk(sb.root_inode, args.output.resolve(), "/")
    except Exception as exc:  # emit partial results for forensic debugging
        errors.append(f"Extraction stopped: {type(exc).__name__}: {exc}")
    manifest.extend(["", "Errors:", *(errors or ["none"])])
    args.manifest.write_text("\n".join(manifest) + "\n", encoding="utf-8")
    print(f"Extracted entries: {len(manifest)}; errors: {len(errors)}")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
