# Meizu R18 stage-1 TODO

## Confirmed

- Vendor image is a valid U-Boot legacy `uImage`, MIPS/Linux/kernel/LZMA.
- Kernel payload CRC and header CRC validate; decompression yields Linux 3.10.14.
- SquashFS 4.0/XZ starts exactly at the end of the uImage payload.
- SoC family is MediaTek/Ralink MT7628; OpenWrt target is `ramips/mt76x8`.
- No valid FDT/DTB exists in the decompressed kernel scan.
- R18-marked Padavan uImage contains MT7628 kernel support, MT7628 2.4 GHz and mt76x2/MT7612E-class 5 GHz driver packages, and USB host support.
- Original and Padavan root-device indices conflict (`mtdblock5` versus `mtdblock4`); no MTD index may be projected between layouts.

## Probable

- R18 is the Meizu router speed edition with 128 MB RAM and 16 MB serial flash (external, still unmeasured). Padavan provides high-confidence image-internal support for integrated 2.4 GHz and an MT7612E-class PCIe 5 GHz radio, but not a live hardware probe.
- R18 exposes one WAN and two LAN 100 Mbps ports.

## Unknown

- Exact flash IC, layout, factory/EEPROM offsets, MAC addresses and calibration data.
- Bootloader identity, environment, recovery path, and UART parameters.
- Exact Ethernet/switch mapping and GPIOs. Padavan rootfs and scripts are now extracted, but they do not expose R18-specific port/GPIO constants or physical flash offsets.
- Exact R18 DTS topology and image-wrapper requirements.

## Blockers

- `binwalk`, `dtc`, `unsquashfs`, `ubireader`, `7z`, and the other requested Unix analysis utilities are unavailable in this Windows workspace; no WSL distribution is installed.
- No supported Python SquashFS extractor was found (`pip index versions squashfs-tools`, `unsquashfs`, `pysquashfs`, `squashfs`, and `squashfs-reader` all returned no matching distribution).
- The supplied file is an OTA image, not a physical flash dump.

## Next Steps

1. Obtain a known-good, read-only full SPI flash dump plus UART boot log.
2. Capture read-only runtime `/proc/mtd`, `/proc/cmdline`, `dmesg`, memory, PCIe and switch evidence through UART.
3. Use the dump and runtime evidence to locate MAC/factory/calibration data before drafting an R18 DTS.
4. Compare against the chosen OpenWrt reference DTS; do not copy its offsets or GPIOs.
