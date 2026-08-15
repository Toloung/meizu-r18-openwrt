#!/usr/bin/env python3
"""Read-only evidence collector for a Meizu R18 bootloader dump.

This tool never opens an MTD device, never changes an input, and deliberately
does not dump arbitrary strings or nearby raw bytes.  It is intended for the
non-private 0x30000-byte mtd0_Bootloader.bin only; Factory, Config and full
flash dumps are rejected by the expected-size guard.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path


EXPECTED_SIZE = 0x30000
EXPECTED_MD5 = "f0f49f8e2a73dc3288bab13351ba111e"

# Only recovery-relevant terms are retained. This avoids accidentally exposing
# unrelated environment values from a user-provided dump.
TERMS = re.compile(
    rb"(?:tftp|bootm|bootfile|serverip|ipaddr|meizu_r18\.bin|"
    rb"system load linux|load linux|sdram|write to flash|cp\.linux|"
    rb"erase linux|erase|spi|wps|reset|gpio|u-boot|ralink|"
    rb"image|crc|checksum|header|kernel|recovery)",
    re.IGNORECASE,
)

CONSTANTS = {
    "uImage magic": 0x27051956,
    "firmware flash offset": 0x00050000,
    "storage flash offset": 0x00F50000,
    "16 MiB flash end": 0x01000000,
    "legacy default TFTP address": 0x80A00000,
    "proposed CLI-only test address": 0x82000000,
}


def printable_strings(blob: bytes) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    for match in re.finditer(rb"[\x20-\x7e]{4,}", blob):
        value = match.group().decode("ascii", "replace")
        if TERMS.search(match.group()):
            # A recovery report never needs a potential environment secret.
            if re.search(r"pass(word|wd)?|token|secret|key", value, re.I):
                value = "<redacted recovery-adjacent string>"
            result.append((match.start(), value))
    return result


def constant_hits(blob: bytes) -> list[dict[str, object]]:
    hits: list[dict[str, object]] = []
    for label, value in CONSTANTS.items():
        for endian, packed in (("little", struct.pack("<I", value)), ("big", struct.pack(">I", value))):
            pos = 0
            while (found := blob.find(packed, pos)) >= 0:
                hits.append({"label": label, "value": f"0x{value:08x}", "endian": endian, "file_offset": f"0x{found:05x}"})
                pos = found + 1
    return hits


def direct_jumps(blob: bytes, image_base: int) -> list[dict[str, str]]:
    """List MIPS J/JAL encodings, without claiming they are recovery code."""
    results: list[dict[str, str]] = []
    for offset in range(0, len(blob) - 3, 4):
        insn = struct.unpack_from("<I", blob, offset)[0]
        opcode = insn >> 26
        if opcode not in (2, 3):
            continue
        pc = image_base + offset
        target = ((pc + 4) & 0xF0000000) | ((insn & 0x03FFFFFF) << 2)
        results.append({
            "file_offset": f"0x{offset:05x}",
            "instruction": "jal" if opcode == 3 else "j",
            "target": f"0x{target:08x}",
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bootloader", type=Path, help="Read-only mtd0_Bootloader.bin path")
    parser.add_argument("--output", type=Path, default=Path("analysis/stage2_5"))
    parser.add_argument("--image-base", type=lambda value: int(value, 0), default=0xBC000000,
                        help="Unverified virtual mapping used only to render J/JAL candidates (default: 0xbc000000)")
    args = parser.parse_args()

    if not args.bootloader.is_file():
        raise SystemExit(f"Input not found: {args.bootloader}")
    if args.bootloader.stat().st_size != EXPECTED_SIZE:
        raise SystemExit(f"Refusing {args.bootloader}: expected exactly 0x{EXPECTED_SIZE:x} bytes (mtd0 only).")

    blob = args.bootloader.read_bytes()
    md5 = hashlib.md5(blob).hexdigest()
    report = {
        "input_name": args.bootloader.name,
        "input_size": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "md5": md5,
        "expected_md5_matches": md5 == EXPECTED_MD5,
        "image_base_for_jump_rendering": f"0x{args.image_base:08x}",
        "strings": [{"file_offset": f"0x{offset:05x}", "text": value} for offset, value in printable_strings(blob)],
        "constant_hits": constant_hits(blob),
        "direct_jumps": direct_jumps(blob, args.image_base),
        "limits": [
            "String and constant hits are locations, not proof of a callable recovery path.",
            "J/JAL targets depend on the unverified image-base assumption and require disassembly/control-flow review.",
            "No conclusion about WPS GPIO, RAM buffer, erase/write range, image validation, or RAM-only recovery is made automatically.",
        ],
    }
    args.output.mkdir(parents=True, exist_ok=True)
    json_path = args.output / "r18_bootloader_recovery_evidence.json"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    string_lines = [f"- `{item['file_offset']}`: `{item['text']}`" for item in report["strings"]]
    constant_lines = [
        f"- {item['label']} `{item['value']}` ({item['endian']}) at `{item['file_offset']}`"
        for item in report["constant_hits"]
    ]
    lines = [
        "# Meizu R18 bootloader recovery evidence (machine-assisted, read-only)",
        "",
        f"- Input: `{report['input_name']}`; size `{report['input_size']}` bytes.",
        f"- MD5: `{md5}`; expected baseline match: **{report['expected_md5_matches']}**.",
        f"- SHA-256: `{report['sha256']}`.",
        f"- J/JAL rendering base: `{report['image_base_for_jump_rendering']}` (**UNVERIFIED mapping assumption**).",
        "",
        "## Recovery-relevant strings",
        "",
        *(string_lines or ["- None found."]),
        "",
        "## Constant byte-pattern hits",
        "",
        *(constant_lines or ["- None found."]),
        "",
        "## Direct MIPS J/JAL candidates",
        "",
        "The complete machine-readable candidate list is in the JSON output. These are not function identifications.",
        f"- Count: {len(report['direct_jumps'])}.",
        "",
        "## Limits",
        "",
        *(f"- {item}" for item in report["limits"]),
        "",
    ]
    (args.output / "r18_bootloader_recovery_evidence.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Read-only report written to {args.output}; MD5 baseline match={report['expected_md5_matches']}.")


if __name__ == "__main__":
    main()
