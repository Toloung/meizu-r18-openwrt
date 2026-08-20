# Meizu R18 OpenWrt

OpenWrt 25.12.5 support for the Meizu R18. This project provides recovery and
sysupgrade images for the MT7628-based router; it is not an official OpenWrt
target.

Current release candidate: **v0.4.0-rc5**.

## Features

- OpenWrt 25.12.5 with Linux 6.12.94
- S25FL128S1 SPI NOR fix: 256-byte page programming for JEDEC
  `01 20 18 4d 01 80`
- Full-size WPS/TFTP recovery image with a clean `rootfs_data` marker and
  erased (`FF`) suffix
- Compact, board-checked sysupgrade image targeting only the firmware area
- LAN and WAN configuration with DHCP, DHCPv6, firewall, and NAT
- 2.4 GHz Wi-Fi and MT7662 PCIe 5 GHz Wi-Fi
- LuCI with Simplified Chinese, Argon as the ROM default, and Bootstrap as a
  fallback
- Read-only `r18-healthcheck` diagnostics
- Retained manual `r18-net-rescue` framework, disabled by default

## Hardware

| Component | Supported hardware |
| --- | --- |
| SoC | MediaTek MT7628AN |
| Flash | 16 MiB Spansion S25FL128S1 SPI NOR |
| Wireless | Integrated 2.4 GHz plus MT7662 PCIe 5 GHz |

## Network

The default LAN address is `192.168.1.1/24`.

| R18 switch port | OpenWrt role |
| --- | --- |
| P1 | LAN1 |
| P3 | LAN2 |
| P4 | WAN |
| P6 | CPU / `eth0` |

WAN uses DHCP and DHCPv6. The firewall's WAN zone provides NAT and LAN-to-WAN
forwarding. WAN Internet connectivity has been validated with a real upstream
network on hardware; RC5 does not change this network path.

## Wireless

Both radios are enabled on a clean install and bridge to LAN.

| Band | SSID | Security |
| --- | --- | --- |
| 2.4 GHz | `R18-OpenWrt` | WPA2-PSK/CCMP |
| 5 GHz | `R18-OpenWrt-5G` | WPA2-PSK/CCMP |

The public factory Wi-Fi password is `password`.

**Change the wireless password immediately after first login.** It is not a
LuCI or root password; management credentials are handled separately.

## LuCI

- Default clean-install theme: **Argon**
- Installed fallback theme: **Bootstrap**
- Liquid is not included
- Default language: Simplified Chinese

The image includes `/lib/upgrade/keep.d/r18-luci`, so a normal settings-kept
sysupgrade retains `/etc/config/luci`, including a user-selected theme. A clean
upgrade uses the Argon ROM default and does not run a boot-time theme override.

## Flash layout

The 16 MiB SPI NOR layout is preserved by the supplied images.

| Region | Physical range |
| --- | --- |
| Bootloader | `0x000000-0x030000` |
| Config | `0x030000-0x040000` |
| Factory | `0x040000-0x050000` |
| Firmware | `0x050000-0xF50000` |
| Storage | `0xF50000-0x1000000` |

The recovery image is exactly `0xF00000` bytes and maps only to Firmware. It
places the `DE AD C0 DE` `rootfs_data` marker after SquashFS and pads the
remaining firmware space with `FF`; it does not cover Bootloader, Config,
Factory, or Storage.

## Upgrade

- First install or recovery: use `meizu_r18.bin` with the documented
  [WPS/TFTP recovery procedure](docs/RECOVERY.md).
- Normal upgrade: use the `*-squashfs-sysupgrade.bin` image and validate it
  before writing:

  ```sh
  sysupgrade -T /tmp/openwrt-ramips-mt76x8-meizu_r18-squashfs-sysupgrade.bin
  sysupgrade /tmp/openwrt-ramips-mt76x8-meizu_r18-squashfs-sysupgrade.bin
  ```

- Clean upgrade: use `sysupgrade -n` with the same sysupgrade image.

Do not use a recovery image as a sysupgrade image. See
[SYSUPGRADE.md](docs/SYSUPGRADE.md) for safety notes. Stage 3.5 keep-settings
and clean-upgrade paths were hardware-validated; RC5 additionally packages the
LuCI keep rule and Argon ROM default for its RC5-to-RC5 validation path.

## Hardware status

### Confirmed

- S25FL128S1 dedicated 256-byte page-size fix and clean JFFS2 first/second
  boot behavior
- Recovery format, firmware boundary protection, marker, and FF padding
- LAN1/LAN2 mapping, WAN P4 configuration, and real-upstream WAN connectivity
- 2.4 GHz and MT7662 5 GHz operation, including VHT80
- LuCI, Chinese language default, Argon/Bootstrap themes, and the public Wi-Fi
  defaults
- `r18-net-rescue` retained for manual use and disabled from automatic start

### Deferred

- **LEDs:** GPIO number, polarity, and chassis wiring are not all confirmed.
- **Reset:** GPIO43 is a candidate, but its electrical polarity is unknown.
- **WPS:** the runtime GPIO is unknown; OpenWrt runtime WPS is not enabled.

No `gpio-keys` or `gpio-leds` node is added until those electrical mappings are
verified. The separate bootloader WPS/TFTP recovery procedure is unaffected.

## Tools

Run `r18-healthcheck` over SSH or from LuCI's terminal for read-only
diagnostics. It checks SPI NOR identity and page size, JFFS2 messages, network,
Wi-Fi, and rescue-service state. It does not write MTD, alter SPI NOR,
restart networking, or reboot the router.

## Build

The GitHub Actions workflow builds OpenWrt 25.12.5 / Linux 6.12.94 and verifies
the Stage 2.4 SPI NOR patch, sysupgrade metadata, final rootfs defaults,
recovery structure, checksums, and artifacts. Compiler and download caches are
used without caching build output directories.

## Release

**v0.4.0-rc5** is a Release Candidate. Its published build identity is:

- Stage 4 / Release Candidate
- Argon ROM default; Argon and Bootstrap installed
- S25FL128S1 page-size fix: 256 bytes
- Network rescue autostart: disabled

## Known issues

- LED integration is deferred pending confirmed GPIO, polarity, and wiring.
- Reset-button integration is deferred pending GPIO43 polarity confirmation.
- Runtime WPS integration is deferred pending GPIO identification.

## Roadmap

Stage 5 focuses on:

- LED adaptation after electrical verification
- Reset-button evaluation
- Additional packages
- Boot-time optimization
