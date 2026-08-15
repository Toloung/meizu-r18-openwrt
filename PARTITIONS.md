# Meizu R18 flash / MTD partition status (stage 1)

## What is actually known

This file is an OTA-style vendor image, not a full raw flash dump. It begins with a kernel uImage at offset `0x00000000`; it contains no bootloader, factory partition, MTD table, or flash JEDEC identification. Therefore offsets in this file must **not** be projected onto physical flash addresses.

The kernel's embedded default command line contains `root=/dev/mtdblock5`. This confirms that the vendor system mounts its root filesystem through MTD index 5 at boot, but does not reveal the names, offsets, sizes, or preceding partition boundaries.

| Partition | Offset | Size | Function | Writable? | Risk | Evidence |
| -- | --: | --: | -- | -- | -- | -- |
| mtd0–mtd4 | UNKNOWN | UNKNOWN | UNKNOWN | NO | Critical | Only `root=/dev/mtdblock5` is embedded in the kernel. |
| mtd5 | UNKNOWN | UNKNOWN | Vendor root filesystem mount target | NO | Critical | Kernel string; not an offset declaration. |
| bootloader / config / factory / EEPROM / RF calibration / MAC | UNKNOWN | UNKNOWN | May exist in mtd0–mtd4 or elsewhere | **NEVER write** | Critical | Absent from this OTA image. |

## Validated image-internal components (not MTD partitions)

| Component | Image offset | Size | Validation |
| -- | --: | --: | -- |
| U-Boot legacy image header | `0x00000000` | `0x40` | Magic and header CRC valid |
| LZMA-compressed Linux kernel | `0x00000040` | `0x149125` | uImage payload CRC valid; decompression succeeds |
| SquashFS 4.0 rootfs | `0x00149165` | `0x7454f0` | Superblock structurally parsed; XZ compression ID 4 |
| Trailing vendor/padding data | `0x0088e655`–`0x008c0224` | `0x31bd0` | Uninterpreted; not a partition |

The exact final trailing length and hashes are preserved in `analysis/reports/firmware-layout.md` and `analysis/reports/uimage-and-squashfs.txt`.

## Required next evidence

1. Read-only complete SPI flash dump and its hash.
2. UART boot log including the kernel's `Creating ... MTD partitions` output and `/proc/mtd`.
3. Read-only copies of `/proc/cmdline`, `/proc/mtd`, `/sys/class/mtd/*`, and `dmesg`.
4. Only then transcribe a partition table and identify factory/calibration locations.
