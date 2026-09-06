import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "extract-paper" / "scripts" / "extract_pdf.py"
PDF = ROOT / "UDNet" / "Model-Driven_Based_Deep_Unfolding_Equalizer_for_Underwater_Acoustic_OFDM_Communications.pdf"


class ExtractionTests(unittest.TestCase):
    @unittest.skipUnless(PDF.exists(), "licensed anchor PDF is not committed")
    def test_anchor_pdf_produces_page_located_text_and_renders(self):
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "dossier"
            completed = subprocess.run(
                [sys.executable, str(SCRIPT), "extract", str(PDF), "--output", str(output)],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(12, result["pages"])
            markdown = (output / "paper.md").read_text(encoding="utf-8")
            self.assertIn("<!-- page: 1 -->", markdown)
            self.assertIn("Model-Driven Based Deep Unfolding Equalizer", markdown)
            manifest = yaml.safe_load((output / "source-manifest.yaml").read_text(encoding="utf-8"))
            self.assertEqual(64, len(manifest["sha256"]))
            self.assertEqual(12, len(list((output / "pages").glob("page-*.png"))))


if __name__ == "__main__":
    unittest.main()
