#!/usr/bin/env python3
"""Report setup capabilities without importing optional dependencies."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    gh_name = os.environ.get("PAPER2CODE_GH", "gh")
    checks = {
        "PyYAML": importlib.util.find_spec("yaml") is not None,
        "jsonschema": importlib.util.find_spec("jsonschema") is not None,
        "Git": shutil.which("git") is not None,
        "GitHub CLI": Path(gh_name).exists() if Path(gh_name).is_absolute() else shutil.which(gh_name) is not None,
    }
    report = {
        "schema_version": "1.0",
        "stage": "setup-paper2code",
        "available": [{"name": name} for name, found in checks.items() if found],
        "missing": [{"name": name} for name, found in checks.items() if not found],
        "recovery_commands": (
            (["python -m pip install PyYAML==6.0.3"] if not checks["PyYAML"] else [])
            + (["python -m pip install jsonschema==4.26.0"] if not checks["jsonschema"] else [])
            + (["Install Git and put git on PATH."] if not checks["Git"] else [])
            + (["Install GitHub CLI and run gh auth login."] if not checks["GitHub CLI"] else [])
        ),
    }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(json.dumps(report, sort_keys=True))
    return 3 if not checks["PyYAML"] or not checks["jsonschema"] or not checks["Git"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
