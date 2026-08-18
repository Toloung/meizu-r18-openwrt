# Meizu R18 OpenWrt

## Status

**Release Candidate** for Meizu R18, based on OpenWrt 25.12.5 and Linux
6.12.94. This repository builds tested recovery and sysupgrade images; it is
not an official OpenWrt target.

## Hardware

- MediaTek MT7628AN
- 128 MiB RAM
- 16 MiB S25FL128S1 SPI NOR
- MT7628 integrated 2.4 GHz radio
- MT7662 PCIe 5 GHz radio
- Two LAN ports and one WAN port

## Verified features

- LAN1 (P1) and LAN2 (P3)
- WAN configuration: P4 / `eth0.2`, DHCP and DHCPv6
- 2.4 GHz and 5 GHz access points
- LuCI, Chinese language default, and three installed themes
- Keep-settings and clean (`sysupgrade -n`) upgrades
- WPS/TFTP recovery image
- JFFS2 first/second boot and upgrade persistence
- S25FL128S1 256-byte page-program fix
- Read-only `r18-healthcheck`

**Pending:** WAN P4 DHCP and Internet physical validation with a real upstream
network. It has not been represented as completed.

## Port mapping

| Physical port | OpenWrt role |
| --- | --- |
| P1 | LAN1 |
| P3 | LAN2 |
| P4 | WAN |
| P6 | CPU / `eth0` |

## Wi-Fi

- 2.4 GHz: `R18-OpenWrt`
- 5 GHz: `R18-OpenWrt-5G`

The build receives the WPA2 key only through a GitHub Actions secret. Passwords
are not stored in this repository or documentation.

## LuCI themes

- **Liquid** — default on a clean install
- **Argon** — optional
- **Bootstrap** — official fallback

A settings-preserved sysupgrade explicitly retains `/etc/config/luci`, including
an existing `luci.main.mediaurlbase` choice that happens to equal the previous
firmware's ROM default. A clean upgrade selects Liquid.

## Flash layout

| Region | Range |
| --- | --- |
| Bootloader | `0x000000-0x030000` |
| Config | `0x030000-0x040000` |
| Factory | `0x040000-0x050000` |
| Firmware | `0x050000-0xF50000` |
| Storage | `0xF50000-0x1000000` |

**Never erase Factory.** Recovery and sysupgrade are designed to target the
firmware range only.

## Installation and upgrades

- First install or recovery: see [INSTALL.md](docs/INSTALL.md).
- WPS/TFTP recovery details: see [RECOVERY.md](docs/RECOVERY.md).
- Normal OpenWrt upgrades: see [SYSUPGRADE.md](docs/SYSUPGRADE.md).
- Hardware and SPI-NOR technical notes: see [HARDWARE.md](docs/HARDWARE.md).

## Healthcheck

Run `r18-healthcheck` over SSH or from LuCI's terminal. It is diagnostic and
read-only; a WAN warning is expected when P4 has no upstream cable.

## Known limitations

- WAN upstream DHCP / Internet physical validation is pending.
- Reset/WPS/LED GPIO mappings are not formally confirmed.
- Startup timing has not been aggressively optimized.
