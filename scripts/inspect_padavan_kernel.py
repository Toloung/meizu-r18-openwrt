#!/usr/bin/env python3
"""Search the decoded MZ-R18 Padavan kernel for board-level evidence."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


TERMS = re.compile(
    rb"(?:MZ-R18|\bR18\b|[Mm]eizu|MT7628\w*|MT7612\w*|ralink|mediatek|"
    rb"BOARD(?:_PID)?|PRODUCT(?:_ID)?|CONFIG_(?:PRODUCT|BOARD)|mtd(?:block)?\d*|"
    rb"/dev/mtd|Bootloader|U-Boot|Breed|Factory|EEPROM|cal(?:ibration|data)|"
    rb"HWADDR|et0macaddr|il0macaddr|rai0|ra0|iNIC|PCIe?|802\.11ac|"
    rb"eth\d|vlan|switch|esw|raeth|WAN(?:PORT)?|LAN(?:PORT|[12])?|"
    rb"GPIO|LED|POWER|WIFI|RESET|WPS|BUTTON|EHCI|OHCI|usb_storage|"
    rb"hanwckf|padavan|rt-n56u|prometheus)",
    re.IGNORECASE,
)


def printable_strings(data: bytes) -> list[tuple[int, str]]:
    return [(m.start(), m.group().decode("ascii", "replace")) for m in re.finditer(rb"[\x20-\x7e]{4,}", data)]


def main() -> None:
    kernel = Path("extracted/padavan/kernel.uncompressed.bin")
    report = Path("analysis/padavan/kernel-strings.txt")
    data = kernel.read_bytes()
    strings = printable_strings(data)
    hits = [(offset, value) for offset, value in strings if TERMS.search(value.encode())]
    Path("analysis/padavan").mkdir(parents=True, exist_ok=True)
    Path("analysis/padavan/kernel-all-strings.txt").write_text(
        "\n".join(f"0x{offset:08x}  {value}" for offset, value in strings) + "\n", encoding="utf-8")
    report.write_text(
        "\n".join([
            "# Padavan decoded-kernel evidence",
            "",
            f"- Artifact: `{kernel}`",
            f"- Length: {len(data)} bytes (`0x{len(data):x}`)",
            f"- SHA-256: `{hashlib.sha256(data).hexdigest()}`",
            f"- ELF at offset zero: {'yes' if data.startswith(bytes.fromhex('7f454c46')) else 'no'}",
            "",
            "## Keyword-bearing strings",
            "",
            *(f"`0x{offset:08x}`  {value}" for offset, value in hits),
            "",
            "## Interpretation constraints",
            "",
            "Strings identify compiled support and static defaults; an individual driver string is not accepted as proof that the R18 board uses that component unless linked to a board marker or runtime/configuration record.",
            "",
        ]), encoding="utf-8")
    print(f"Padavan kernel strings: {len(hits)} relevant entries.")


if __name__ == "__main__":
    main()
