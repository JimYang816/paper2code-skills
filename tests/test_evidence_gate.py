"""Exercise the Evidence Gate, ambiguity resolution, and paper-grilling CLI."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from _tmp import TempDirectory


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "skills/setup-paper2code/scripts/setup.py"
CORE = ROOT / "skills/paper2code-core/scripts/paper2code.py"
GATE = ROOT / "skills/paper-grilling/scripts/gate.py"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def make_dossier(target, ambiguities):
    (target / "dossier/figures").mkdir(parents=True, exist_ok=True)
    (target / "dossier/paper.md").write_text(
        "# Paper Dossier\n\n"
        "## Source\n\nsource\n\n"
        "## Evidence\n\nevidence.yaml\n\n"
        "## Figures\n\nfigures\n\n"
        "## Audit\n\naudit.yaml\n",
        encoding="utf-8",
    )
    write_json(target / "dossier/evidence.yaml", {"schema_version": "1.0", "items": []})
    write_json(
        target / "dossier/audit.yaml",
        {
            "schema_version": "1.0",
            "generated_at": "2026-09-07T00:00:00+00:00",
            "items": [],
            "summary": {"total": 0, "open": 0, "triaged": 0},
        },
    )
    write_json(target / "dossier/ambiguities.yaml", ambiguities)


def make_ambiguity(number, scope="must", status="open", resolution=None):
    item = {
        "id": f"AMB-{number:04d}",
        "scope": scope,
        "question": f"Question {number}",
        "evidence_ids": [],
        "status": status,
    }
    if resolution is not None:
        item["resolution"] = resolution
    return item


class EvidenceGateTests(unittest.TestCase):
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
        return target

    def set_state(self, target, state):
        write_json(
            target / ".paper2code/state.yaml",
            {"schema_version": "1.0", "state": state, "return_target": None},
        )

    def run_core(self, *args, expected=0):
        completed = subprocess.run(
            [sys.executable, str(CORE), *map(str, args)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(expected, completed.returncode, completed.stderr or completed.stdout)
        return completed

    def run_gate(self, target, *args, expected=0):
        completed = subprocess.run(
            [sys.executable, str(GATE), "--root", str(target), *map(str, args)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(expected, completed.returncode, completed.stderr or completed.stdout)
        return completed

    def test_validate_ambiguities_rejects_open_must_scope(self):
        target = self.scaffold()
        make_dossier(
            target,
            {
                "schema_version": "1.0",
                "ambiguities": [make_ambiguity(1)],
            },
        )
        result = self.run_core("validate-ambiguities", "--root", target, expected=2)
        self.assertIn("unresolved must-scope ambiguity", result.stderr)

    def test_validate_ambiguities_accepts_terminal_resolutions(self):
        target = self.scaffold()
        make_dossier(
            target,
            {
                "schema_version": "1.0",
                "ambiguities": [
                    make_ambiguity(
                        1,
                        status="resolved",
                        resolution={
                            "kind": "reconstructed",
                            "basis": "Researcher decision",
                            "evidence_ids": [],
                            "decision_ids": ["DEC-0001"],
                        },
                    )
                ],
            },
        )
        result = self.run_core("validate-ambiguities", "--root", target)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual(1, payload["must_total"])

    def test_validate_ambiguities_rejects_resolved_must_without_resolution(self):
        target = self.scaffold()
        make_dossier(
            target,
            {
                "schema_version": "1.0",
                "ambiguities": [make_ambiguity(1, status="resolved", resolution=None)],
            },
        )
        result = self.run_core("validate-ambiguities", "--root", target, expected=2)
        self.assertIn("missing a resolution", result.stderr)

    def test_approve_records_a_hash_bound_gate_and_advances_state(self):
        target = self.scaffold()
        make_dossier(
            target,
            {
                "schema_version": "1.0",
                "ambiguities": [
                    make_ambiguity(
                        1,
                        status="resolved",
                        resolution={
                            "kind": "confirmed",
                            "basis": "Paper evidence",
                            "evidence_ids": ["EVID-0001"],
                            "decision_ids": [],
                        },
                    )
                ],
            },
        )
        self.set_state(target, "evidence_extracted")

        result = self.run_gate(target, "approve", "--approver", "researcher@example.com")
        payload = json.loads(result.stdout)
        self.assertEqual("evidence_approved", payload["state"])
        self.assertTrue((target / ".paper2code/gates/evidence-gate.yaml").is_file())

        gate = json.loads((target / ".paper2code/gates/evidence-gate.yaml").read_text(encoding="utf-8"))
        self.assertEqual("researcher@example.com", gate["approved_by"])
        self.assertEqual("evidence_extracted -> evidence_approved", gate["transition"])
        self.assertIn("dossier/ambiguities.yaml", gate["artifacts"])

    def test_validate_wayfinding_requires_known_ambiguity_ids(self):
        target = self.scaffold()
        make_dossier(
            target,
            {
                "schema_version": "1.0",
                "ambiguities": [make_ambiguity(1)],
            },
        )
        write_json(
            target / "decisions/frontier.yaml",
            {
                "schema_version": "1.0",
                "ambiguities": [
                    {
                        "id": "AMB-0001",
                        "work": [
                            {
                                "id": "AMB-0001:decision",
                                "kind": "decision",
                                "title": "Choose a model",
                                "issue": None,
                            }
                        ],
                    }
                ],
                "frontier": [
                    {
                        "id": "AMB-0001:decision",
                        "kind": "decision",
                        "title": "Choose a model",
                        "issue": None,
                        "blocked_by": [],
                    }
                ],
            },
        )
        result = self.run_core("validate-wayfinding", "--root", target)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual(1, payload["mapped_ambiguities"])

        write_json(
            target / "decisions/frontier.yaml",
            {
                "schema_version": "1.0",
                "ambiguities": [
                    {
                        "id": "AMB-9999",
                        "work": [],
                    }
                ],
                "frontier": [],
            },
        )
        result = self.run_core("validate-wayfinding", "--root", target, expected=2)
        self.assertIn("AMB-9999", result.stderr)

    def test_approve_refuses_when_a_must_ambiguity_is_open(self):
        target = self.scaffold()
        make_dossier(
            target,
            {
                "schema_version": "1.0",
                "ambiguities": [make_ambiguity(1)],
            },
        )
        self.set_state(target, "evidence_extracted")
        result = self.run_gate(
            target, "approve", "--approver", "researcher@example.com", expected=2
        )
        self.assertIn("unresolved must-scope ambiguity", result.stderr)
        state = json.loads((target / ".paper2code/state.yaml").read_text(encoding="utf-8"))
        self.assertEqual("evidence_extracted", state["state"])

    def test_verify_gate_detects_stale_artifacts(self):
        target = self.scaffold()
        make_dossier(
            target,
            {
                "schema_version": "1.0",
                "ambiguities": [
                    make_ambiguity(
                        1,
                        status="resolved",
                        resolution={
                            "kind": "excluded",
                            "basis": "Out of scope",
                            "evidence_ids": [],
                            "decision_ids": [],
                        },
                    )
                ],
            },
        )
        self.set_state(target, "evidence_extracted")
        self.run_gate(target, "approve", "--approver", "researcher@example.com")

        evidence = target / "dossier/evidence.yaml"
        evidence.write_text(
            '{"schema_version":"1.0","items":[{"id":"EVID-0001","class":"parameter",'
            '"text":"learning_rate=0.1","provenance":"paper_evidence",'
            '"confidence":"confirmed","status":"triaged","locator":{"page":1,"text":"x"},'
            '"units":"dimensionless","dependencies":[]}]}\n',
            encoding="utf-8",
        )
        result = self.run_gate(target, "verify-gate", expected=2)
        self.assertIn("stale", result.stderr)


if __name__ == "__main__":
    unittest.main()
