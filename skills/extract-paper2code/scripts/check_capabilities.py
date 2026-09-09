#!/usr/bin/env python3
"""Write a non-mutating Capability Report for PDF extraction."""

import argparse
from pathlib import Path

from capabilities import build_report, render_report, required_capabilities_present


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = build_report(args.pdf)
    rendered = render_report(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")

    print(rendered, end="")
    return 0 if required_capabilities_present(report) else 3


if __name__ == "__main__":
    raise SystemExit(main())
