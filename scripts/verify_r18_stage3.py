#!/usr/bin/env python3
"""Verify the Stage 4 Meizu R18 release-candidate image contract."""

from __future__ import annotations

import argparse
import shlex
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


DT = "target/linux/ramips/dts/mt7628an_meizu_r18.dts"
NETWORK = "target/linux/ramips/mt76x8/base-files/etc/board.d/02_network"
RESCUE = "target/linux/ramips/mt76x8/base-files/etc/init.d/r18-net-rescue"
RESCUE_DISABLE = "target/linux/ramips/mt76x8/base-files/etc/uci-defaults/98-r18-net-rescue-disable"
DEFAULTS = "target/linux/ramips/mt76x8/base-files/etc/uci-defaults/97-r18-stage3-defaults"
KEEP_LUCI = "target/linux/ramips/mt76x8/base-files/lib/upgrade/keep.d/r18-luci"
WIFI_DEFAULTS = "target/linux/ramips/mt76x8/base-files/etc/uci-defaults/99-r18-wifi-defaults"
HEALTHCHECK = "target/linux/ramips/mt76x8/base-files/usr/sbin/r18-healthcheck"
BUILD_INFO = "target/linux/ramips/mt76x8/base-files/etc/r18-build-info"
IMAGE_MK = "target/linux/ramips/image/mt76x8.mk"
UPGRADE_PLATFORM = "target/linux/ramips/mt76x8/base-files/lib/upgrade/platform.sh"
ARGON_DEPENDS = "+USE_APK:wget-any +!USE_APK:wget +jsonfilter"
ROOTFS_PATHS = (
    "etc/init.d/r18-net-rescue",
    "etc/uci-defaults",
    "lib/upgrade/keep.d/r18-luci",
    "usr/sbin/r18-healthcheck",
    "etc/r18-build-info",
    "etc/config/luci",
    "etc/rc.d",
    "www/luci-static/bootstrap",
    "www/luci-static/argon",
)


def passed(message: str) -> None:
    print(f"[PASS] {message}")


def fail(message: str) -> None:
    raise VerificationError(message)


def section_for(stage_patch: str, path: str) -> str:
    header = f"diff --git a/{path} b/{path}"
    start = stage_patch.find(header)
    require(start >= 0, f"managed Stage patch does not add {path}")
    end = stage_patch.find("\ndiff --git ", start + len(header))
    return stage_patch[start:] if end < 0 else stage_patch[start:end]


def require_all(text: str, items: tuple[str, ...], label: str) -> None:
    for item in items:
        require(item in text, f"{label} lacks required content: {item}")


def require_exact_line(text: str, expected: str, label: str) -> None:
    require(expected in text.splitlines(), f"{label} is missing or incorrect (expected {expected})")


def uci_option_value(config: str, section_type: str, section_name: str, option_name: str) -> str | None:
    """Return one UCI option value, accepting quoted or canonical serialized syntax."""
    in_section = False
    for raw_line in config.splitlines():
        tokens = shlex.split(raw_line, comments=True)
        if not tokens:
            continue
        if tokens[0] == "config":
            in_section = len(tokens) >= 3 and tokens[1] == section_type and tokens[2] == section_name
            continue
        if in_section and tokens[0] == "option" and len(tokens) >= 3 and tokens[1] == option_name:
            return " ".join(tokens[2:])
    return None


def verify_source(
    stage_patch: Path,
    generated_patch: Path,
    config: Path,
    upgrade_platform: Path,
    theme_lock: Path,
    argon_package: Path,
) -> None:
    text = read_text(stage_patch, "managed Stage patch")
    verify_stage_patch(stage_patch)
    verify_generated_patch(generated_patch)
    config_text = read_text(config, "R18 build configuration")

    require_all(
        config_text,
        (
            "CONFIG_PACKAGE_kmod-mt76=y",
            "CONFIG_PACKAGE_kmod-mt76-core=y",
            "CONFIG_PACKAGE_kmod-mt76x2-common=y",
            "CONFIG_PACKAGE_kmod-mt76x2=y",
            "CONFIG_PACKAGE_kmod-mt7603=y",
            "CONFIG_PACKAGE_luci=y",
            "CONFIG_PACKAGE_luci-app-firewall=y",
            "CONFIG_PACKAGE_luci-app-package-manager=y",
            "CONFIG_PACKAGE_luci-theme-bootstrap=y",
            "CONFIG_PACKAGE_luci-theme-argon=y",
        ),
        "R18 build configuration",
    )
    require("CONFIG_PACKAGE_luci-theme-liquid=y" not in config_text, "Liquid must not be selected")
    require("CONFIG_PACKAGE_luci-app-argon-config=y" not in config_text, "Argon Config must not be selected")
    require("CONFIG_PACKAGE_wget-nossl=y" not in config_text, "R18 must not select wget-nossl")
    passed("Stage 4 RC4 retains LuCI, Bootstrap, Argon, and the MT76/MT7662 driver chain")

    dts = section_for(text, DT)
    require_all(
        dts,
        (
            "eeprom@0 {",
            "reg = <0x0000 0x0400>;",
            "macaddr@4 {",
            "reg = <0x0004 0x0006>;",
            "macaddr@28 {",
            "reg = <0x0028 0x0006>;",
            "eeprom@8000 {",
            "reg = <0x8000 0x0200>;",
            "macaddr@8004 {",
            "reg = <0x8004 0x0006>;",
            "&wmac {",
            "<&eeprom_factory_0>, <&macaddr_factory_4>",
            "<&eeprom_factory_8000>, <&macaddr_factory_8004>",
            "ieee80211-freq-limit = <5000000 6000000>;",
        ),
        "R18 DTS",
    )
    require(
        "macaddr_factory_e000" not in dts and "eeprom@e000" not in dts and "macaddr@e000" not in dts,
        "R18 DTS must not use unconfirmed Factory +0xE000",
    )
    passed("R18 DTS retains the confirmed 2.4 GHz/5 GHz Factory EEPROM and MAC offsets")

    network = section_for(text, NETWORK)
    require('"1:lan:1" "3:lan:2" "4:wan" "6@eth0"' in network, "R18 LAN/WAN switch mapping changed")
    require("meizu,r18" in network and "wan_mac=$(macaddr_add" in network, "R18 WAN MAC +1 rule is missing")
    passed("R18 switch topology retains LAN1=P1, LAN2=P3, WAN=P4, CPU=P6")

    wifi = section_for(text, WIFI_DEFAULTS)
    require_all(
        wifi,
        (
            "psk='password'",
            "configure_ap r18_24g",
            "configure_ap r18_5g",
            "R18-OpenWrt",
            "R18-OpenWrt-5G",
            "wireless.$section.network=lan",
            "wireless.$section.encryption=psk2+ccmp",
            "uci -q get wireless.r18_24g",
            "uci -q get wireless.r18_5g",
            "2g)",
            "5g)",
        ),
        "Stage 4 wireless defaults",
    )
    require("R18-OpenWrt-Test" not in wifi, "Stage 4 must not retain the test SSID")
    require("r18-wifi-psk" not in wifi, "wireless defaults retain the private PSK file")
    require('wireless.$section.key=$psk' in wifi, "wireless defaults do not configure the public Wi-Fi credential")
    require(
        wifi.find("uci -q get wireless.r18_24g") < wifi.find("for iface in"),
        "wireless defaults may overwrite settings-preserved Wi-Fi configuration",
    )
    passed("2.4 GHz and 5 GHz first-boot LAN AP defaults use the intentional public WPA2 credential")

    defaults = section_for(text, DEFAULTS)
    keep_luci = section_for(text, KEEP_LUCI)
    require_all(
        defaults,
        (
            "Meizu-R18",
            "luci.main.lang='zh_cn'",
        ),
        "Stage 4 system defaults",
    )
    require("luci.main.mediaurlbase" not in defaults, "R18 defaults must not override LuCI Bootstrap")
    require("/etc/config/luci" in keep_luci, "R18 LuCI config is absent from sysupgrade keep list")
    require(
        text.count("uci set luci.main.mediaurlbase") == 0,
        "theme selection has an unexpected boot-time override",
    )
    passed("/etc/config/luci explicitly retained by keep-settings")
    passed("no boot-time theme override; Bootstrap remains LuCI's clean default")

    rescue = section_for(text, RESCUE)
    disable = section_for(text, RESCUE_DISABLE)
    require("START=99" in rescue and "USE_PROCD=1" in rescue, "manual rescue metadata changed")
    require("procd_set_param command /usr/sbin/r18-net-rescue-worker" in rescue, "manual rescue worker is missing")
    require("[ -n \"$IPKG_INSTROOT\" ] && return 0" in rescue, "rescue is enabled during image construction")
    require("/etc/init.d/r18-net-rescue disable" in disable, "rescue disable hook is missing")
    require("S99r18-net-rescue" not in text, "Stage patch must not create a rescue auto-start link")
    passed("manual r18-net-rescue is retained and image auto-start remains disabled")

    health = section_for(text, HEALTHCHECK)
    require("new file mode 100755" in health, "r18-healthcheck is not executable")
    require_all(
        health,
        (
            "Meizu R18 Health Check",
            "Board:",
            "MTD LAYOUT",
            "WAN status:",
            "radio0 / 2.4 GHz",
            "radio1 / 5 GHz",
            "s25fl128s1",
            "01 20 18 4d 01 80",
            "Page size",
            "Auto start: disabled",
        ),
        "r18-healthcheck",
    )
    require_all(
        health,
        (
            "Remove only the requested field name(s), then return the complete value.",
            "sub(/^[[:space:]]*[^[:space:]]+[[:space:]]*/, \"\")",
            "sub(/^[[:space:]]*[^[:space:]]+[[:space:]]+[^[:space:]]+[[:space:]]*/, \"\")",
            "R18_HEALTHCHECK_TEST_ONLY",
        ),
        "r18-healthcheck full-value parser",
    )
    for prohibited in ("reboot", "firstboot", "jffs2reset", "mtd erase", "mtd write", "network restart", "wifi reload", "uci set"):
        require(prohibited not in health, f"r18-healthcheck contains prohibited state-changing command: {prohibited}")
    passed("r18-healthcheck parses full SPI values and remains read-only")

    lock = read_text(theme_lock, "Stage 4 theme lock")
    require_all(
        lock,
        (
            "ARGON_SOURCE=https://github.com/jerrykuku/luci-theme-argon.git",
            "ARGON_VERSION=2.4.6-20260731",
            "ARGON_COMMIT=86c3156bab0ee2b8c91af68b3fa4655f2df51d09",
        ),
        "Stage 4 theme lock",
    )
    argon = read_text(argon_package, "pinned Argon Makefile")
    require("LUCI_TITLE:=Argon Theme" in argon, "pinned Argon package is not luci-theme-argon")
    require(f"LUCI_DEPENDS:={ARGON_DEPENDS}" in argon, "Argon dependency audit changed")
    require("wget-nossl" not in argon, "Argon must not select wget-nossl")
    require("luci-app-argon-config" not in argon, "Argon theme must not depend on Argon Config")
    require("LIQUID_" not in lock and "luci-theme-liquid" not in lock, "Liquid source pin must be absent")
    passed("Bootstrap installed")
    passed("Argon source pinned")
    passed("Liquid absent")
    passed("wget-nossl absent")
    passed("argon-config absent")

    build_info = section_for(text, BUILD_INFO)
    require("@@ -0,0 +1,16 @@" in build_info, "r18-build-info patch hunk must declare all 16 lines")
    require_all(
        build_info,
        (
            "Stage=4",
            "NAME=Release Candidate",
            "OPENWRT=25.12.5",
            "KERNEL=6.12.94",
            "BOARD=meizu,r18",
            "SPI_NOR_PAGE_SIZE_FIX=256",
            "NET_RESCUE_AUTOSTART=disabled",
            "DEFAULT_LUCI_THEME=Bootstrap",
            "THEMES=Bootstrap,Argon",
            "RELEASE_CANDIDATE=v0.4.0-rc4",
        ),
        "Stage 4 build identity",
    )
    image = section_for(text, IMAGE_MK)
    require(
        "DEVICE_VARIANT := Stage 4 Release Candidate 4" in image,
        "R18 image variant is not Stage 4",
    )
    require(
        "IMAGE/sysupgrade.bin := append-kernel | append-rootfs | pad-rootfs | check-size | append-metadata" in image,
        "R18 sysupgrade must be compact and carry standard OpenWrt metadata",
    )
    require(
        "IMAGE/recovery.bin := append-kernel | append-rootfs | pad-rootfs | r18-pad-to-ff $$(IMAGE_SIZE) | check-size" in image,
        "R18 recovery rule changed",
    )
    passed("Stage 4 identity is selected; compact sysupgrade metadata and recovery format are retained")

    platform = read_text(upgrade_platform, "MT76x8 sysupgrade platform")
    require("PART_NAME=firmware" in platform, "MT76x8 sysupgrade does not target the firmware partition")
    require("REQUIRE_IMAGE_METADATA=1" in platform, "MT76x8 sysupgrade does not require image metadata")
    require("default_do_upgrade \"$1\"" in platform, "MT76x8 sysupgrade default write path is missing")
    passed("sysupgrade targets firmware safely and requires meizu,r18 image metadata")


def verify_rootfs(rootfs: Path) -> None:
    require(rootfs.is_dir(), f"extracted rootfs is missing: {rootfs}")
    expected = (
        rootfs / "etc/init.d/r18-net-rescue",
        rootfs / "etc/uci-defaults/98-r18-net-rescue-disable",
        rootfs / "etc/uci-defaults/97-r18-stage3-defaults",
        rootfs / "lib/upgrade/keep.d/r18-luci",
        rootfs / "etc/uci-defaults/99-r18-wifi-defaults",
        rootfs / "usr/sbin/r18-healthcheck",
        rootfs / "etc/config/luci",
        rootfs / "www/luci-static/bootstrap",
        rootfs / "www/luci-static/argon",
    )
    for path in expected:
        require(path.exists(), f"Stage 4 rootfs misses {path.relative_to(rootfs)}")
    rescue, _, defaults, keep_luci, wifi, health, luci_config, bootstrap, argon = expected
    build_info = rootfs / "etc/r18-build-info"
    require(build_info.is_file(), "final rootfs is missing /etc/r18-build-info")
    passed("final rootfs contains /etc/r18-build-info")
    require(rescue.stat().st_mode & 0o111, "r18-net-rescue is not executable in rootfs")
    require(health.stat().st_mode & 0o111, "r18-healthcheck is not executable in rootfs")
    require("Meizu-R18" in defaults.read_text(encoding="utf-8"), "rootfs hostname default is missing")
    require(
        keep_luci.read_text(encoding="utf-8").strip() == "/etc/config/luci",
        "rootfs sysupgrade keep list does not explicitly retain /etc/config/luci",
    )
    wifi_text = wifi.read_text(encoding="utf-8")
    require("configure_ap r18_24g" in wifi_text and "configure_ap r18_5g" in wifi_text, "rootfs dual-band defaults are missing")
    require("psk='password'" in wifi_text and 'wireless.$section.key=$psk' in wifi_text, "rootfs public Wi-Fi credential is missing")
    require("r18-wifi-psk" not in wifi_text, "rootfs wireless defaults retain the private PSK file")
    require(
        wifi_text.find("uci -q get wireless.r18_24g") < wifi_text.find("for iface in"),
        "rootfs wireless defaults may overwrite settings-preserved Wi-Fi configuration",
    )
    passed("R18-OpenWrt and R18-OpenWrt-5G are configured with the public WPA2 default")
    passed("public default Wi-Fi credential is intentional")
    passed("final rootfs LuCI config exists")
    require(
        uci_option_value(luci_config.read_text(encoding="utf-8"), "core", "main", "mediaurlbase")
        == "/luci-static/bootstrap",
        "rootfs LuCI Bootstrap clean default is missing",
    )
    passed("Bootstrap is LuCI clean default")
    defaults_dir = rootfs / "etc/uci-defaults"
    for default_script in defaults_dir.rglob("*"):
        if default_script.is_file():
            require(
                "uci set luci.main.mediaurlbase" not in default_script.read_text(encoding="utf-8"),
                f"rootfs has a boot-time theme override: {default_script.relative_to(rootfs)}",
            )
    passed("no boot-time theme override")
    identity = build_info.read_text(encoding="utf-8")
    for expected_line, label in (
        ("Stage=4", "Stage=4"),
        ("NAME=Release Candidate", "NAME=Release Candidate"),
        ("OPENWRT=25.12.5", "OpenWrt=25.12.5"),
        ("KERNEL=6.12.94", "Kernel=6.12.94"),
        ("BOARD=meizu,r18", "Board=meizu,r18"),
        ("SPI_NOR_PAGE_SIZE_FIX=256", "SPI NOR page-size fix=256"),
        ("NET_RESCUE_AUTOSTART=disabled", "rescue autostart=disabled"),
        ("DEFAULT_LUCI_THEME=Bootstrap", "default theme=Bootstrap"),
        ("THEMES=Bootstrap,Argon", "themes=Bootstrap,Argon"),
        ("RELEASE_CANDIDATE=v0.4.0-rc4", "release candidate=v0.4.0-rc4"),
    ):
        require_exact_line(identity, expected_line, f"rootfs {label}")
        passed(f"rootfs {label}")
    require(bootstrap.is_dir(), "Bootstrap theme assets are missing")
    passed("Bootstrap static assets installed")
    require(argon.is_dir(), "Argon theme assets are missing")
    passed("Argon static assets installed")
    enabled_links = sorted((rootfs / "etc/rc.d").glob("S*r18-net-rescue"))
    require(not enabled_links, "r18-net-rescue is unexpectedly enabled in image")
    passed("r18-net-rescue has no auto-start link")


def verify_recovery_rootfs(recovery: Path) -> None:
    require(recovery.is_file(), f"R18 recovery image is missing: {recovery}")
    unsquashfs = shutil.which("unsquashfs")
    require(unsquashfs is not None, "unsquashfs is required for Stage 4 rootfs verification")
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

    with tempfile.TemporaryDirectory(prefix="r18-stage3-rootfs-") as temporary:
        root = Path(temporary)
        squashfs_path = root / "rootfs.squashfs"
        extracted = root / "rootfs"
        squashfs_path.write_bytes(squashfs)
        result = subprocess.run(
            [unsquashfs, "-no-progress", "-d", str(extracted), str(squashfs_path), *ROOTFS_PATHS],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            fail("selective unsquashfs failed: " + (result.stdout + result.stderr).strip())
        listing = subprocess.run(
            [unsquashfs, "-lls", str(squashfs_path)],
            text=True,
            capture_output=True,
            check=False,
        )
        if listing.returncode:
            fail("SquashFS listing failed: " + (listing.stdout + listing.stderr).strip())
        require("etc/r18-wifi-psk" not in listing.stdout, "final rootfs contains a private Wi-Fi PSK file")
        passed("no private Wi-Fi PSK file")
        passed("no /etc/r18-wifi-psk")
        require("www/luci-static/liquid" not in listing.stdout, "Liquid is unexpectedly present in final rootfs")
        passed("Liquid absent from final rootfs")
        verify_rootfs(extracted)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-patch", type=Path, required=True)
    parser.add_argument("--generated-patch", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--upgrade-platform", type=Path, required=True)
    parser.add_argument("--theme-lock", type=Path, required=True)
    parser.add_argument("--argon-package", type=Path, required=True)
    parser.add_argument("--kernel-tar", type=Path)
    parser.add_argument("--spansion", type=Path)
    parser.add_argument("--recovery", type=Path)
    args = parser.parse_args()

    try:
        verify_source(
            args.stage_patch,
            args.generated_patch,
            args.config,
            args.upgrade_platform,
            args.theme_lock,
            args.argon_package,
        )
        if args.kernel_tar:
            verify_kernel_patch_application(args.generated_patch, args.kernel_tar)
        if args.spansion:
            verify_patched_source(read_text(args.spansion, "prepared spansion.c"))
        if args.recovery:
            verify_recovery_rootfs(args.recovery)
    except (OSError, tarfile.TarError, VerificationError) as error:
        print(f"::error::{error}", file=sys.stderr)
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Stage 4 source verification: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
