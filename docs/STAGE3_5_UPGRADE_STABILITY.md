# Meizu R18 Stage 3.5 — Upgrade and Stability Validation

Stage 3.5 fixes only the read-only healthcheck parser and prepares the normal
OpenWrt sysupgrade path. It does not change the SPI-NOR fix, flash layout,
recovery image, Ethernet topology, radio calibration/MAC cells, default SSIDs,
rescue policy, or preinit/network startup ordering.

## Sysupgrade safety contract

`squashfs-sysupgrade.bin` remains compact and is smaller than the 15 MiB
firmware partition. It now carries standard OpenWrt metadata for `meizu,r18`;
MT76x8 `platform.sh` requires that metadata and sets `PART_NAME=firmware`.
Its normal path calls `default_do_upgrade`, which writes only the `firmware`
MTD partition (`0x050000-0xF50000`). It does not target bootloader, config,
factory, or storage.

The recovery image remains the distinct 15 MiB WPS/TFTP candidate with the
`DE AD C0 DE` rootfs_data marker and erased-FF suffix.

## Hardware validation sequence (not performed by CI)

1. Record the Stage 3 running configuration and healthcheck output.
2. Test `sysupgrade -T` with the Stage 3.5 sysupgrade image first; verify the
   image metadata identifies `meizu,r18`.
3. Perform one keep-settings upgrade, then verify page size 256, JFFS2
   counters, LAN/WAN configuration, both SSIDs, and no rescue autostart.
4. Perform one no-keep-settings upgrade only after the keep-settings path has
   passed; rerun the same checks.
5. Perform second and third boot checks, plus P1 LAN and P4 upstream DHCP
   physical tests.
6. Keep the verified recovery image available throughout. Do not use recovery
   or any erase/reset operation as a substitute for an upgrade test.
