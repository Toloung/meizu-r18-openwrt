# Recovery image

`meizu_r18.bin` is byte-identical to `squashfs-recovery.bin`. It is a WPS/TFTP
recovery image for the firmware region only:

- firmware range: `0x050000-0xF50000`
- exact image size: `0xF00000` / 15 MiB
- storage starts at: `0xF50000`

Before use, compare its SHA256 with `SHA256SUMS`. The build verifier checks the
uImage header, SquashFS, the computed `rootfs_data` boundary, and the complete
tail of the image.

At the aligned `rootfs_data` start the image contains the JFFS2 end marker
`DE AD C0 DE`. Every byte after the marker through the image end is `FF`. This
prevents stale recovery-tail data from being carried into a first boot.

Use the WPS/TFTP method described in [INSTALL.md](INSTALL.md). Do not interrupt
the transfer or flash programming, and do not use recovery to bypass normal
upgrade testing.

Keep an original full-flash backup private and offline. It may contain Factory
calibration, MAC addresses, and other device-specific data; it must never be
committed to this repository.
