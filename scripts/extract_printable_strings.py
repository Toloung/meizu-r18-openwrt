#!/usr/bin/env python3
"""Extract targeted printable strings without requiring external `strings`."""

from __future__ import annotations

import argparse
import pathlib
import re


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    parser.add_argument("--min-length", type=int, default=4)
    parser.add_argument("--pattern", action="append", default=[])
    args = parser.parse_args()

    raw = args.input.read_bytes()
    strings = re.findall(rb"[\x20-\x7e]{%d,}" % args.min_length, raw)
    patterns = [re.compile(item, re.IGNORECASE) for item in args.pattern]
    if patterns:
        strings = [
            item for item in strings
            if any(pattern.search(item.decode("ascii", "replace")) for pattern in patterns)
        ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "# Printable-string extraction\n"
        f"# Input: {args.input.as_posix()}\n"
        f"# Minimum length: {args.min_length}\n"
        f"# Filters: {args.pattern or ['(none)']}\n\n"
        + "\n".join(item.decode("ascii", "replace") for item in strings)
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(strings)} strings to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
