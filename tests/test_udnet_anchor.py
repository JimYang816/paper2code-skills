import subprocess
import sys
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "skills" / "paper2code-core" / "scripts" / "paper2code.py"
ANCHOR = ROOT / "skills" / "underwater-acoustics" / "assets" / "udnet-v1"


class UdnetAnchorTests(unittest.TestCase):
    def validate(self, path: Path, schema: str):
        completed = subprocess.run(
            [sys.executable, str(CLI), "validate", str(path), "--schema", schema],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_scope_matrix_encodes_the_agreed_m0_through_m2_boundary(self):
        path = ANCHOR / "scope-matrix.yaml"
        self.validate(path, "scope-matrix")
        claims = yaml.safe_load(path.read_text(encoding="utf-8"))["claims"]
        must = {claim["claim_id"] for claim in claims if claim["scope"] == "must"}
        out = {claim["claim_id"] for claim in claims if claim["scope"] == "out"}
        self.assertIn("M1-WATERMARK", must)
        self.assertIn("M1-SIM-B", must)
        self.assertIn("OUT-NANPENG", out)

    def test_dataset_contracts_preserve_source_fidelity_and_exclusions(self):
        for path in (ANCHOR / "datasets").glob("*.yaml"):
            self.validate(path, "dataset-manifest")
        watermark = (ANCHOR / "datasets" / "watermark-nof-ncs.yaml").read_text(encoding="utf-8")
        sim_b = (ANCHOR / "datasets" / "bellhop-sim-b.yaml").read_text(encoding="utf-8")
        nanpeng = (ANCHOR / "datasets" / "nanpeng-noise.yaml").read_text(encoding="utf-8")
        self.assertIn("Reference Oracle", watermark)
        self.assertIn("source-faithful reconstruction", sim_b)
        self.assertIn("Do not substitute synthetic noise", nanpeng)


if __name__ == "__main__":
    unittest.main()
