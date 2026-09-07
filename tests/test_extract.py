"""Exercise extract-paper2code with standard-library PDF tool mocks."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from _tmp import TempDirectory


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "skills/setup-paper2code/scripts/setup.py"
CHECK = ROOT / "skills/extract-paper2code/scripts/check_capabilities.py"
EXTRACT = ROOT / "skills/extract-paper2code/scripts/extract.py"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def make_pdf(path, page_count=2):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        (
            "%PDF-1.4\n"
            "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
            f"2 0 obj\n<< /Type /Pages /Count {page_count} /Kids "
            f"[{' '.join(f'{i} 0 R' for i in range(3, 3 + page_count))}] >>\nendobj\n"
        ).encode("utf-8")
    )


class ExtractTests(unittest.TestCase):
    def scaffold(self):
        temp = TempDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        target = folder / "paper"
        subprocess.run(
            [
                sys.executable,
                str(SETUP),
                "--target",
                str(target),
                "--bundle-root",
                str(ROOT),
                "--apply",
            ],
            text=True,
            capture_output=True,
            check=True,
        )
        write_json(
            target / ".paper2code/state.yaml",
            {"schema_version": "1.0", "state": "ready_for_extraction", "return_target": None},
        )
        pdf = folder / "target.pdf"
        make_pdf(pdf)
        return folder, target, pdf

    def make_tool_env(self, folder):
        tools = folder / "tools"
        tools.mkdir(exist_ok=True)
        env = os.environ.copy()
        env["PATH"] = str(tools) + os.pathsep + env.get("PATH", "")

        if os.name == "nt":
            (tools / "pdftotext.cmd").write_text(
                "@echo off\r\n"
                "set OUT=\r\n"
                "for %%A in (%*) do set OUT=%%A\r\n"
                'echo Page 1 Figure 1 Table 1 plot y=x > "%OUT%"\r\n',
                encoding="utf-8",
            )
            (tools / "pdftoppm.cmd").write_text(
                "@echo off\r\n"
                "set OUT=\r\n"
                "for %%A in (%*) do set OUT=%%A\r\n"
                'echo fake > "%OUT%-01.png"\r\n'
                'echo fake > "%OUT%-02.png"\r\n',
                encoding="utf-8",
            )
            (tools / "tesseract.cmd").write_text(
                "@echo off\r\n"
                "set OUT=\r\n"
                "for %%A in (%*) do set OUT=%%A\r\n"
                'echo ocr fallback > "%OUT%.txt"\r\n',
                encoding="utf-8",
            )
        else:
            (tools / "pdftotext").write_text(
                "#!/bin/sh\nout=${@: -1}\necho 'Page 1 Figure 1 Table 1 plot y=x' > \"$out\"\n",
                encoding="utf-8",
            )
            (tools / "pdftoppm").write_text(
                "#!/bin/sh\nout=${@: -1}\necho fake > \"${out}-01.png\"\necho fake > \"${out}-02.png\"\n",
                encoding="utf-8",
            )
            (tools / "tesseract").write_text(
                "#!/bin/sh\nout=${@: -1}\necho 'ocr fallback' > \"${out}.txt\"\n",
                encoding="utf-8",
            )
            for name in ("pdftotext", "pdftoppm", "tesseract"):
                (tools / name).chmod(0o755)
        return env

    def test_capability_report_covers_required_categories(self):
        folder, target, pdf = self.scaffold()
        report = folder / "capabilities.yaml"
        completed = subprocess.run(
            [
                sys.executable,
                str(CHECK),
                "--pdf",
                str(pdf),
                "--output",
                str(report),
            ],
            text=True,
            capture_output=True,
            env=self.make_tool_env(folder),
        )
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
        payload = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual("extract-paper2code", payload["stage"])
        names = {item["name"] for item in payload["available"]}
        self.assertSetEqual(
            {
                "Native text extraction",
                "Page rendering",
                "OCR fallback",
                "Formula extraction",
                "Table extraction",
                "Figure extraction",
                "Plot extraction",
            },
            names,
        )
        self.assertEqual([], payload["missing"])

    def test_missing_capabilities_report_and_do_not_mutate(self):
        folder, target, pdf = self.scaffold()
        empty = folder / "empty-tools"
        empty.mkdir()
        env = os.environ.copy()
        env["PATH"] = str(empty)

        report = folder / "missing-capabilities.yaml"
        completed = subprocess.run(
            [
                sys.executable,
                str(CHECK),
                "--pdf",
                str(pdf),
                "--output",
                str(report),
            ],
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(3, completed.returncode, completed.stderr or completed.stdout)
        payload = json.loads(report.read_text(encoding="utf-8"))
        self.assertTrue(payload["missing"])
        self.assertTrue(payload["recovery_commands"])

        rejected = subprocess.run(
            [sys.executable, str(EXTRACT), "extract", "--pdf", str(pdf), "--root", str(target)],
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(3, rejected.returncode)
        self.assertFalse((target / ".paper2code/extraction").exists())
        self.assertFalse((target / "dossier/paper.md").exists())

    def test_extract_creates_machine_and_human_dossier_artifacts(self):
        folder, target, pdf = self.scaffold()
        env = self.make_tool_env(folder)
        completed = subprocess.run(
            [
                sys.executable,
                str(EXTRACT),
                "extract",
                "--pdf",
                str(pdf),
                "--root",
                str(target),
            ],
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)

        paper = (target / "dossier/paper.md").read_text(encoding="utf-8")
        for heading in ("# Paper Dossier", "## Source", "## Evidence", "## Figures", "## Audit"):
            self.assertIn(heading, paper)

        manifest = json.loads((target / ".paper2code/extraction/manifest.yaml").read_text(encoding="utf-8"))
        self.assertEqual(2, manifest["pdf"]["page_count"])
        self.assertTrue(manifest["pages"])
        self.assertTrue((target / "dossier/figures/figure-0001.png").is_file())
        self.assertTrue((target / ".paper2code/extraction/pages/page-01.png").is_file())

    def test_audit_reports_all_categories_and_requires_triage(self):
        folder, target, pdf = self.scaffold()
        evidence = target / "dossier/evidence.yaml"
        write_json(
            evidence,
            {
                "schema_version": "1.0",
                "items": [
                    {
                        "id": "EVID-0001",
                        "class": "formula",
                        "text": "h = W x + b",
                        "provenance": "paper_evidence",
                        "confidence": "confirmed",
                        "status": "triaged",
                        "locator": {"page": 1, "text": "Equation 1"},
                        "units": None,
                        "dependencies": ["EVID-9999"],
                    },
                    {
                        "id": "EVID-0002",
                        "class": "parameter",
                        "text": "learning_rate = 0.001",
                        "provenance": "paper_evidence",
                        "confidence": "confirmed",
                        "status": "triaged",
                        "locator": {"page": 1, "text": "training details"},
                        "units": None,
                        "dependencies": [],
                    },
                    {
                        "id": "EVID-0002",
                        "class": "parameter",
                        "text": "learning_rate = 0.01",
                        "provenance": "paper_evidence",
                        "confidence": "confirmed",
                        "status": "triaged",
                        "locator": {"page": 2, "text": "training details"},
                        "units": "dimensionless",
                        "dependencies": [],
                    },
                    {
                        "id": "EVID-0003",
                        "class": "network_component",
                        "text": "UDNet uses 8 unfolded layers",
                        "provenance": "paper_evidence",
                        "confidence": "confirmed",
                        "status": "triaged",
                        "locator": {"page": 1, "text": "architecture"},
                        "units": None,
                        "dependencies": [],
                    },
                    {
                        "id": "EVID-0004",
                        "class": "baseline",
                        "text": "ZF is compared in [12]",
                        "provenance": "paper_evidence",
                        "confidence": "confirmed",
                        "status": "triaged",
                        "locator": {"page": 2, "text": "baselines"},
                        "units": None,
                        "dependencies": [],
                    },
                    {
                        "id": "EVID-0005",
                        "class": "result_claim",
                        "text": "SER 0.01",
                        "provenance": "derived",
                        "confidence": "medium",
                        "status": "triaged",
                        "locator": {"page": 2, "text": "results"},
                        "units": "dimensionless",
                        "dependencies": [],
                    },
                ],
            },
        )

        completed = subprocess.run(
            [sys.executable, str(EXTRACT), "audit", "--root", str(target)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)

        audit_path = target / "dossier/audit.yaml"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        categories = {item["category"] for item in audit["items"]}
        self.assertSetEqual(
            {
                "omission",
                "contradiction",
                "unit",
                "indexing",
                "citation_dependency",
                "unsupported_inference",
            },
            categories,
        )
        self.assertTrue(all(item["status"] == "open" for item in audit["items"]))

    def test_finalize_requires_a_triaged_valid_dossier(self):
        folder, target, pdf = self.scaffold()
        paper = target / "dossier/paper.md"
        paper.write_text(
            "# Paper Dossier\n\n## Source\n\nsource\n\n## Evidence\n\nevidence.yaml\n\n"
            "## Figures\n\nfigures\n\n## Audit\n\naudit.yaml\n",
            encoding="utf-8",
        )
        evidence = target / "dossier/evidence.yaml"
        write_json(
            evidence,
            {
                "schema_version": "1.0",
                "items": [],
            },
        )
        subprocess.run(
            [sys.executable, str(EXTRACT), "audit", "--root", str(target)],
            text=True,
            capture_output=True,
            check=True,
        )

        rejected = subprocess.run(
            [sys.executable, str(EXTRACT), "finalize", "--root", str(target)],
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(0, rejected.returncode)

        audit_path = target / "dossier/audit.yaml"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        for item in audit["items"]:
            item["status"] = "triaged"
            item["triage_note"] = "accepted after review"
        write_json(audit_path, audit)

        completed = subprocess.run(
            [sys.executable, str(EXTRACT), "finalize", "--root", str(target)],
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
        state = json.loads((target / ".paper2code/state.yaml").read_text(encoding="utf-8"))
        self.assertEqual("evidence_extracted", state["state"])


if __name__ == "__main__":
    unittest.main()
