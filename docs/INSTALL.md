# Installation

Use only the generated `meizu_r18.bin` recovery candidate for WPS/TFTP first
install or recovery. Do not use raw `mtd` commands.

1. Verify the artifact SHA256 from `SHA256SUMS`.
2. Install and start Tftpd32/Tftpd64 on Windows.
3. Configure the Windows Ethernet adapter as `10.10.10.3/24`, with no gateway.
4. Put `meizu_r18.bin` in the TFTP root directory.
5. Connect the computer to **LAN1 / P1**.
6. Power the router off.
7. Hold WPS, power it on, then release WPS after approximately six seconds.
8. The recovery client uses `10.10.10.123`; wait for the TFTP transfer.
9. After transfer completes, continue waiting for flash programming and the
   first OpenWrt boot. Do not disconnect power during this period.

The recovery image is exactly 15 MiB and occupies only the Firmware region.
It is not a raw whole-flash image and must not be substituted with an unknown
binary.

Do not erase, overwrite, or otherwise modify Factory, Config, Storage, or the
bootloader. Preserve an original full-flash backup offline before experimenting.
