# Meizu R18 Stage 2.1 — Ethernet default-network fix

The first R18 image booted and reported PHY link on LAN1, but did not create a
usable default LAN/WAN topology.  On MT7628, `mediatek,portmap` and
`mediatek,portdisable` are driver-level ESW settings; they do not replace the
board script that creates UCI switch VLAN roles.

`02_network` now declares the confirmed topology explicitly:

```text
P1 = lan.1 (LAN1)
P3 = lan.2 (LAN2)
P4 = wan
P6 = CPU, eth0
```

The DTS retains `portmap = <0x0a>` and `portdisable = <0x05>` only to describe
the physical ESW wiring: P1/P3 are present and P0/P2 have no connector.  This
matches the v25.12.5 MT7628 pattern used by HiWiFi HC5761A/HC5861B, while the
new UCI topology is intentionally independent of that bitmap.

LAN MAC remains the confirmed Factory `+0x28` MAC supplied by DTS.  The board
script derives WAN as LAN MAC plus one, matching the HiWiFi precedent and not
using the unverified Factory `+0xe000` value.  No Flash, Factory, WiFi EEPROM,
USB, or partition definition changed.

The image recipe now emits a metadata-free `recovery.bin`; CI copies it to
`meizu_r18.bin` as a static candidate.  This is not a recommendation or
validated route for WPS/TFTP recovery; Stage 2.5 continues to prohibit that
untested persistent-write path.

## 2.4 GHz debug access

On first boot only, `99-r18-wifi-test` finds the generated 2.4 GHz radio,
enables it, and creates `R18-OpenWrt-Test` as a WPA2-PSK AP on `lan`/`br-lan`.
It does not enable the 5 GHz radio. This historical debug-AP policy was
superseded by Stage 4 RC4, which enables both production SSIDs with the public
factory Wi-Fi password documented in [INSTALL.md](INSTALL.md). LAN remains
`192.168.1.1` from the standard default network configuration.
