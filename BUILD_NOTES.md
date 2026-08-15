# Build / analysis log

## 2026-08-13 — workspace initialization

- Created the required project structure.
- Copied the supplied `meizu_r18原.bin` to `firmware/meizu_r18原.bin` and set that analysis copy to Windows read-only. The original root-level file was left intact.
- No device connection, flash operation, firmware generation, or OpenWrt source modification was performed.

## 2026-08-13 — basic identity and layout

- Commands/tools: PowerShell `Get-FileHash`; `scripts/analyze_firmware.py` (Python standard library).
- SHA-256: `9261AD191BEE416C4281ED5B6612E60F95EFDC1D709417DF360C8049EDECA8F4`.
- MD5: `17C4F0610E06D70165B69B24035F9141`.
- Found and validated uImage at `0x0`; both header and data CRCs are valid. Extracted only verified component copies to `extracted/`.
- Found and structurally validated a SquashFS 4.0/XZ rootfs at `0x00149165`. Byte patterns resembling JFFS2/XZ elsewhere were rejected as compressed-data false positives.

## 2026-08-13 — kernel and DTB inspection

- Commands/tools: `scripts/inspect_artifacts.py` (Python standard library).
- LZMA decompression produced a 4,015,836-byte kernel. Kernel evidence establishes Linux 3.10.14, MIPS, Ralink MT7628, and vendor Meizu code.
- Scan found no structurally valid FDT. `dtc` was unavailable, so no DTS was fabricated.

## 2026-08-13 — tool availability / failures retained

- Missing: `file`, `binwalk`, `xxd`, `hexdump`, `strings`, `fdisk`, `parted`, `7z`, `unsquashfs`, `ubireader`, `dtc`, and `dd`.
- `wsl -l -q` showed no installed WSL Linux distribution.
- Initial `git clone` failed due to Windows Schannel credentials: `SEC_E_NO_CREDENTIALS`. Retrying transiently with Git's OpenSSL backend succeeded.
- No matching PyPI extractor package was found in the attempted names noted in `TODO.md`; no new dependency was installed.

## 2026-08-13 — OpenWrt reference checkout

- Command: `git -c http.sslBackend=openssl clone --depth 1 --branch v25.12.5 https://github.com/openwrt/openwrt.git openwrt`
- Result: detached, clean checkout at `f0a60eee2fe051741c643ea6118718aae1ef17fb`, tag `v25.12.5`.
- Inspection only; no OpenWrt source file was changed.

## 2026-08-13 — Padavan / MZ-R18 static analysis (Stage 1.5)

- Discovered the additional read-only image dynamically in `firmware/`: `meizu_r18 - 老毛子.bin`.
- Commands/tools: PowerShell `Get-FileHash`; `scripts/analyze_padavan.py`; `scripts/inspect_padavan_kernel.py`; `scripts/extract_squashfs_xz.py`; and `scripts/extract_printable_strings.py` (all Python standard library).
- SHA-256: `755E429C403410F24A5AE81E267320C96290264E5E8952B1EE3BC2C4B7CF2C6C`; MD5: `E73FF678D1342CA1F966115867AA9EF7`.
- It is a CRC-valid U-Boot legacy uImage whose header and `/sbin/rc` both identify MZ-R18. It contains LZMA kernel plus SquashFS v4/XZ rootfs, not TRX/Breed/raw SPI content.
- `scripts/extract_squashfs_xz.py` completed with 1,327 manifest entries and no parser errors. It recovers logical directories/regular files and records rather than materializes special nodes.
- A shallow `hanwckf/rt-n56u` clone was attempted using the temporary OpenSSL Git backend. Fetch succeeded, but Windows worktree checkout failed on the tracked path `trunk/user/ipset/ipset-6.x/tests/bitmap:ip` (colon is invalid on Windows). Git metadata was retained at commit `23387b278a7cf728748af606760758f5d59d1451`; no MZ-R18 source profile was identified and the repository is not claimed as the image source.
- No device operation, MTD operation, bootloader modification, firmware generation, or OpenWrt source modification was performed.

## 2026-08-13 — Stage 1.6 binary reverse engineering

- Analysed extracted Padavan MIPS ELF binaries statically with `scripts/stage16_mips_analysis.py` and installed `pyelftools`; no binary or module was executed.
- No MIPS cross-binutils, Ghidra, radare2/rizin, `readelf`, or `objdump` was available. The project script records ELF headers/sections/symbol metadata, direct MIPS literal xrefs and GOT resolution.
- Recovered Padavan logical Factory reads from `/sbin/rc`: 2.4G MAC `+0x0004`, WAN MAC `+0x0022`, LAN MAC `+0x0028`, country code `+0x0188` (2 bytes), and 5G MAC `+0x8004`; MAC reads use 6 bytes.
- Examined a related public Padavan Git object database only. Its generic function semantics match the binary’s Factory read/command-dispatch behavior, but it lacks MZ-R18 and is not claimed as the exact build source.
- No router connection, flash/MTD operation, OpenWrt source modification, build or firmware generation was performed.
