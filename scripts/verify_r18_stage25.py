#!/usr/bin/env python3
"""Verify Stage 2.5 R18 rescue, health-check, and SPI-NOR regressions."""

from __future__ import annotations

import argparse
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from verify_r18_stage24 import (
    VerificationError,
    read_text,
    require,
    verify_generated_patch,
    verify_kernel_patch_application,
    verify_patched_source,
    verify_stage_patch,
)


RESCUE = "target/linux/ramips/mt76x8/base-files/etc/init.d/r18-net-rescue"
RESCUE_DISABLE = "target/linux/ramips/mt76x8/base-files/etc/uci-defaults/98-r18-net-rescue-disable"
HEALTHCHECK = "target/linux/ramips/mt76x8/base-files/usr/sbin/r18-healthcheck"
BUILD_INFO = "target/linux/ramips/mt76x8/base-files/etc/r18-build-info"


def fail(message: str) -> None:
    raise VerificationError(message)


def passed(message: str) -> None:
    print(f"[PASS] {message}")


def section_for_new_file(stage_patch: str, path: str) -> str:
    header = f"diff --git a/{path} b/{path}"
    start = stage_patch.find(header)
    require(start >= 0, f"managed Stage patch does not add {path}")
    end = stage_patch.find("\ndiff --git ", start + len(header))
    return stage_patch[start:] if end < 0 else stage_patch[start:end]


def verify_stage25_source(stage_patch: Path, generated_patch: Path) -> None:
    text = read_text(stage_patch, "managed Stage patch")
    verify_stage_patch(stage_patch)
    verify_generated_patch(generated_patch)

    rescue = section_for_new_file(text, RESCUE)
    require("new file mode 100755" in rescue, "r18-net-rescue is not executable")
    require("START=99" in rescue and "USE_PROCD=1" in rescue, "r18-net-rescue init metadata changed")
    require("start_service()" in rescue, "r18-net-rescue manual start implementation is missing")
    require(
        "procd_set_param command /usr/sbin/r18-net-rescue-worker" in rescue,
        "r18-net-rescue no longer starts its retained manual worker",
    )
    passed("r18-net-rescue script and manual start implementation are retained")

    disable = section_for_new_file(text, RESCUE_DISABLE)
    require("/etc/init.d/r18-net-rescue disable" in disable, "default rescue disable hook is missing")
    require("before its S99 phase" in disable, "rescue disable hook does not document boot ordering")
    require("S99r18-net-rescue" not in text, "Stage patch must not generate an S99 rescue symlink")
    passed("default rescue auto-start is disabled by the first-boot native init hook")

    health = section_for_new_file(text, HEALTHCHECK)
    require("new file mode 100755" in health, "r18-healthcheck is not executable")
    for required in (
        "Meizu R18 Health Check",
        "s25fl128s1",
        "01 20 18 4d 01 80",
        "page_size",
        "Magic bitmask",
        "wrong data CRC",
        "Truncating ino",
        "Auto start: disabled",
        "Manual service available: yes",
        "exit 1",
    ):
        require(required in health, f"r18-healthcheck lacks required check: {required}")
    for prohibited in ("reboot", "firstboot", "jffs2reset", "mtd erase", "mtd write", "network restart", "wifi reload", "uci set"):
        require(prohibited not in health, f"r18-healthcheck contains prohibited state-changing command: {prohibited}")
    passed("r18-healthcheck is executable and contains only read-only diagnostics")

    build_info = section_for_new_file(text, BUILD_INFO)
    for required in (
        "Stage=2.5",
        "OpenWrt=25.12.5",
        "Kernel=6.12.94",
        "SPI_NOR=s25fl128s1",
        "SPI_NOR_JEDEC=01 20 18 4d 01 80",
        "SPI_NOR_PAGE_SIZE_FIX=256",
        "NET_RESCUE_AUTOSTART=disabled",
    ):
        require(required in build_info, f"/etc/r18-build-info lacks {required}")
    passed("Stage 2.5 image build identity is installed")

    require("DEVICE_VARIANT := Stage 2.5 Disable Automatic Network Rescue" in text, "R18 image variant is not Stage 2.5")
    passed("Stage 2.5 image identity is selected")


def verify_rootfs(rootfs: Path) -> None:
    require(rootfs.is_dir(), f"extracted R18 rootfs is missing: {rootfs}")
    health = rootfs / "usr/sbin/r18-healthcheck"
    rescue = rootfs / "etc/init.d/r18-net-rescue"
    disable = rootfs / "etc/uci-defaults/98-r18-net-rescue-disable"
    build_info = rootfs / "etc/r18-build-info"
    for path in (health, rescue, disable, build_info):
        require(path.is_file(), f"Stage 2.5 rootfs misses {path.relative_to(rootfs)}")
    require(health.stat().st_mode & 0o111, "Stage 2.5 r18-healthcheck is not executable in rootfs")
    require(rescue.stat().st_mode & 0o111, "Stage 2.5 r18-net-rescue is not executable in rootfs")
    require(
        not (rootfs / "etc/rc.d/S99r18-net-rescue").exists(),
        "Stage 2.5 rootfs unexpectedly contains automatic S99 r18-net-rescue link",
    )
    passed("Stage 2.5 rootfs retains manual rescue and contains no S99 auto-start link")


def verify_recovery_rootfs(recovery: Path) -> None:
    require(recovery.is_file(), f"R18 recovery image is missing: {recovery}")
    unsquashfs = shutil.which("unsquashfs")
    require(unsquashfs is not None, "unsquashfs is required for Stage 2.5 recovery rootfs verification")
    with recovery.open("rb") as image:
        header = image.read(64)
        require(len(header) == 64, "R18 recovery is shorter than its uImage header")
        kernel_size = struct.unpack_from(">I", header, 12)[0]
        squashfs_start = 64 + kernel_size
        image.seek(squashfs_start)
        superblock = image.read(48)
        require(superblock[:4] == b"hsqs", "R18 recovery has no SquashFS at its uImage boundary")
        squashfs_size = struct.unpack_from("<Q", superblock, 40)[0]
        require(squashfs_size > 0, "R18 recovery SquashFS has zero bytes_used")
        image.seek(squashfs_start)
        squashfs = image.read(squashfs_size)
        require(len(squashfs) == squashfs_size, "R18 recovery SquashFS is truncated")

    with tempfile.TemporaryDirectory(prefix="r18-stage25-rootfs-") as temporary:
        temporary_path = Path(temporary)
        squashfs_path = temporary_path / "rootfs.squashfs"
        rootfs = temporary_path / "rootfs"
        squashfs_path.write_bytes(squashfs)
        result = subprocess.run([unsquashfs, "-d", str(rootfs), str(squashfs_path)], text=True, capture_output=True, check=False)
        if result.returncode:
            fail("unsquashfs failed: " + (result.stdout + result.stderr).strip())
        verify_rootfs(rootfs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-patch", type=Path, required=True)
    parser.add_argument("--generated-patch", type=Path, required=True)
    parser.add_argument("--kernel-tar", type=Path)
    parser.add_argument("--spansion", type=Path)
    parser.add_argument("--recovery", type=Path)
    args = parser.parse_args()

    try:
        verify_stage25_source(args.stage_patch, args.generated_patch)
        if args.kernel_tar:
            verify_kernel_patch_application(args.generated_patch, args.kernel_tar)
        if args.spansion:
            verify_patched_source(read_text(args.spansion, "prepared spansion.c"))
        if args.recovery:
            verify_recovery_rootfs(args.recovery)
    except (OSError, tarfile.TarError, VerificationError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Stage 2.5 source verification: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
