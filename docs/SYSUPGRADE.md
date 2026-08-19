# Sysupgrade

Use `*-squashfs-sysupgrade.bin` for an upgrade from a running OpenWrt system.
It is compact, carries OpenWrt metadata, and identifies `meizu,r18`.

Upload and validate first:

```sh
scp firmware.bin root@192.168.1.1:/tmp/
sysupgrade -T /tmp/firmware.bin
```

For a normal upgrade that retains configuration:

```sh
sysupgrade /tmp/firmware.bin
```

For a clean upgrade:

```sh
sysupgrade -n /tmp/firmware.bin
```

`-n` erases the current OpenWrt configuration and generates a new overlay. Back
up configuration first with `sysupgrade -b backup.tar.gz` and keep that archive
private.

Never use `-F` unless there is a specific, understood development reason. Do
not use a recovery image as a sysupgrade image.

The Stage 3 to Stage 3.5 keep-settings path and the Stage 3.5 clean sysupgrade
path were hardware-validated. A keep-settings upgrade preserves an existing
LuCI theme choice; a clean install uses the RC5 ROM Argon default.
