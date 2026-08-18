# Meizu R18 OpenWrt 25.12.5 — RC1

This draft release is based on OpenWrt 25.12.5 and Linux 6.12.94.

## Verified on hardware

- WPS/TFTP recovery and the 15 MiB recovery image contract
- Settings-preserved and clean sysupgrade
- LAN1 (P1) and LAN2 (P3)
- 2.4 GHz and 5 GHz MT7662 / mt76x2e operation
- LuCI, Chinese defaults, and read-only healthcheck
- S25FL128S1 256-byte SPI-NOR page-program fix
- JFFS2 first/second boot and upgrade persistence

## LuCI themes

- Bootstrap is the clean-install default.
- Argon remains a selectable alternative.
- Existing theme selection is preserved by a settings-retained sysupgrade.

## Pending validation

- WAN P4 actual upstream DHCP / Internet physical validation
- Final Reset/WPS/LED GPIO mapping

This is a draft release candidate, not a published stable release.
