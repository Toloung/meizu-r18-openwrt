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

## Buttons and LEDs

Stage 4.1 completed non-destructive runtime, source, and passive physical
observation. No GPIO was driven, exported, or read directly.

- **WPS:** runtime GPIO and polarity are unknown. The Padavan MZ-R18 profile
  leaves `BOARD_GPIO_BTN_WPS` undefined, and a runtime short press produced no
  kernel, ubus, hotplug, input, or hostapd event. OpenWrt runtime WPS is
  deferred; the separate bootloader WPS/TFTP recovery procedure is unchanged.
- **Reset:** Padavan source identifies GPIO43, but does not state polarity.
  No `gpio-keys` binding is included.
- **Power LED:** Padavan source identifies GPIO4, but does not state polarity.
  No `gpio-leds` binding is included.
- **MT7628 LED-function pads:** GPIO39=P4, GPIO40=P3, GPIO41=P2, GPIO42=P1,
  GPIO43=P0, GPIO44=WLAN. Physical chassis wiring is unverified; passive LAN,
  WAN, and Wi-Fi observation did not establish a mapping.

No GPIO button or LED nodes are included because electrical polarity and
physical wiring are not sufficiently verified. See
[GPIO-DISCOVERY.md](GPIO-DISCOVERY.md) for the evidence record.
