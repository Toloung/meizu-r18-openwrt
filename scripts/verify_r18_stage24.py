#!/usr/bin/env python3
"""Verify the narrowly scoped Meizu R18 Stage 2.4 SPI-NOR patch chain."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


GENERATED_PATCH_RELATIVE = (
    "target/linux/ramips/patches-6.12/"
    "935-mtd-spi-nor-spansion-s25fl128s1-256-byte-page.patch"
)
SPANSION_RELATIVE = "drivers/mtd/spi-nor/spansion.c"
JEDEC = "SNOR_ID(0x01, 0x20, 0x18, 0x4d, 0x01, 0x80)"
FIXUP_FUNCTION = "s25fl128s1_post_bfpt_fixups"
FIXUP_STRUCT = "s25fl128s1_fixups"
PAGE_SIZE_ASSIGNMENT = "nor->params->page_size = 256;"


class VerificationError(Exception):
    """A Stage 2.4 verification requirement was not met."""


def fail(message: str) -> None:
    raise VerificationError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def pass_message(message: str) -> None:
    print(f"[PASS] {message}")


def read_text(path: Path, label: str) -> str:
    require(path.is_file(), f"{label} is missing: {path}")
    return path.read_text(encoding="utf-8")


def verify_stage_patch(stage_patch: Path) -> None:
    text = read_text(stage_patch, "managed Stage patch")
    header = f"diff --git a/{GENERATED_PATCH_RELATIVE} b/{GENERATED_PATCH_RELATIVE}"
    require(
        header in text,
        "managed Stage patch does not create the Stage 2.4 935 kernel patch "
        f"({GENERATED_PATCH_RELATIVE})",
    )
    pass_message("managed Stage patch injects the Stage 2.4 935 kernel patch")


def verify_generated_patch(kernel_patch: Path) -> str:
    text = read_text(kernel_patch, "generated Stage 2.4 kernel patch")
    require(
        f"--- a/{SPANSION_RELATIVE}" in text and f"+++ b/{SPANSION_RELATIVE}" in text,
        "generated 935 patch does not modify drivers/mtd/spi-nor/spansion.c",
    )
    require(FIXUP_FUNCTION in text, "generated 935 patch lacks the dedicated S25FL128S1 post-BFPT fixup")
    require(PAGE_SIZE_ASSIGNMENT in text, "generated 935 patch lacks the 256-byte page-size assignment")
    require(
        f".post_bfpt = {FIXUP_FUNCTION}" in text,
        "generated 935 patch lacks the dedicated spi_nor_fixups post_bfpt binding",
    )
    require(
        f".fixups = &{FIXUP_STRUCT}," in text,
        "generated 935 patch lacks the S25FL128S1 dedicated fixup binding",
    )
    require(
        '.name = "s25fl128s1",' in text,
        "generated 935 patch lacks S25FL128S1 flash_info entry context",
    )
    require(
        ".fixups = &s25fs_s_nor_fixups," not in text,
        "generated 935 patch incorrectly binds S25FL128S1 to s25fs_s_nor_fixups",
    )

    added_page_size_assignments = [
        line
        for line in text.splitlines()
        if line.startswith("+") and not line.startswith("+++") and "page_size" in line
    ]
    require(
        added_page_size_assignments == [f"+\t{PAGE_SIZE_ASSIGNMENT}"],
        "generated 935 patch must add exactly one page_size assignment inside the "
        "dedicated S25FL128S1 fixup; found: " + repr(added_page_size_assignments),
    )
    pass_message("generated 935 patch contains only the dedicated S25FL128S1 page-size fixup")
    return text


def run_patch(command: list[str], description: str) -> None:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    details = (result.stdout + result.stderr).strip()
    if result.returncode:
        fail(f"{description} failed (exit {result.returncode}): {details or 'no patch output'}")
    normalized = details.lower()
    require(
        "fuzz" not in normalized and "offset" not in normalized,
        f"{description} applied with prohibited fuzz or offset: {details or 'no patch output'}",
    )


def find_tar_member(archive: tarfile.TarFile) -> tarfile.TarInfo:
    matches = [member for member in archive.getmembers() if member.name.endswith(SPANSION_RELATIVE)]
    require(
        len(matches) == 1,
        "Linux source archive must contain exactly one " + SPANSION_RELATIVE,
    )
    return matches[0]


def flash_info_entry(source: str) -> str:
    start = source.find(JEDEC)
    require(start >= 0, "patched spansion.c lacks JEDEC 01 20 18 4d 01 80")
    end = source.find("\n\t}, {", start)
    require(end >= 0, "could not delimit the S25FL128S1 flash_info entry in patched spansion.c")
    return source[start:end]


def function_body(source: str, function: str) -> str:
    start = source.find(f"static int {function}(")
    require(start >= 0, f"patched spansion.c lacks {function}")
    open_brace = source.find("{", start)
    require(open_brace >= 0, f"could not find the body of {function}")
    depth = 0
    for index in range(open_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[open_brace : index + 1]
    fail(f"could not delimit the body of {function}")


def verify_patched_source(source: str) -> None:
    body = function_body(source, FIXUP_FUNCTION)
    require(PAGE_SIZE_ASSIGNMENT in body, "S25FL128S1 post-BFPT fixup does not set page_size to 256")

    struct_start = source.find(f"static const struct spi_nor_fixups {FIXUP_STRUCT}")
    require(struct_start >= 0, "patched spansion.c lacks the dedicated S25FL128S1 spi_nor_fixups structure")
    struct_end = source.find("\n};", struct_start)
    require(struct_end >= 0, "could not delimit the dedicated S25FL128S1 spi_nor_fixups structure")
    require(
        f".post_bfpt = {FIXUP_FUNCTION}" in source[struct_start:struct_end],
        "dedicated S25FL128S1 spi_nor_fixups structure lacks its post_bfpt callback",
    )

    entry = flash_info_entry(source)
    require('.name = "s25fl128s1",' in entry, "JEDEC 01 20 18 4d 01 80 is not the s25fl128s1 entry")
    require(
        f".fixups = &{FIXUP_STRUCT}," in entry,
        "JEDEC 01 20 18 4d 01 80 is missing the dedicated S25FL128S1 fixup binding",
    )
    require(
        ".fixups = &s25fs_s_nor_fixups," not in entry,
        "JEDEC 01 20 18 4d 01 80 must not use s25fs_s_nor_fixups",
    )
    pass_message("patched spansion.c binds JEDEC 01 20 18 4d 01 80 only to the dedicated S25FL128S1 fixup")


def verify_kernel_patch_application(kernel_patch: Path, kernel_tar: Path) -> None:
    kernel_patch = kernel_patch.resolve()
    kernel_tar = kernel_tar.resolve()
    require(kernel_tar.is_file(), f"Linux 6.12.94 source archive is missing: {kernel_tar}")
    patch_binary = shutil.which("patch")
    require(patch_binary is not None, "host 'patch' utility is required for kernel patch verification")

    with tempfile.TemporaryDirectory(prefix="r18-stage24-") as temporary:
        root = Path(temporary) / "linux-6.12.94"
        spansion = root / SPANSION_RELATIVE
        spansion.parent.mkdir(parents=True)
        with tarfile.open(kernel_tar, "r:xz") as archive:
            member = find_tar_member(archive)
            source_file = archive.extractfile(member)
            require(source_file is not None, f"could not read {member.name} from {kernel_tar}")
            spansion.write_bytes(source_file.read())

        dry_run = [patch_binary, "--batch", "--forward", "--dry-run", "-p1", "-d", str(root), "-i", str(kernel_patch)]
        run_patch(dry_run, "kernel patch dry-run")
        pass_message("kernel patch dry-run")

        apply = [patch_binary, "--batch", "--forward", "-p1", "-d", str(root), "-i", str(kernel_patch)]
        run_patch(apply, "kernel patch application")
        pass_message("kernel patch applied")

        verify_patched_source(read_text(spansion, "patched spansion.c"))

        reverse = [patch_binary, "--batch", "--forward", "--dry-run", "-R", "-p1", "-d", str(root), "-i", str(kernel_patch)]
        run_patch(reverse, "kernel patch reverse dry-run")
        pass_message("kernel patch reverse check")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-patch", type=Path, required=True, help="managed R18 Stage patch")
    parser.add_argument("--generated-patch", type=Path, required=True, help="935 patch created after Stage patch application")
    parser.add_argument("--kernel-tar", type=Path, help="OpenWrt v25.12.5 Linux 6.12.94 source archive")
    parser.add_argument("--spansion", type=Path, help="already prepared spansion.c to validate after the build")
    args = parser.parse_args()

    try:
        verify_stage_patch(args.stage_patch)
        verify_generated_patch(args.generated_patch)
        if args.kernel_tar:
            verify_kernel_patch_application(args.generated_patch, args.kernel_tar)
        if args.spansion:
            verify_patched_source(read_text(args.spansion, "prepared spansion.c"))
    except (OSError, tarfile.TarError, VerificationError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Stage 2.4 source verification: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
