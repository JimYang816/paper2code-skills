"""Read-only capability detection for PDF extraction paths."""

import importlib.util
import json
import shutil
from pathlib import Path


SCHEMA_VERSION = "1.0"


def executable(name):
    return shutil.which(name)


def module_available(name):
    return importlib.util.find_spec(name) is not None


def _tools(*names):
    found = [name for name in names if executable(name)]
    return found


def _module_tools(*names):
    return [name for name in names if module_available(name)]


def build_report(pdf=None):
    native_text = _tools("pdftotext", "mutool") + _module_tools(
        "pypdf", "PyPDF2", "pdfminer", "fitz"
    )
    page_rendering = _tools("pdftoppm", "pdftocairo", "mutool") + _module_tools("fitz")
    image_extraction = _tools("pdfimages", "mutool") + _module_tools("fitz")
    ocr = _tools("tesseract")

    capabilities = [
        ("Native text extraction", bool(native_text), native_text, "Extract text directly from the PDF."),
        ("Page rendering", bool(page_rendering), page_rendering, "Render pages to raster images."),
        ("OCR fallback", bool(page_rendering and ocr), [*page_rendering, *ocr], "OCR rendered pages when native text is absent."),
        ("Formula extraction", bool(native_text or (page_rendering and ocr)), native_text or ocr, "Heuristic extraction from page text; not symbolic verification."),
        ("Table extraction", bool(native_text or (page_rendering and ocr)), native_text or ocr, "Heuristic layout-preserving text/OCR extraction."),
        ("Figure extraction", bool(page_rendering or image_extraction), page_rendering or image_extraction, "Rendered pages or embedded image extraction."),
        ("Plot extraction", bool(page_rendering and (image_extraction or native_text)), page_rendering, "Rendered figure pages with text-based plot detection."),
    ]

    available = []
    missing = []
    recovery_commands = []
    for name, present, tools, detail in capabilities:
        if present:
            available.append({"name": name, "tools": sorted(set(tools)), "detail": detail})
        else:
            missing.append({"name": name, "tools": sorted(set(tools)), "detail": detail})

    if not native_text and not (page_rendering and ocr):
        recovery_commands.append(
            "Install pdftotext, pypdf, or PyMuPDF, or install tesseract with a PDF renderer."
        )
    if not page_rendering:
        recovery_commands.append("Install pdftoppm, pdftocairo, or PyMuPDF for page rendering.")
    if not ocr:
        recovery_commands.append("Install tesseract to enable the OCR fallback.")

    return {
        "schema_version": SCHEMA_VERSION,
        "stage": "extract-paper2code",
        "pdf": Path(pdf).name if pdf else None,
        "available": available,
        "missing": missing,
        "recovery_commands": recovery_commands,
    }


def render_report(report=None):
    return json.dumps(report or build_report(), indent=2, sort_keys=True) + "\n"
