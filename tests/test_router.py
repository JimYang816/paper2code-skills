"""Exercise the read-only Paper-to-Code lifecycle router."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from _tmp import TempDirectory


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "skills/setup-paper2code/scripts/setup.py"
CLI = ROOT / "skills/paper2code-core/scripts/paper2code.py"


NORMAL_ROUTES = {
    "setup_pending": "setup-paper2code",
    "ready_for_extraction": "extract-paper2code",
    "evidence_extracted": "paper-grilling",
    "evidence_approved": "paper-spec",
    "specification_ready": "paper-spec",
    "specification_approved": "implement",
    "implementation_active": "paper-validation",
    "cpu_validated": "paper-run",
    "full_run_approved": "paper-run",
    "full_run_complete": "paper-evaluation",
}


class RouterTests(unittest.TestCase):
    def run_cli(self, *args, expected=0):
        completed = subprocess.run(
            [sys.executable, str(CLI), *map(str, args)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(expected, completed.returncode, completed.stderr or completed.stdout)
        return json.loads(completed.stdout)

    def scaffold(self):
        temp = TempDirectory()
        self.addCleanup(temp.cleanup)
        target = Path(temp.name) / "paper"
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
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        return target

    def set_state(self, target, state, return_target=None):
        (target / ".paper2code/state.yaml").write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "state": state,
                    "return_target": return_target,
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def test_setup_pending_reports_a_ready_route_without_mutating_the_repository(self):
        target = self.scaffold()
        state_before = (target / ".paper2code/state.yaml").read_bytes()

        result = self.run_cli("route", "--root", target)

        self.assertTrue(result["valid"])
        self.assertEqual("setup_pending", result["state"]["state"])
        self.assertEqual("setup-paper2code", result["legal_next"][0]["skill"])
        self.assertEqual("ready_for_extraction", result["legal_next"][0]["target"])
        self.assertEqual(state_before, (target / ".paper2code/state.yaml").read_bytes())

    def test_every_normal_state_has_only_its_legal_next_stage_skill(self):
        target = self.scaffold()

        for state, skill in NORMAL_ROUTES.items():
            with self.subTest(state=state):
                self.set_state(target, state)
                result = self.run_cli("route", "--root", target)
                self.assertEqual(state, result["state"]["state"])
                self.assertEqual(skill, result["legal_next"][0]["skill"])
                self.assertTrue(result["legal_next"][0]["legal"])

        self.set_state(target, "evaluated")
        result = self.run_cli("route", "--root", target)
        self.assertEqual([], result["legal_next"])
        self.assertTrue(result["terminal"])

    def test_exception_states_expose_a_typed_return_target_and_diagnosis_route(self):
        target = self.scaffold()
        for state, return_target in {
            "needs_decision": "evidence_extracted",
            "diagnosing": "implementation_active",
            "revision_required": "full_run_complete",
        }.items():
            with self.subTest(state=state):
                self.set_state(target, state, return_target)
                result = self.run_cli("route", "--root", target)
                self.assertEqual(state, result["state"]["state"])
                self.assertEqual(return_target, result["state"]["return_target"])
                self.assertEqual("paper-diagnosis", result["legal_next"][0]["skill"])
                self.assertEqual(return_target, result["legal_next"][0]["return_target"])

    def test_invalid_current_artifacts_block_readiness_without_invoking_a_stage(self):
        target = self.scaffold()
        self.set_state(target, "evidence_extracted")

        result = self.run_cli("route", "--root", target)

        self.assertFalse(result["valid"])
        self.assertEqual("paper-grilling", result["legal_next"][0]["skill"])
        self.assertFalse(result["legal_next"][0]["ready"])
        self.assertTrue(result["validation_errors"])
        self.assertEqual("evidence_extracted", json.loads(
            (target / ".paper2code/state.yaml").read_text(encoding="utf-8")
        )["state"])


if __name__ == "__main__":
    unittest.main()
