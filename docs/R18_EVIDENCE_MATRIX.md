# Meizu R18 evidence matrix — Stage 2

No real MAC values are recorded in this repository.

| Item | Status | Evidence / implementation consequence |
|---|---|---|
| MT7628A SoC | CONFIRMED | Live hardware; target is `ramips/mt76x8`. |
| MIPS 24KEc / ~580 MHz | CONFIRMED | Live hardware. |
| 128 MiB DDR2 (Linux MemTotal ~126380 kB) | CONFIRMED | Live Linux report. |
| S25FL128P, 16 MiB, 64 KiB erase | CONFIRMED | Live MTD/SPI evidence. |
| Bootloader `0x000000 + 0x030000` | CONFIRMED | Live MTD; DTS read-only. |
| Config `0x030000 + 0x010000` | CONFIRMED | Live MTD; DTS read-only. |
| Factory `0x040000 + 0x010000` | CONFIRMED | Live MTD; DTS read-only nvmem provider. |
| Firmware `0x050000 + 0xF00000` | CONFIRMED | Fixed Stage 2 layout, ending at storage. |
| Storage `0xF50000 + 0x0B0000` | CONFIRMED | Live MTD; DTS read-only and excluded from firmware. |
| WAN P4 | CONFIRMED | Physical insertion test and board source. |
| LAN1 P1 | CONFIRMED | Physical insertion test and board source. |
| LAN2 P3 | CONFIRMED | Physical insertion test and board source. |
| CPU P6 | CONFIRMED | MT7628 ESW evidence. |
| No physical LAN connectors on P0/P2 | CONFIRMED | R18 physical-port inspection; ports disabled. |
| Integrated 2.4 GHz WMAC | CONFIRMED | Live hardware. |
| Factory `+0x0000` 2.4 GHz EEPROM, ID 0x7628 | CONFIRMED | Live Factory inspection. |
| Factory `+0x0004` 2.4 GHz MAC | CONFIRMED | Live Factory inspection. |
| PCIe 5 GHz radio `14c3:7662` | CONFIRMED | Live PCI probe. |
| Factory `+0x8000` 5 GHz EEPROM, ID 0x7662 | CONFIRMED | Live Factory inspection. |
| Factory `+0x8004` 5 GHz MAC | CONFIRMED | Live Factory inspection. |
| Factory `+0x0028` Ethernet MAC source | CONFIRMED | Observed Padavan LAN behavior; used via nvmem. |
| Factory `+0xE000` third MAC exists | CONFIRMED | Factory inspection. |
| Factory `+0xE000` Ethernet purpose | UNVERIFIED | Explicitly unused in DTS. |
| MT76x2 EEPROM cell size 0x200 | STRONG INFERENCE | Current v25.12.5 MT7628/MT76x2 DTS precedent. |
| USB 2.0 EHCI / OHCI, one port | CONFIRMED | Live dmesg. |
| Reset GPIO43 | CONFIRMED (source) | MZ-R18 Padavan board source confirms pin; physical electrical behavior is not yet bench-confirmed. |
| Reset electrical polarity | UNVERIFIED | No key node until verified. |
| Power LED GPIO4 | CONFIRMED (source) | MZ-R18 Padavan board source confirms pin; physical electrical behavior is not yet bench-confirmed. |
| Power LED electrical polarity | UNVERIFIED | No LED node until verified. |
| Linux UART | CONFIRMED | `ttyS0`, 57600 8N1. |
| U-Boot real serial baud | UNVERIFIED | 115200 is only a bootloader-string inference; TTL test required. |
| U-Boot TFTP RAM boot / `bootm` availability | CONFIRMED | Bootloader analysis; use only without flash writes. |
| U-Boot TFTP RAM address and exact syntax | UNVERIFIED | Obtain with `printenv` over TTL before use. |
| Bootloader dump identity (Stage 2.5) | CONFIRMED | Two mtd0 copies, `0x30000`, MD5 `f0f49f8e2a73dc3288bab13351ba111e`; only mtd0 was read. |
| Menu 1 TFTP-to-RAM control flow | CONFIRMED | Menu mode 1 enters common downloader `0xbc001320`; no Flash-writer call is present in its immediate branch. Destination remains unverified. |
| Menu 2 TFTP-to-Flash control flow | CONFIRMED | After Y/y, mode 2 download then `0xbc008218(source, 0x50000, length)`. |
| Menu 2 erase/write/readback | CONFIRMED | Writer code aligns blocks and invokes erase/program/compare operations. |
| Menu 2 max write length | CONFIRMED | Capacity minus `0x50000`; `0xfb0000` with the confirmed 16 MiB SPI. |
| Menu 2 Storage protection | CONFIRMED absent | Allowed span can reach `0x1000000`, beyond firmware end `0xf50000`. |
| WPS + power TFTP workflow | STRONG INFERENCE | Two public R18 recovery reports; WPS branch itself is still not isolated in mtd0. |
| WPS GPIO / polarity | UNVERIFIED | Do not infer from Reset GPIO43. |
| TFTP defaults `10.10.10.123` / `10.10.10.3` / `meizu_r18.bin` | CONFIRMED (compiled default) | mtd0 offsets `0x14d75` / `0x14d89` / `0x14d9d`; runtime saved environment unverified. |
| WPS automatic Flash write | UNVERIFIED — safety decision YES-risk | Menu 2 writes Flash, but WPS-to-menu linkage remains unproven. |
| WPS erase/write range and protected partitions | UNVERIFIED | Do not substitute Menu 2 boundaries for WPS until the GPIO path is recovered. |
| WPS RAM-only OpenWrt boot | UNVERIFIED — safety decision NO | No code-proven non-writing WPS branch exists. |
