# Meizu R18 Stage 2 first-boot test plan

## Safety boundary

This stage permits only a U-Boot TFTP transfer to RAM followed by `bootm`.
Do not run `erase`, `sf erase`, `mtd`, `mtd write`, `sysupgrade`, `cp.linux`,
`spi write`, or any command that changes flash, Bootloader, Factory, Config,
or Storage. Keep a verified original SPI backup offline.

**The initramfs image is the only boot artifact permitted for the first test.**
Any `sysupgrade.bin` produced alongside it is **DO NOT FLASH / NOT FOR
FLASHING YET** and is retained only for static image-format inspection.

## Stage 2.5 WPS-recovery exclusion

Do not use WPS + power recovery for this plan. The mtd0 analysis proves that
menu 2 is a persistent erase/write path from `0x50000`, with an accepted
length large enough to reach Storage; the WPS-to-menu linkage is still
unproven. It is therefore outside the permitted RAM-only route. See
`docs/R18_RECOVERY_MAP.md`.

## Before powering the board

1. Attach a 3.3 V TTL adapter with a common ground; do not connect a 5 V UART.
2. Start at 115200 8N1 to probe U-Boot, but treat this only as a probable rate.
   If unreadable, test documented rates conservatively. Linux is confirmed at
   57600 8N1.
3. Connect the intended physical Ethernet port to an isolated TFTP host.
   Record which connector has link; do not assume the U-Boot network port.
4. Place only `*meizu*r18*initramfs-kernel.bin` in the TFTP root and record its
   SHA256 from the build output.

## U-Boot RAM-only sequence

1. Interrupt autoboot and capture the complete banner and `printenv` output.
   Record the actual baud, `ipaddr`, `serverip`, TFTP command, `loadaddr`, and
   boot command. Do not save the environment.
2. If networking parameters are missing, set only volatile RAM environment
   values for the current session. Do not issue `saveenv`.
3. Use the bootloader's displayed TFTP command to load the initramfs image to
   its reported safe RAM load address. Confirm transfer size and checksum.
4. Run the bootloader's `bootm` form against that RAM address only. Do not use
   a flash address or a flash-copy command.
5. Capture the entire OpenWrt console log through the first login prompt.

## In-initramfs validation

Run read-only diagnostics and save their serial output:

```sh
cat /proc/cmdline
cat /proc/mtd
dmesg
logread
ip link
swconfig dev switch0 show
ethtool eth0
lspci -nn
iw dev
lsusb
```

Perform one-at-a-time physical link checks on WAN, LAN1, LAN2 and compare with
P4, P1, P3. Confirm both radios have non-fallback calibration and distinct
Factory-derived MACs. Do not alter flash after the test; power-cycle returns
the board to its original firmware.

## Required evidence before Stage 3

- Full U-Boot serial log, exact baud, and the confirmed RAM-only command log.
- Kernel boot log and MTD table matching protected-partition intent.
- Per-port VLAN/link observations proving WAN=P4, LAN1=P1, LAN2=P3.
- `lspci`, wireless calibration, USB EHCI/OHCI, and MAC-source observations.
- GPIO43/GPIO4 electrical polarity tests, performed without write operations.
