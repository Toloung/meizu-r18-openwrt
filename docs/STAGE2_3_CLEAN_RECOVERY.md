# Meizu R18 Stage 2.3 — Clean Recovery / JFFS2 Residual Test

## Purpose and scope

Stage 2.3 tests a high-confidence **hypothesis**, not a proven root cause:
the compact Stage 2.2 WPS/TFTP image may leave old data in the unwritten tail
of the `firmware` partition. On a later boot, that data could be scanned as
`rootfs_data`, explaining the observed JFFS2 magic and CRC errors near the end
of the partition.

No Ethernet topology, Factory EEPROM location, MAC rule, Wi-Fi EEPROM, USB,
or Flash partition has changed in this stage. The delayed R18 network fallback
is retained, but now waits 180 seconds so a clean-recovery boot can be observed
without the fallback immediately masking its result.

## Exact recovery boundary

| Item | Value |
|---|---:|
| Firmware physical start | `0x00050000` |
| Firmware size / recovery file size | `0x00f00000` (15,728,640 bytes) |
| Firmware physical end (exclusive) | `0x00f50000` |
| Storage physical start | `0x00f50000` |
| Storage size | `0x000b0000` |

The Stage 2.3 `squashfs-recovery.bin` is exactly `0x00f00000` bytes and
`meizu_r18.bin` is an exact byte-for-byte copy. `squashfs-sysupgrade.bin`
remains compact and is deliberately not padded to the firmware partition size.

The recovery layout is:

```text
legacy uImage | SquashFS | erase-block alignment | DE AD C0 DE | FF ... FF
                                                         ^ rootfs_data
0x000000 -------------------------------------------------------- 0x00f00000
```

The JFFS2 EOF marker remains at the erase-aligned `rootfs_data` start; it is
not the final four bytes of the file. Every byte after the marker through the
firmware boundary is explicitly `0xff`.

## Padding implementation and CI verification

OpenWrt v25.12.5 `Build/pad-to` calls `dd ... conv=sync`, which uses zero-byte
padding. It is therefore not suitable for this recovery image. The R18-only
`Build/r18-pad-to-ff` helper retains the compact `pad-rootfs` output, then
creates exactly the remaining number of bytes from `/dev/zero` and translates
them from `0x00` to `0xff`; it rejects an oversize image and rechecks the final
size.

`scripts/verify_r18_recovery.py` is run by CI on `squashfs-recovery.bin`. It
parses the legacy uImage header, reads `ih_size`, requires SquashFS `hsqs` at
the kernel end, reads the little-endian SquashFS `bytes_used` field, derives
the 64 KiB-aligned `rootfs_data` offset, checks `DE AD C0 DE` there, and scans
the entire remaining file byte-for-byte for `0xff`. It also verifies that the
physical recovery end equals the Storage start. CI separately asserts that
the sysupgrade output remains smaller than `0x00f00000` and that
`meizu_r18.bin` is exactly equal to the recovery image.

## U-Boot recovery boundary

The existing static analysis remains relevant:

- Menu 2 calls the Flash writer with destination `0x50000` and the downloaded
  length.
- The current 16 MiB capacity check allows at most `0x00fb0000` bytes, so a
  `0x00f00000` image is below that length limit.
- The writer erases to an erase-block boundary, writes, and readback-compares.
- The writer has no confirmed awareness of the Linux `firmware` / `storage`
  split: an input larger than `0x00f00000` can reach Storage.

Consequently, the Stage 2.3 exact-size check is the protection against
overwriting Storage; it is not evidence that every WPS/TFTP path applies the
same boundary. The WPS control flow and its relationship to Menu 2 remain
unverified. **Full-size recovery still requires hardware validation.** No
flash operation is authorised by this stage.

## Test interpretation

During Stage 2.3 testing, LAN or the 2.4 GHz debug AP becoming available
before the 180-second rescue begins is evidence consistent with the clean
recovery removing the reboot-time residual-data condition. It is not, by
itself, proof of causality. If fallback recovery is needed, inspect
`/root/r18-boot-debug.log` and retain the serial boot log for comparison.
