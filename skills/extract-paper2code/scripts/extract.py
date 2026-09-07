#!/usr/bin/env python3
"""Extract a target PDF into an audited Paper Dossier."""

import argparse
import datetime as _datetime
import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from capabilities import build_report, executable


SCHEMA_VERSION = "1.0"
READY_STATE = "ready_for_extraction"
EXTRACTED_STATE = "evidence_extracted"
EVIDENCE_CLASSES = {
    "formula",
    "parameter",
    "dataset",
    "network_component",
    "baseline",
    "result_claim",
}
DERIVED_PROVENANCE = {"derived", "reconstructed", "empirically_selected"}
UNIT_CLASSES = {"parameter", "result_claim"}


class ContractError(ValueError):
    pass


class CapabilityUnavailable(ContractError):
    pass


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"Cannot read {path}: {exc}") from exc


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_tool(name, *arguments, cwd=None):
    tool = executable(name)
    if not tool:
        raise FileNotFoundError(name)
    command = [tool, *arguments]
    if os.name == "nt" and tool.lower().endswith((".cmd", ".bat")):
        command = ["cmd", "/c", tool, *arguments]
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True)


def read_pdf_info(path):
    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        raise ContractError(f"{path} is not a PDF")
    text = data.decode("latin-1", errors="replace")
    match = re.search(r"/Type\s*/Pages[^>]*?/Count\s+(\d+)", text, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"/Count\s+(\d+)", text)
    page_count = int(match.group(1)) if match else 0
    if page_count < 1:
        raise ContractError(f"{path} does not declare a usable page count")

    metadata = {}
    for key in ("Title", "Author", "Subject", "Keywords"):
        found = re.search(rf"/{key}\s*\(([^)]*)\)", text)
        if found:
            metadata[key.lower()] = found.group(1)
    return {
        "name": path.name,
        "sha256": sha256(path),
        "page_count": page_count,
        "metadata": metadata,
    }


def _optional_module(name):
    try:
        return importlib.import_module(name)
    except ImportError:
        return None


def extract_page_text(pdf, page, destination):
    if executable("pdftotext"):
        completed = run_tool(
            "pdftotext", "-layout", "-f", str(page), "-l", str(page), str(pdf), str(destination)
        )
        if completed.returncode != 0:
            raise ContractError(completed.stderr.strip() or "pdftotext failed")
        return destination.read_text(encoding="utf-8", errors="replace")

    pypdf = _optional_module("pypdf") or _optional_module("PyPDF2")
    if pypdf:
        reader = pypdf.PdfReader(str(pdf))
        if page <= len(reader.pages):
            text = reader.pages[page - 1].extract_text() or ""
            destination.write_text(text, encoding="utf-8")
            return text

    fitz = _optional_module("fitz")
    if fitz:
        document = fitz.open(str(pdf))
        if page <= document.page_count:
            text = document[page - 1].get_text()
            destination.write_text(text, encoding="utf-8")
            return text

    return ""


def render_page(pdf, page, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if executable("pdftoppm"):
        prefix = destination.with_suffix("")
        completed = run_tool(
            "pdftoppm", "-png", "-f", str(page), "-l", str(page), str(pdf), str(prefix)
        )
        if completed.returncode != 0:
            raise ContractError(completed.stderr.strip() or "pdftoppm failed")
        expected = prefix.parent / f"{prefix.name}-{page:02d}.png"
        if expected.is_file():
            if expected != destination:
                shutil.copy2(expected, destination)
            return destination
        candidates = sorted(prefix.parent.glob(f"{prefix.name}*.png"))
        if candidates:
            shutil.copy2(candidates[0], destination)
            return destination
        raise ContractError("pdftoppm did not produce a page image")

    fitz = _optional_module("fitz")
    if fitz:
        document = fitz.open(str(pdf))
        if page > document.page_count:
            raise ContractError(f"Page {page} is outside the PDF")
        pixmap = document[page - 1].get_pixmap(dpi=150)
        pixmap.save(str(destination))
        return destination

    raise ContractError("No page renderer is available")


def ocr_page(pdf, page, destination):
    render_path = destination.with_name(f"page-{page:02d}-ocr.png")
    render_page(pdf, page, render_path)
    completed = run_tool("tesseract", str(render_path), str(destination.with_suffix("")))
    if completed.returncode != 0:
        raise ContractError(completed.stderr.strip() or "tesseract failed")
    text_path = destination.with_suffix(".txt")
    return text_path.read_text(encoding="utf-8", errors="replace")


def write_capability_report(root, pdf):
    report = build_report(pdf)
    path = root / ".paper2code/capability-reports/extraction.yaml"
    write_json(path, report)
    return report, path


def required_capabilities_present(report):
    available = {item["name"] for item in report["available"]}
    text_ready = "Native text extraction" in available or "OCR fallback" in available
    render_ready = "Page rendering" in available
    return text_ready and render_ready


def command_extract(args):
    root = args.root.resolve()
    pdf = args.pdf.resolve()
    state_path = root / ".paper2code/state.yaml"
    if not state_path.is_file():
        raise ContractError("Missing .paper2code/state.yaml")
    state = load_json(state_path)
    if state.get("state") != READY_STATE:
        raise ContractError(
            f"Extraction requires state {READY_STATE}, got {state.get('state')}"
        )

    report, report_path = write_capability_report(root, pdf)
    if not required_capabilities_present(report):
        raise CapabilityUnavailable(
            json.dumps(
                {
                    "stage": "extract-paper2code",
                    "capability_report": str(report_path),
                    "missing": report["missing"],
                    "recovery_commands": report["recovery_commands"],
                },
                sort_keys=True,
            )
        )

    info = read_pdf_info(pdf)
    paper_dir = root / "paper"
    paper_dir.mkdir(parents=True, exist_ok=True)
    managed_pdf = paper_dir / pdf.name
    if managed_pdf != pdf:
        shutil.copy2(pdf, managed_pdf)

    extraction_dir = root / ".paper2code/extraction"
    text_dir = extraction_dir / "text"
    page_dir = extraction_dir / "pages"
    text_dir.mkdir(parents=True, exist_ok=True)
    page_dir.mkdir(parents=True, exist_ok=True)

    pages = []
    figure_index = 0
    plot_index = 0
    for page in range(1, info["page_count"] + 1):
        text_path = text_dir / f"page-{page:02d}.txt"
        page_path = page_dir / f"page-{page:02d}.png"
        text = extract_page_text(pdf, page, text_path)
        ocr_path = None
        if not text.strip() and executable("tesseract"):
            text = ocr_page(pdf, page, text_path)
            ocr_path = str(text_path)
        if not text.strip():
            text_path.write_text("", encoding="utf-8")
        render_page(pdf, page, page_path)
        pages.append(
            {
                "page": page,
                "text": str(text_path.relative_to(root)),
                "render": str(page_path.relative_to(root)),
                "ocr": str(Path(ocr_path).relative_to(root)) if ocr_path else None,
                "has_text": bool(text.strip()),
            }
        )

    figures = []
    for record in pages:
        text_path = root / record["text"]
        text = text_path.read_text(encoding="utf-8", errors="replace")
        page_path = root / record["render"]
        if re.search(r"\b(Figure|Fig\.)\s*\d", text, flags=re.IGNORECASE):
            figure_index += 1
            destination = root / "dossier/figures" / f"figure-{figure_index:04d}.png"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(page_path, destination)
            figures.append(
                {
                    "id": f"FIG-{figure_index:04d}",
                    "kind": "figure",
                    "page": record["page"],
                    "path": str(destination.relative_to(root)),
                }
            )
        if re.search(r"\b(plot|curve)\b", text, flags=re.IGNORECASE):
            plot_index += 1
            destination = root / "dossier/figures" / f"plot-{plot_index:04d}.png"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(page_path, destination)
            figures.append(
                {
                    "id": f"PLOT-{plot_index:04d}",
                    "kind": "plot",
                    "page": record["page"],
                    "path": str(destination.relative_to(root)),
                }
            )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "pdf": {
            "name": info["name"],
            "sha256": info["sha256"],
            "page_count": info["page_count"],
            "metadata": info["metadata"],
            "managed_path": str(managed_pdf.relative_to(root)),
        },
        "capability_report": str(report_path.relative_to(root)),
        "pages": pages,
        "figures": figures,
    }
    write_json(extraction_dir / "manifest.yaml", manifest)

    evidence_path = root / "dossier/evidence.yaml"
    if not evidence_path.is_file():
        write_json(evidence_path, {"schema_version": SCHEMA_VERSION, "items": []})

    paper = [
        "# Paper Dossier",
        "",
        "## Source",
        "",
        f"- PDF: {info['name']}",
        f"- SHA-256: `{info['sha256']}`",
        f"- Page count: {info['page_count']}",
        f"- Extracted: {_datetime.datetime.now(_datetime.timezone.utc).isoformat()}",
        "",
        "## Evidence",
        "",
        "Structured Evidence Items are recorded in `evidence.yaml`.",
        "",
        "## Figures",
        "",
        "Rendered figures and plots are stored in `figures/`.",
        "",
        "## Audit",
        "",
        "The adversarial Evidence Audit is recorded in `audit.yaml`.",
        "",
    ]
    for record in pages:
        text_path = root / record["text"]
        page_text = text_path.read_text(encoding="utf-8", errors="replace").strip()
        paper.extend(["## Extracted Text", "", f"### Page {record['page']}", "", page_text or "_No text extracted._", ""])

    (root / "dossier/paper.md").write_text("\n".join(paper), encoding="utf-8")
    return {
        "stage": "extract-paper2code",
        "state": state.get("state"),
        "pdf": str(managed_pdf),
        "pages": len(pages),
        "figures": len(figures),
        "manifest": str(extraction_dir / "manifest.yaml"),
        "capability_report": str(report_path),
    }


def _normalize_numbers(value):
    return re.sub(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", "#", value)


def _numeric_tokens(value):
    return tuple(
        float(token) for token in re.findall(
            r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", value
        )
    )


def command_audit(args):
    root = args.root.resolve()
    evidence_path = root / "dossier/evidence.yaml"
    if not evidence_path.is_file():
        raise ContractError("Missing dossier/evidence.yaml")
    evidence = load_json(evidence_path)
    items = evidence.get("items", [])
    manifest_path = root / ".paper2code/extraction/manifest.yaml"
    manifest = load_json(manifest_path) if manifest_path.is_file() else None
    page_count = manifest["pdf"]["page_count"] if manifest else None

    findings = []
    counter = 0

    def add_finding(category, severity, title, detail, evidence_ids, page=None):
        nonlocal counter
        counter += 1
        findings.append(
            {
                "id": f"AUD-{counter:04d}",
                "category": category,
                "severity": severity,
                "title": title,
                "detail": detail,
                "evidence_ids": evidence_ids,
                "page": page,
                "status": "open",
                "triage_note": None,
            }
        )

    if not items:
        add_finding(
            "omission",
            "blocking",
            "No Evidence Items were recorded",
            "The dossier must record at least one material Evidence Item before the audit can check its claims.",
            [],
        )

    evidence_ids = {item.get("id") for item in items if item.get("id")}
    for item in items:
        for dependency in item.get("dependencies", []):
            if isinstance(dependency, str) and dependency not in evidence_ids:
                add_finding(
                    "omission",
                    "blocking",
                    f"{item.get('id')} references missing Evidence Item {dependency}",
                    "Every dependency must resolve to an Evidence Item already present in the dossier.",
                    [item.get("id")],
                    (item.get("locator") or {}).get("page"),
                )

    identifiers = [item.get("id") for item in items]
    duplicates = sorted({item for item in identifiers if identifiers.count(item) > 1})
    for duplicate in duplicates:
        add_finding(
            "indexing",
            "blocking",
            f"Duplicate Evidence Item identifier {duplicate}",
            "Evidence Item identifiers must be unique and stable.",
            [duplicate],
        )
    if page_count is not None:
        for item in items:
            page = (item.get("locator") or {}).get("page")
            if isinstance(page, int) and page > page_count:
                add_finding(
                    "indexing",
                    "blocking",
                    f"{item.get('id')} points outside the PDF",
                    f"Locator page {page} exceeds the declared page count {page_count}.",
                    [item.get("id")],
                    page,
                )

    grouped = {}
    for item in items:
        if item.get("class") in UNIT_CLASSES:
            key = (item.get("class"), _normalize_numbers(item.get("text", "")))
            grouped.setdefault(key, []).append(item)
    for (item_class, _), group in grouped.items():
        numeric_values = {_numeric_tokens(item.get("text", "")) for item in group}
        if len(group) > 1 and len(numeric_values) > 1:
            add_finding(
                "contradiction",
                "blocking",
                f"Conflicting numeric values in {item_class}",
                "Multiple Evidence Items use the same normalized statement but disagree on a numeric value.",
                [item.get("id") for item in group],
            )

    for item in items:
        if item.get("class") in UNIT_CLASSES and not item.get("units"):
            add_finding(
                "unit",
                "warning",
                f"{item.get('id')} is missing units",
                "Material parameters and result claims must declare their units.",
                [item.get("id")],
                (item.get("locator") or {}).get("page"),
            )

    for item in items:
        citations = re.findall(r"\[(\d+)\]", item.get("text", ""))
        if citations:
            add_finding(
                "citation_dependency",
                "blocking",
                f"{item.get('id')} depends on untriaged citations",
                f"Citation markers {sorted(set(citations))} must be resolved to named supporting sources or target-paper references.",
                [item.get("id")],
                (item.get("locator") or {}).get("page"),
            )

    for item in items:
        if item.get("provenance") in DERIVED_PROVENANCE and not item.get("dependencies"):
            add_finding(
                "unsupported_inference",
                "blocking",
                f"{item.get('id')} is an unsupported inference",
                "Derived, reconstructed, and empirically selected evidence must cite the Paper Evidence or Reconstruction Decisions it depends on.",
                [item.get("id")],
                (item.get("locator") or {}).get("page"),
            )

    items_by_id = sorted(findings, key=lambda item: item["id"])
    audit = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
        "items": items_by_id,
        "summary": {
            "total": len(items_by_id),
            "open": len(items_by_id),
            "triaged": 0,
        },
    }
    audit_path = root / "dossier/audit.yaml"
    write_json(audit_path, audit)
    return {
        "stage": "extract-paper2code",
        "audit": str(audit_path),
        "findings": len(items_by_id),
    }


def _run_core(root, *arguments):
    completed = subprocess.run(
        [sys.executable, str(root / "skills/paper2code-core/scripts/paper2code.py"), *arguments],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ContractError(completed.stderr.strip() or completed.stdout.strip())
    return json.loads(completed.stdout)


def command_validate(args):
    root = args.root.resolve()
    result = _run_core(root, "validate-dossier", "--root", str(root))
    return {"stage": "extract-paper2code", **result}


def command_finalize(args):
    root = args.root.resolve()
    validation = _run_core(root, "validate-dossier", "--root", str(root))
    state_path = root / ".paper2code/state.yaml"
    _run_core(root, "check-transition", str(state_path), "--to", EXTRACTED_STATE)
    write_json(
        state_path,
        {
            "schema_version": SCHEMA_VERSION,
            "state": EXTRACTED_STATE,
            "return_target": None,
        },
    )
    return {
        "stage": "extract-paper2code",
        "state": EXTRACTED_STATE,
        "valid": validation["valid"],
        "artifacts": validation["artifacts"],
    }


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    extract = commands.add_parser("extract", help="extract a target PDF")
    extract.add_argument("--pdf", type=Path, required=True)
    extract.add_argument("--root", type=Path, required=True)
    extract.set_defaults(handler=command_extract)

    audit = commands.add_parser("audit", help="generate the adversarial Evidence Audit")
    audit.add_argument("--root", type=Path, required=True)
    audit.set_defaults(handler=command_audit)

    validate = commands.add_parser("validate", help="validate dossier artifacts")
    validate.add_argument("--root", type=Path, required=True)
    validate.set_defaults(handler=command_validate)

    finalize = commands.add_parser("finalize", help="advance to evidence_extracted")
    finalize.add_argument("--root", type=Path, required=True)
    finalize.set_defaults(handler=command_finalize)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = args.handler(args)
    except CapabilityUnavailable as exc:
        print(exc, file=sys.stderr)
        return 3
    except (ContractError, OSError, FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
