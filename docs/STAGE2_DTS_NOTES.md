# Meizu R18 Stage 2 DTS notes

Target baseline: OpenWrt `v25.12.5`, `ramips/mt76x8`. This board support is
for an initramfs RAM boot only. A generated sysupgrade file is a static build
artifact, **not a flashing authorization**.

## Design decisions

- The DTS uses the current fixed `nvmem-layout` binding. The Factory partition
  is read-only; it exposes 2.4 GHz EEPROM at `+0x0000`, 2.4 GHz MAC at
  `+0x0004`, Ethernet MAC at `+0x0028`, 5 GHz EEPROM at `+0x8000`, and 5 GHz
  MAC at `+0x8004`.
- `wmac` consumes the `+0x0000` EEPROM and `+0x0004` MAC. The PCIe radio uses
  the `mediatek,mt76` binding and consumes `+0x8000` / `+0x8004`; this matches
  the live `14c3:7662` identification and selects `kmod-mt76x2`.
- Ethernet consumes Factory `+0x0028`, matching the observed Padavan LAN MAC
  source. No MAC value is embedded in source.
- MT7628's legacy ESW driver still uses the current `mediatek,portmap` bitmap.
  `0x0a` means LAN=P1|P3. P4 is deliberately outside the LAN bitmap (WAN).
  P0 and P2 are disabled because R18 has no connectors for them; P6 is the CPU
  port and is not represented in the six-bit LAN bitmap.
- The fixed NOR layout leaves bootloader, config, factory, and storage outside
  firmware. Firmware is `0x050000 + 0xF00000`; storage is retained at
  `0xF50000 + 0x0B0000`.
- USB host nodes are supplied by `mt7628an.dtsi`; `kmod-usb2` and
  `kmod-usb-ohci` are included. No USB-power GPIO is claimed.

## Deliberately omitted pending bench verification

- Reset GPIO43 exists in the MZ-R18 Padavan board source, but its polarity is
  unverified, so no `gpio-keys` node is created.
- Power LED GPIO4 exists in that source, but its polarity is unverified, so no
  LED node or boot-status alias is created.
- Factory `+0xE000` contains a third consecutive manufacturer MAC, but its
  Ethernet purpose is unverified. It is intentionally not exported or used.
- U-Boot's actual serial baud, TFTP command syntax, RAM load address, and
  `bootm` argument form require an attached-TTL capture. Linux `ttyS0` at
  57600 is confirmed and is the DTS console setting.

## Strong-inference implementation details

`mt76x2` boards in this OpenWrt release use a 0x200-byte nvmem cell for the
MT76x2 PCI EEPROM. The R18 cell at `Factory +0x8000` uses that proven driver
shape; the placement and EEPROM ID `0x7662` are confirmed, while a full
byte-for-byte calibration length has not yet been independently measured.

The DTS uses a deliberately conservative 12 MHz SPI rate. The R18 maximum SPI
clock is **UNVERIFIED**; measure it before raising this value in any later
stage.
