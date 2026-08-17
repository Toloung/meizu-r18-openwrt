# Hardware notes

## Confirmed platform

- SoC: MediaTek MT7628AN
- RAM: 128 MiB
- NOR: 16 MiB Spansion S25FL128S1
- JEDEC: `01 20 18 4d 01 80`
- 2.4 GHz: MT7628 integrated radio
- 5 GHz: MT7662 PCIe / `mt76x2e`

The Wi-Fi calibration and MAC sources are deliberately scoped to confirmed
Factory locations:

| Radio | EEPROM | MAC |
| --- | --- | --- |
| 2.4 GHz | Factory + `0x0000` | Factory + `0x0004` |
| 5 GHz | Factory + `0x8000` | Factory + `0x8004` |

No personal MAC addresses are recorded here.

## SPI-NOR page programming fix

Linux initially interpreted this S25FL128S1 variant as having 512-byte pages.
On R18 hardware, JFFS2 LZMA nodes crossing a 256-byte program boundary were
corrupted: the observed bad nodes all crossed that boundary.

The R18 kernel patch adds a dedicated post-BFPT fixup only to the exact
`s25fl128s1` JEDEC entry above:

```c
nor->params->page_size = 256;
```

It does not change other NOR models or platforms. Runtime debugfs now reports
page size 256. JFFS2 first boot, second boot, keep-settings sysupgrade, and
clean sysupgrade all recorded zero `Magic bitmask`, `CRC failed`, `wrong data
CRC`, and `Truncating ino` counters.

## Ethernet mapping

- P1 = LAN1
- P3 = LAN2
- P4 = WAN
- P6 = CPU / `eth0`

LAN1 and LAN2 were physically validated. WAN configuration is validated, but
the P4 upstream DHCP / Internet physical test remains pending.

## Deferred GPIO work

Reset, WPS, and LED GPIO electrical mappings are not formally established and
are intentionally not claimed by this target.
