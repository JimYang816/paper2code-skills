"""Exercise the paper specification and Specification Gate."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from _tmp import TempDirectory


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "skills/setup-paper2code/scripts/setup.py"
CORE = ROOT / "skills/paper2code-core/scripts/paper2code.py"
EVIDENCE_GATE = ROOT / "skills/paper-grilling/scripts/gate.py"
SPEC = ROOT / "skills/paper-spec/scripts/spec.py"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def make_scope():
    return {
        "schema_version": "1.0",
        "claims": [
            {
                "id": "CLM-0001",
                "title": "Reproduce the learned equalizer",
                "class": "method",
                "scope": "must",
                "evidence_ids": [],
                "ambiguity_ids": [],
                "rationale": "The paper reports the learned equalizer as its primary result.",
            }
        ],
    }


def make_dossier(target, ambiguities=None, scope=None):
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
    write_json(
        target / "dossier/ambiguities.yaml",
        ambiguities or {"schema_version": "1.0", "ambiguities": []},
    )
    write_json(target / "dossier/scope-matrix.yaml", scope or make_scope())


def make_ambiguity():
    return {
        "schema_version": "1.0",
        "ambiguities": [
            {
                "id": "AMB-0001",
                "scope": "must",
                "question": "Choose the reconstruction detail",
                "evidence_ids": [],
                "status": "resolved",
                "resolution": {
                    "kind": "reconstructed",
                    "basis": "Researcher decision",
                    "evidence_ids": [],
                    "decision_ids": ["DEC-0001"],
                },
            }
        ],
    }


def make_spec_item(prefix, number, scope="must"):
    return {
        "id": f"{prefix}-{number:04d}",
        "title": f"{prefix} item {number}",
        "scope": scope,
        "specification": "Complete specification text.",
        "evidence_ids": [],
        "decision_ids": [],
        "acceptance": "Independent checks pass.",
    }


def make_specification(scope=None):
    scope_claims = (scope or make_scope())["claims"]
    return {
        "schema_version": "1.0",
        "scope": {"claims": scope_claims},
        "method": [make_spec_item("MTH", 1)],
        "data": [make_spec_item("DATA", 1)],
        "baselines": [make_spec_item("BASE", 1)],
        "experiments": [make_spec_item("EXP", 1)],
        "figures": [make_spec_item("FIG", 1)],
        "metrics": [
            {
                "id": "MET-0001",
                "title": "Symbol error rate",
                "scope": "must",
                "specification": "Fraction of incorrectly detected symbols.",
                "evidence_ids": [],
                "decision_ids": [],
                "acceptance": "Numerical reference matches.",
                "unit": "dimensionless",
                "higher_is_better": False,
            }
        ],
        "uncertainty": {
            "digitization": "Report extraction uncertainty for paper curves.",
            "statistical": "Use three seeds and report variability.",
        },
        "budget": {
            "compute": "Reduced deterministic CPU configuration.",
            "seeds": "3",
            "notes": "",
        },
        "acceptance": {
            "rules": [
                {
                    "id": "ACC-0001",
                    "claim_ids": ["CLM-0001"],
                    "metric_id": "MET-0001",
                    "criterion": "SER matches the digitized paper curve.",
                    "tolerance": "Within approved digitization uncertainty.",
                    "scope": "must",
                }
            ]
        },
    }


def make_paper_spec():
    return (
        "# Paper Specification\n\n"
        "## Scope\n\nReproduce the primary learned equalizer result.\n\n"
        "## Method\n\nLearned unfolding equalizer.\n\n"
        "## Data\n\nSource-faithful channel replay.\n\n"
        "## Baselines\n\nZF and MMSE.\n\n"
        "## Experiments\n\nReduced CPU matrix.\n\n"
        "## Figures\n\nPrimary SER curve.\n\n"
        "## Metrics\n\nSymbol error rate.\n\n"
        "## Uncertainty\n\nDigitization and seed variability.\n\n"
        "## Budget\n\nReduced deterministic CPU.\n\n"
        "## Acceptance\n\nApproved tolerances.\n"
    )


class SpecificationTests(unittest.TestCase):
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

    def run_spec(self, target, *args, expected=0):
        completed = subprocess.run(
            [sys.executable, str(SPEC), "--root", str(target), *map(str, args)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(expected, completed.returncode, completed.stderr or completed.stdout)
        return completed

    def establish_evidence_gate(self, target):
        make_dossier(target, ambiguities=make_ambiguity(), scope=make_scope())
        self.set_state(target, "evidence_extracted")
        completed = subprocess.run(
            [
                sys.executable,
                str(EVIDENCE_GATE),
                "--root",
                str(target),
                "approve",
                "--approver",
                "researcher@example.com",
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)

    def write_spec_artifacts(self, target, specification=None, scope=None):
        write_json(
            target / "decisions/frontier.yaml",
            {"schema_version": "1.0", "ambiguities": [], "frontier": []},
        )
        write_json(
            target / "specification/specification.yaml",
            specification or make_specification(scope=scope),
        )
        (target / "specification/paper-spec.md").write_text(make_paper_spec(), encoding="utf-8")
        write_json(
            target / "contracts/baselines/BASE-0001.yaml",
            {"schema_version": "1.0", "name": "ZF", "specification": "Linear equalizer."},
        )

    def test_prepare_and_approve_advance_state_and_bind_hashes(self):
        target = self.scaffold()
        self.establish_evidence_gate(target)
        self.write_spec_artifacts(target)

        prepared = self.run_spec(target, "prepare")
        payload = json.loads(prepared.stdout)
        self.assertEqual("specification_ready", payload["state"])
        state = json.loads((target / ".paper2code/state.yaml").read_text(encoding="utf-8"))
        self.assertEqual("specification_ready", state["state"])

        approved = self.run_spec(target, "approve", "--approver", "researcher@example.com")
        payload = json.loads(approved.stdout)
        self.assertEqual("specification_approved", payload["state"])
        gate = json.loads(
            (target / ".paper2code/gates/specification-gate.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual("researcher@example.com", gate["approved_by"])
        self.assertEqual("specification_ready -> specification_approved", gate["transition"])
        self.assertIn("specification/specification.yaml", gate["artifacts"])
        self.assertIn("contracts/baselines/BASE-0001.yaml", gate["artifacts"])
        self.assertIn("scope", gate["schemas"])
        self.assertIn("specification", gate["schemas"])

    def test_approve_refuses_stale_evidence_gate(self):
        target = self.scaffold()
        self.establish_evidence_gate(target)
        self.write_spec_artifacts(target)
        self.run_spec(target, "prepare")

        evidence = target / "dossier/evidence.yaml"
        write_json(
            evidence,
            {
                "schema_version": "1.0",
                "items": [
                    {
                        "id": "EVID-0001",
                        "class": "parameter",
                        "text": "learning_rate=0.1",
                        "provenance": "paper_evidence",
                        "confidence": "confirmed",
                        "status": "triaged",
                        "locator": {"page": 1, "text": "training details"},
                        "units": "dimensionless",
                        "dependencies": [],
                    }
                ],
            },
        )
        result = self.run_spec(target, "approve", "--approver", "researcher@example.com", expected=2)
        self.assertIn("stale Evidence Gate", result.stderr)

    def test_validate_specification_rejects_unresolved_must_value(self):
        target = self.scaffold()
        self.establish_evidence_gate(target)
        specification = make_specification()
        specification["method"][0]["specification"] = "TBD"
        self.write_spec_artifacts(target, specification=specification)
        result = self.run_core("validate-specification", "--root", target, expected=2)
        self.assertIn("MTH-0001", result.stderr)

    def test_validate_specification_rejects_unknown_acceptance_metric(self):
        target = self.scaffold()
        self.establish_evidence_gate(target)
        specification = make_specification()
        specification["acceptance"]["rules"][0]["metric_id"] = "MET-9999"
        self.write_spec_artifacts(target, specification=specification)
        result = self.run_core("validate-specification", "--root", target, expected=2)
        self.assertIn("MET-9999", result.stderr)

    def test_verify_gate_detects_stale_specification(self):
        target = self.scaffold()
        self.establish_evidence_gate(target)
        self.write_spec_artifacts(target)
        self.run_spec(target, "prepare")
        self.run_spec(target, "approve", "--approver", "researcher@example.com")

        changed = make_specification()
        changed["method"][0]["specification"] = "Changed after approval."
        write_json(target / "specification/specification.yaml", changed)
        result = self.run_spec(target, "verify-gate", expected=2)
        self.assertIn("stale", result.stderr)

    def test_validate_scope_matrix_rejects_open_must_claim(self):
        target = self.scaffold()
        self.establish_evidence_gate(target)
        scope = make_scope()
        scope["claims"][0]["rationale"] = "open"
        write_json(target / "dossier/scope-matrix.yaml", scope)
        result = self.run_core("validate-scope-matrix", "--root", target, expected=2)
        self.assertIn("CLM-0001", result.stderr)


if __name__ == "__main__":
    unittest.main()
