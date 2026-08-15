#!/usr/bin/env python3
"""Read-only ELF/MIPS inventory, disassembly and literal-xref analysis for Stage 1.6.

This deliberately uses only the already installed ``pyelftools`` package and a
small, documented MIPS32 decoder.  It does not execute any router binary.
"""

from __future__ import annotations

import argparse
import re
import struct
from collections import defaultdict
from pathlib import Path

from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection
from elftools.elf.sections import SymbolTableSection


REG = ["$zero", "$at", "$v0", "$v1", "$a0", "$a1", "$a2", "$a3", "$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7", "$s0", "$s1", "$s2", "$s3", "$s4", "$s5", "$s6", "$s7", "$t8", "$t9", "$k0", "$k1", "$gp", "$sp", "$fp", "$ra"]
TARGETS = [
    "MZ-R18", "lan_eeprom_mac", "wan_eeprom_mac", "radio2_eeprom_mac",
    "radio5_eeprom_mac", "front_led_pwr", "front_led_usb", "usb5v",
    "reset", "wps", "Factory", "EEPROM", "Storage", "eth2", "eth2.1",
    "eth2.2", "WAN", "LAN", "LAN1", "LAN2", "MT7612", "MT7628",
]


def sx16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def disasm(addr: int, word: int) -> str:
    op, rs, rt, rd, sh, fn, imm, target = (word >> 26, (word >> 21) & 31,
        (word >> 16) & 31, (word >> 11) & 31, (word >> 6) & 31, word & 63,
        word & 0xffff, word & 0x03ffffff)
    if word == 0:
        return "nop"
    if op == 0:
        special = {0x00: "sll", 0x02: "srl", 0x03: "sra", 0x08: "jr", 0x09: "jalr",
                   0x0a: "movz", 0x0b: "movn", 0x20: "add", 0x21: "addu", 0x22: "sub", 0x23: "subu", 0x24: "and",
                   0x25: "or", 0x26: "xor", 0x27: "nor", 0x2a: "slt", 0x2b: "sltu"}
        name = special.get(fn, f"special_{fn:02x}")
        if fn in (0x00, 0x02, 0x03): return f"{name} {REG[rd]}, {REG[rt]}, {sh}"
        if fn == 0x08: return f"jr {REG[rs]}"
        if fn == 0x09: return f"jalr {REG[rd]}, {REG[rs]}"
        if fn in (0x0a, 0x0b): return f"{name} {REG[rd]}, {REG[rs]}, {REG[rt]}"
        return f"{name} {REG[rd]}, {REG[rs]}, {REG[rt]}"
    if op in (2, 3):
        dst = ((addr + 4) & 0xf0000000) | (target << 2)
        return f"{'j' if op == 2 else 'jal'} 0x{dst:08x}"
    names = {4:"beq",5:"bne",6:"blez",7:"bgtz",8:"addi",9:"addiu",10:"slti",11:"sltiu",
             12:"andi",13:"ori",14:"xori",15:"lui",32:"lb",33:"lh",34:"lwl",35:"lw",
             36:"lbu",37:"lhu",38:"lwr",40:"sb",41:"sh",42:"swl",43:"sw",46:"swr",20:"beql",21:"bnel"}
    name = names.get(op, f"op_{op:02x}")
    if op == 15: return f"lui {REG[rt]}, 0x{imm:04x}"
    if op == 1:
        branch = {0:"bltz", 1:"bgez", 16:"bltzal", 17:"bgezal"}.get(rt, f"regimm_{rt:02x}")
        return f"{branch} {REG[rs]}, 0x{(addr + 4 + (sx16(imm) << 2)) & 0xffffffff:08x}"
    if op in (4, 5, 20, 21): return f"{name} {REG[rs]}, {REG[rt]}, 0x{(addr + 4 + (sx16(imm) << 2)) & 0xffffffff:08x}"
    if op in (6, 7): return f"{name} {REG[rs]}, 0x{(addr + 4 + (sx16(imm) << 2)) & 0xffffffff:08x}"
    if op in (32,33,34,35,36,37,38,40,41,42,43,46): return f"{name} {REG[rt]}, {sx16(imm)}({REG[rs]})"
    if op in (12,13,14): return f"{name} {REG[rt]}, {REG[rs]}, 0x{imm:04x}"
    return f"{name} {REG[rt]}, {REG[rs]}, {sx16(imm)}"


def strings_in_load_segments(elf: ELFFile, wanted: list[str]) -> dict[int, str]:
    found: dict[int, str] = {}
    lower = [item.lower() for item in wanted]
    for segment in elf.iter_segments():
        if segment["p_type"] != "PT_LOAD":
            continue
        raw = segment.data()
        for match in re.finditer(rb"[\x20-\x7e]{4,}", raw):
            text = match.group().decode("ascii", "replace")
            if any(needle in text.lower() for needle in lower):
                found[segment["p_vaddr"] + match.start()] = text
    return found


def exec_words(elf: ELFFile):
    for section in elf.iter_sections():
        if not (section["sh_flags"] & 0x4):
            continue
        raw = section.data()
        if len(raw) % 4:
            raw = raw[:len(raw) - len(raw) % 4]
        endian = "<" if elf.little_endian else ">"
        for off in range(0, len(raw), 4):
            yield section.name, section["sh_addr"] + off, struct.unpack_from(endian + "I", raw, off)[0]


def symbols(elf: ELFFile):
    imports, exports, all_symbols = [], [], []
    for section in elf.iter_sections():
        if not isinstance(section, SymbolTableSection):
            continue
        for symbol in section.iter_symbols():
            name = symbol.name
            if not name:
                continue
            rec = (name, symbol["st_value"], symbol["st_size"], section.name)
            all_symbols.append(rec)
            if symbol["st_shndx"] == "SHN_UNDEF": imports.append(rec)
            elif symbol["st_info"]["type"] in ("STT_FUNC", "STT_OBJECT"): exports.append(rec)
    return imports, exports, all_symbols


def parse_modinfo(elf: ELFFile) -> list[str]:
    section = elf.get_section_by_name(".modinfo")
    return [] if section is None else [item.decode("ascii", "replace") for item in section.data().split(b"\0") if item]


def mips_literal_xrefs(elf: ELFFile, literals: dict[int, str]):
    words = list(exec_words(elf))
    starts = {elf.header["e_entry"]}
    direct_calls = defaultdict(list)
    for _, addr, word in words:
        if word >> 26 == 3:
            dst = ((addr + 4) & 0xf0000000) | ((word & 0x03ffffff) << 2)
            starts.add(dst); direct_calls[dst].append(addr)
    starts = sorted(starts)
    xrefs = []
    for index in range(len(words) - 1):
        _, addr, first = words[index]
        _, next_addr, second = words[index + 1]
        if next_addr != addr + 4 or first >> 26 != 15:
            continue
        hi_reg = (first >> 16) & 31
        op, rs, rt, imm = second >> 26, (second >> 21) & 31, (second >> 16) & 31, second & 0xffff
        if op not in (9, 13) or rs != hi_reg:
            continue
        base = (first & 0xffff) << 16
        value = (base + (sx16(imm) if op == 9 else imm)) & 0xffffffff
        if value not in literals:
            continue
        function = max((item for item in starts if item <= addr), default=addr)
        following = min((item for item in starts if item > function), default=function + 0)
        snippet = [f"0x{a:08x}: {disasm(a, w)}" for _, a, w in words[max(0, index - 2):index + 5]]
        xrefs.append({"literal": literals[value], "literal_addr": value, "at": addr,
                      "function": function, "function_end": following if following else None,
                      "callers": direct_calls.get(function, []), "snippet": snippet,
                      "pair": f"{disasm(addr, first)} ; {disasm(next_addr, second)}"})
    return xrefs, words


def markdown_inventory(records: list[dict]) -> str:
    lines = ["# Stage 1.6 binary inventory", "", "All data below comes from static ELF parsing; no binary was executed.", "",
             "| Path | ELF type | Machine / endian | Stripped | Dynamic | Imports | Exports | .modinfo |", "| -- | -- | -- | -- | -- | --: | --: | -- |"]
    for rec in records:
        lines.append(f"| `{rec['path']}` | {rec['type']} | {rec['machine']} / {rec['endian']} | {rec['stripped']} | {rec['dynamic']} | {rec['imports']} | {rec['exports']} | {rec['modinfo']} |")
    for rec in records:
        lines += ["", f"## `{rec['path']}`", "", f"- ELF class: {rec['class']}; entry: `{rec['entry']}`.",
                  f"- Sections: {', '.join(rec['sections'])}."]
        if rec["import_names"]: lines.append("- Imports: " + ", ".join(f"`{x}`" for x in rec["import_names"][:40]) + ".")
        if rec["export_names"]: lines.append("- Exported symbols: " + ", ".join(f"`{x}`" for x in rec["export_names"][:40]) + ".")
        if rec["modinfo_lines"]: lines.append("- Module metadata: " + "; ".join(f"`{x}`" for x in rec["modinfo_lines"]) + ".")
    return "\n".join(lines) + "\n"


def analyse_one(path: Path) -> tuple[dict, list[dict], list[tuple[str, int, int]]]:
    with path.open("rb") as stream:
        elf = ELFFile(stream)
        imports, exports, all_symbols = symbols(elf)
        dynamic = elf.get_section_by_name(".dynamic") is not None
        record = {
            "path": path.as_posix(), "type": elf.header["e_type"], "machine": elf.header["e_machine"],
            "endian": "little" if elf.little_endian else "big", "class": elf.elfclass,
            "entry": f"0x{elf.header['e_entry']:08x}", "stripped": "yes" if elf.get_section_by_name(".symtab") is None else "no",
            "dynamic": "yes" if dynamic else "no", "imports": len(imports), "exports": len(exports),
            "modinfo": "yes" if elf.get_section_by_name(".modinfo") else "no",
            "sections": [item.name for item in elf.iter_sections()], "import_names": [item[0] for item in imports],
            "export_names": [item[0] for item in exports], "modinfo_lines": parse_modinfo(elf),
        }
        literals = strings_in_load_segments(elf, TARGETS)
        xrefs, _ = mips_literal_xrefs(elf, literals) if elf.header["e_machine"] == "EM_MIPS" else ([], [])
        relocs = []
        for sec in elf.iter_sections():
            if isinstance(sec, RelocationSection): relocs.append((sec.name, sec["sh_size"], sec["sh_entsize"]))
        return record, xrefs, relocs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, default=Path("analysis/stage1_6"))
    parser.add_argument("--dump", metavar="PATH:START:END", help="Print a read-only MIPS disassembly range (hex addresses).")
    parser.add_argument("--got", metavar="PATH:GP:OFFSET", help="Resolve a MIPS GOT slot through ELF relocations (hex or decimal GP/offset).")
    parser.add_argument("--dynamic", metavar="PATH", help="Print dynamic tags for an ELF (read-only diagnostic).")
    parser.add_argument("--symbol", metavar="PATH:NAME", help="Print matching ELF symbol records (read-only diagnostic).")
    parser.add_argument("--symbols-like", metavar="PATH:PATTERN", help="Print ELF symbols whose names match a case-insensitive regex (read-only diagnostic).")
    parser.add_argument("--calls", metavar="PATH:ADDRESS", help="List direct MIPS `jal` call sites to an address with the preceding eight instructions (read-only diagnostic).")
    parser.add_argument("--strings-like", metavar="PATH:PATTERN", help="Print printable load-segment strings matching a case-insensitive regex (read-only diagnostic).")
    parser.add_argument("--mips-got", metavar="PATH", help="List the MIPS global-offset-table symbol mapping (read-only diagnostic).")
    parser.add_argument("--jalr-got", metavar="PATH:GP:OFFSET", help="List `lw $t9, offset($gp)` / `jalr $t9` call candidates and preceding instructions (read-only diagnostic).")
    args = parser.parse_args()
    if args.dump:
        path_text, start_text, end_text = args.dump.rsplit(":", 2)
        start, end = int(start_text, 0), int(end_text, 0)
        with Path(path_text).open("rb") as stream:
            elf = ELFFile(stream)
            for _, address, word in exec_words(elf):
                if start <= address <= end:
                    print(f"0x{address:08x}: {word:08x}  {disasm(address, word)}")
        return
    if args.got:
        path_text, gp_text, offset_text = args.got.rsplit(":", 2)
        slot = (int(gp_text, 0) + int(offset_text, 0)) & 0xffffffff
        with Path(path_text).open("rb") as stream:
            elf = ELFFile(stream)
            for section in elf.iter_sections():
                if not isinstance(section, RelocationSection):
                    continue
                linked = elf.get_section(section["sh_link"])
                for relocation in section.iter_relocations():
                    if relocation["r_offset"] == slot:
                        print(f"GOT slot 0x{slot:08x}: {linked.get_symbol(relocation['r_info_sym']).name} ({section.name})")
                        return
            dynamic = elf.get_section_by_name(".dynamic")
            got = elf.get_section_by_name(".got")
            dynsym = elf.get_section_by_name(".dynsym")
            if dynamic is not None and got is not None and dynsym is not None:
                tags = {tag.entry.d_tag: tag.entry.d_val for tag in dynamic.iter_tags()}
                local = tags.get("DT_MIPS_LOCAL_GOTNO")
                first_symbol = tags.get("DT_MIPS_GOTSYM")
                index = (slot - got["sh_addr"]) // 4
                if local is not None and first_symbol is not None and index >= local:
                    symbol_index = first_symbol + index - local
                    if symbol_index < dynsym.num_symbols():
                        print(f"GOT slot 0x{slot:08x}: {dynsym.get_symbol(symbol_index).name} (.got index {index}, dynsym {symbol_index})")
                        return
            if got is not None and got["sh_addr"] <= slot < got["sh_addr"] + got["sh_size"]:
                offset_in_got = slot - got["sh_addr"]
                value = struct.unpack_from("<I" if elf.little_endian else ">I", got.data(), offset_in_got)[0]
                print(f"GOT slot 0x{slot:08x}: local/raw pointer 0x{value:08x} (.got index {offset_in_got // 4})")
                return
        print(f"GOT slot 0x{slot:08x}: unresolved")
        return
    if args.dynamic:
        with Path(args.dynamic).open("rb") as stream:
            elf = ELFFile(stream)
            section = elf.get_section_by_name(".dynamic")
            if section is None:
                print("no .dynamic")
            else:
                for tag in section.iter_tags():
                    print(f"{tag.entry.d_tag}: 0x{tag.entry.d_val:x}")
        return
    if args.symbol:
        path_text, symbol_name = args.symbol.rsplit(":", 1)
        with Path(path_text).open("rb") as stream:
            elf = ELFFile(stream)
            for section in elf.iter_sections():
                if not isinstance(section, SymbolTableSection):
                    continue
                for symbol in section.iter_symbols():
                    if symbol.name == symbol_name:
                        print(f"{section.name}: {symbol.name} value=0x{symbol['st_value']:08x} size={symbol['st_size']} type={symbol['st_info']['type']} bind={symbol['st_info']['bind']} index={symbol['st_shndx']}")
        return
    if args.symbols_like:
        path_text, pattern = args.symbols_like.rsplit(":", 1)
        wanted = re.compile(pattern, re.IGNORECASE)
        with Path(path_text).open("rb") as stream:
            elf = ELFFile(stream)
            for section in elf.iter_sections():
                if not isinstance(section, SymbolTableSection):
                    continue
                for symbol in section.iter_symbols():
                    if symbol.name and wanted.search(symbol.name):
                        print(f"{section.name}: {symbol.name} value=0x{symbol['st_value']:08x} size={symbol['st_size']} type={symbol['st_info']['type']} bind={symbol['st_info']['bind']} index={symbol['st_shndx']}")
        return
    if args.calls:
        path_text, target_text = args.calls.rsplit(":", 1)
        target = int(target_text, 0)
        with Path(path_text).open("rb") as stream:
            elf = ELFFile(stream)
            words = list(exec_words(elf))
            for index, (_, address, word) in enumerate(words):
                if word >> 26 != 3:
                    continue
                destination = ((address + 4) & 0xf0000000) | ((word & 0x03ffffff) << 2)
                if destination != target:
                    continue
                print(f"CALL 0x{address:08x} -> 0x{destination:08x}")
                for _, nearby_addr, nearby_word in words[max(0, index - 8):min(len(words), index + 2)]:
                    print(f"  0x{nearby_addr:08x}: {nearby_word:08x}  {disasm(nearby_addr, nearby_word)}")
        return
    if args.strings_like:
        path_text, pattern = args.strings_like.rsplit(":", 1)
        wanted = re.compile(pattern, re.IGNORECASE)
        with Path(path_text).open("rb") as stream:
            elf = ELFFile(stream)
            for segment in elf.iter_segments():
                if segment["p_type"] != "PT_LOAD":
                    continue
                for match in re.finditer(rb"[\\x20-\\x7e]{4,}", segment.data()):
                    value = match.group().decode("ascii", "replace")
                    if wanted.search(value):
                        print(f"0x{segment['p_vaddr'] + match.start():08x}: {value}")
        return
    if args.mips_got:
        with Path(args.mips_got).open("rb") as stream:
            elf = ELFFile(stream)
            dynamic = elf.get_section_by_name(".dynamic")
            got = elf.get_section_by_name(".got")
            dynsym = elf.get_section_by_name(".dynsym")
            if dynamic is None or got is None or dynsym is None:
                print("no MIPS dynamic GOT mapping")
                return
            tags = {tag.entry.d_tag: tag.entry.d_val for tag in dynamic.iter_tags()}
            local = tags.get("DT_MIPS_LOCAL_GOTNO")
            first_symbol = tags.get("DT_MIPS_GOTSYM")
            if local is None or first_symbol is None:
                print("no DT_MIPS_LOCAL_GOTNO/DT_MIPS_GOTSYM")
                return
            for index in range(local, got["sh_size"] // 4):
                symbol_index = first_symbol + index - local
                if symbol_index >= dynsym.num_symbols():
                    break
                symbol = dynsym.get_symbol(symbol_index)
                print(f"0x{got['sh_addr'] + index * 4:08x}: {symbol.name} (dynsym {symbol_index})")
        return
    if args.jalr_got:
        path_text, gp_text, offset_text = args.jalr_got.rsplit(":", 2)
        gp, offset = int(gp_text, 0), int(offset_text, 0)
        with Path(path_text).open("rb") as stream:
            elf = ELFFile(stream)
            words = list(exec_words(elf))
            for index, (_, address, word) in enumerate(words):
                op, rs, rt, imm = word >> 26, (word >> 21) & 31, (word >> 16) & 31, sx16(word & 0xffff)
                if not (op == 35 and rs == 28 and rt == 25 and imm == offset):
                    continue
                nearby = words[index:min(len(words), index + 4)]
                if not any((candidate >> 26) == 0 and (candidate & 63) == 9 and ((candidate >> 21) & 31) == 25 for _, _, candidate in nearby):
                    continue
                print(f"GOT CALL 0x{address:08x}: slot 0x{(gp + offset) & 0xffffffff:08x}")
                for _, nearby_addr, nearby_word in words[max(0, index - 8):min(len(words), index + 4)]:
                    print(f"  0x{nearby_addr:08x}: {nearby_word:08x}  {disasm(nearby_addr, nearby_word)}")
        return
    out = args.out
    for sub in ("rc", "wifi", "kernel", "switch", "gpio", "mtd", "reports"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    targets = [
        args.root / "sbin/rc", args.root / "bin/mtd_write", args.root / "sbin/switch",
        args.root / "usr/sbin/nvram", args.root / "lib/libshared.so",
        args.root / "lib/modules/3.4.113/kernel/drivers/net/wireless/ralink/mt7628_ap/mt7628_ap.ko",
        args.root / "lib/modules/3.4.113/kernel/drivers/net/wireless/ralink/mt76x2_ap/mt76x2_ap.ko",
    ]
    records, by_name, relocs = [], {}, {}
    for target in targets:
        if not target.exists(): continue
        record, xrefs, relocation_info = analyse_one(target)
        records.append(record); by_name[target.name] = xrefs; relocs[target.name] = relocation_info
    (out / "reports/binary-inventory.md").write_text(markdown_inventory(records), encoding="utf-8")

    rcx = by_name.get("rc", [])
    lines = ["# `/sbin/rc` MIPS literal xrefs", "", "Method: ELF load-segment string addresses were matched to adjacent `lui` + `addiu`/`ori` absolute-address constructions in executable sections. Function boundaries and callers are inferred from entry/direct `jal` targets; position-independent `jalr` calls are not resolved. Thus this is disassembly evidence, not a decompiler reconstruction.", ""]
    if not rcx:
        lines += ["No target literal used a directly recoverable `lui` pair. This does not mean it is unused: MIPS PIC/GOT references require relocation/runtime-GP resolution."]
    for item in rcx:
        end = f"–0x{item['function_end'] - 1:08x}" if item["function_end"] else " (end unknown)"
        callers = ", ".join(f"0x{x:08x}" for x in item["callers"]) or "none recovered (direct `jal` only)"
        lines += [f"## `{item['literal']}`", "", f"- String address: `0x{item['literal_addr']:08x}`.", f"- Reference at: `0x{item['at']:08x}`; enclosing inferred function: `0x{item['function']:08x}{end}`.", f"- Direct callers recovered: {callers}.", f"- Address construction: `{item['pair']}`.", "", "```asm", *item["snippet"], "```", ""]
    (out / "rc/xrefs.md").write_text("\n".join(lines), encoding="utf-8")

    def module_doc(name: str, title: str, expected: str):
        record = next((r for r in records if r["path"].endswith(name)), None)
        lines = [f"# {title}", "", "Static ELF evidence only; this relocatable module has no final load address, so no board flash address is inferred.", ""]
        if record:
            lines += [f"- ELF: `{record['type']}`, `{record['machine']}`, {record['endian']}-endian, stripped={record['stripped']}.", f"- Relocation sections: " + (", ".join(name for name, _, _ in relocs.get(name, [])) or "none") + ".", f"- .modinfo: " + ("; ".join(f"`{x}`" for x in record['modinfo_lines']) or "absent") + "."]
        lines += ["", "## Result", "", expected, ""]
        return "\n".join(lines)
    (out / "wifi/mt7628-module.md").write_text(module_doc("mt7628_ap.ko", "MT7628 AP module", "The module packages an MT7628 EEPROM fallback path, but this module alone does not identify an R18 Factory/MTD partition, offset, or a runtime-preferred source."), encoding="utf-8")
    (out / "wifi/mt76x2-module.md").write_text(module_doc("mt76x2_ap.ko", "MT76x2 / MT7612E AP module", "`.modinfo` PCI aliases and code strings are module evidence for the supported PCI family. They do not substitute for a live PCI probe or reveal an R18 Factory/MTD calibration offset."), encoding="utf-8")

    (out / "gpio/GPIO_CANDIDATES.md").write_text("# GPIO candidates\n\nNo R18-specific GPIO constant was recovered from an R18-specific code branch. Generic `/sbin/rc` GPIO and LED functions are deliberately not converted into R18 GPIO assignments.\n", encoding="utf-8")
    (out / "mtd/OFFSET_CANDIDATES.md").write_text("# Flash-offset candidates\n\nNo MIPS instruction/data pair was recovered that binds a physical MTD/Factory/EEPROM offset to an MZ-R18-specific branch. Immediate constants in generic code are not reported as flash offsets.\n", encoding="utf-8")
    (out / "switch/SWITCH_ANALYSIS.md").write_text("# Switch analysis\n\n`/sbin/rc` contains generic VLAN/switch management and `eth2`, `eth2.1`, `eth2.2` strings, but this static ELF pass recovered no MZ-R18-specific port mask or switch register table. WAN/LAN/CPU-port mapping remains unknown.\n", encoding="utf-8")
    (out / "kernel/kernel-analysis.md").write_text("# Kernel analysis\n\nThe decompressed kernel is a raw MIPS image, not an ELF file. Its command line and targeted strings remain evidence of MT7628 and `root=/dev/mtdblock4`; a static named partition array with bound offsets was not recovered in this pass. No physical layout is inferred.\n", encoding="utf-8")
    print(f"analysed {len(records)} ELF files; rc direct literal xrefs={len(rcx)}")


if __name__ == "__main__":
    main()
