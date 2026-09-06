#!/usr/bin/env python3
"""Capability-check and extract page-located text/renders from a target PDF."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


def capabilities() -> dict[str, Any]:
    checks = {
        "pdfplumber": importlib.util.find_spec("pdfplumber") is not None,
        "pypdf": importlib.util.find_spec("pypdf") is not None,
        "pdftoppm": shutil.which("pdftoppm") is not None,
    }
    return {
        "schema_version": "1.0",
        "stage": "extract-paper",
        "available": [{"name": name} for name, found in checks.items() if found],
        "missing": [{"name": name} for name, found in checks.items() if not found],
        "recovery_commands": [
            "python -m pip install -r skills/extract-paper/references/requirements.txt"
            for name in ("pdfplumber", "pypdf")
            if not checks[name]
        ]
        + (["Install Poppler and ensure pdftoppm is on PATH."] if not checks["pdftoppm"] else []),
    }


def write_capability_report(output: Path, report: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "capability-report.yaml").write_text(
        yaml.safe_dump(report, sort_keys=False), encoding="utf-8"
    )


def extract(pdf_path: Path, output: Path, dpi: int) -> dict[str, object]:
    report = capabilities()
    if report["missing"]:
        write_capability_report(output, report)
        missing = ", ".join(item["name"] for item in report["missing"])
        raise RuntimeError(f"Missing extraction capabilities: {missing}")

    import pdfplumber

    output.mkdir(parents=True, exist_ok=True)
    pages_dir = output / "pages"
    pages_dir.mkdir(exist_ok=True)
    page_texts: list[str] = []
    needs_ocr: list[int] = []
    with pdfplumber.open(pdf_path) as document:
        metadata = {str(key): value for key, value in (document.metadata or {}).items()}
        for number, page in enumerate(document.pages, 1):
            text = page.extract_text(x_tolerance=2, y_tolerance=3) or ""
            page_texts.append(text)
            if len("".join(text.split())) < 24:
                needs_ocr.append(number)

    prefix = pages_dir / "page"
    rendered = subprocess.run(
        ["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), str(prefix)],
        text=True,
        capture_output=True,
    )
    if rendered.returncode != 0:
        raise RuntimeError(rendered.stderr or "pdftoppm failed")

    markdown = []
    page_map = []
    for number, text in enumerate(page_texts, 1):
        markdown.extend([f"<!-- page: {number} -->", f"## Page {number}", "", text, ""])
        page_map.append(
            {
                "page": number,
                "text_status": "needs_ocr" if number in needs_ocr else "native",
                "render": f"pages/page-{number:02d}.png",
            }
        )
    (output / "paper.md").write_text("\n".join(markdown), encoding="utf-8")
    (output / "extraction-map.yaml").write_text(
        yaml.safe_dump(
            {"schema_version": "1.0", "pages": page_map, "needs_ocr_pages": needs_ocr},
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    source_manifest = {
        "schema_version": "1.0",
        "source_type": "target_paper_pdf",
        "file_name": pdf_path.name,
        "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "page_count": len(page_texts),
        "metadata": metadata,
        "redistribution": "not_assumed",
    }
    (output / "source-manifest.yaml").write_text(
        yaml.safe_dump(source_manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return {
        "pages": len(page_texts),
        "needs_ocr_pages": needs_ocr,
        "renders": len(list(pages_dir.glob("page-*.png"))),
        "output": str(output),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("capabilities")
    extract_parser = commands.add_parser("extract")
    extract_parser.add_argument("pdf", type=Path)
    extract_parser.add_argument("--output", type=Path, required=True)
    extract_parser.add_argument("--dpi", type=int, default=120)
    args = parser.parse_args()
    try:
        if args.command == "capabilities":
            result = capabilities()
        else:
            result = extract(args.pdf, args.output, args.dpi)
    except (OSError, RuntimeError, yaml.YAMLError) as exc:
        print(str(exc), file=sys.stderr)
        return 3
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
