# Meizu R18 Stage 3 — Functional Complete

Stage 3 promotes the tested Stage 2.5 baseline to a normal dual-band OpenWrt
router configuration without changing the SPI-NOR fix, flash boundaries,
recovery format, or startup sequencing.

## Default services

- LAN is the confirmed P1/P3 bridge on `eth0.1`, with `192.168.1.1/24` and
  the normal OpenWrt DHCP server.
- WAN is confirmed P4 on `eth0.2`, using the normal DHCP/DHCPv6 client. The
  resulting LuCI configuration remains suitable for changing WAN to PPPoE.
- First boot replaces generated wireless placeholder interfaces with two LAN
  APs: `R18-OpenWrt` on 2.4 GHz and `R18-OpenWrt-5G` on the MT7662 5 GHz PHY.
  The common WPA2-PSK/CCMP key comes only from CI secret injection and is
  deleted from the target after first boot.
- Hostname is `Meizu-R18`; LuCI defaults to Simplified Chinese. No timezone is
  forced.

## Confirmed calibration sources

- 2.4 GHz: Factory `+0x0000` EEPROM and `+0x0004` MAC.
- 5 GHz MT7662: Factory `+0x8000` EEPROM and `+0x8004` MAC.
- Ethernet: Factory `+0x0028`; WAN remains LAN MAC plus one. Factory
  `+0xe000` remains intentionally unused.

`kmod-mt76x2` is the v25.12.5 package containing `mt76x2e.ko`; the build
configuration explicitly selects its MT76 core/common dependency chain.

## Intentionally unresolved hardware

No DTS button or LED nodes are added in this stage. Reset GPIO43 and Power LED
GPIO4 are source-level candidates, but their electrical polarities are not
bench-confirmed. WPS GPIO and polarity are unknown. Implementing any of them
would be guesswork and could create a false reset or LED state.

## Required hardware validation

CI proves that the DTS, packages, defaults, recovery format, and rootfs files
are present. It cannot prove RF operation. After a normal boot, verify both
PHYs with `iw phy`, `iw dev`, and `dmesg | grep -Ei 'mt76|mt76x2|pci'`; then
confirm both APs can join LAN and test P4 WAN DHCP/NAT/firewall operation.
