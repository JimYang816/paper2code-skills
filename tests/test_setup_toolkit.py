"""Exercise the standard-library Deterministic Toolkit setup commands."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from _tmp import TempDirectory


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "skills/setup-paper2code/scripts/setup.py"
CLI = ROOT / "skills/paper2code-core/scripts/paper2code.py"


class SetupToolkitTests(unittest.TestCase):
    def run_cli(self, *args, expected=0):
        completed = subprocess.run(
            [sys.executable, str(CLI), *map(str, args)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(expected, completed.returncode, completed.stderr or completed.stdout)
        return completed

    def scaffold(self):
        temp = TempDirectory()
        self.addCleanup(temp.cleanup)
        target = Path(temp.name) / "paper"
        subprocess.run(
            [sys.executable, str(SETUP), "--target", str(target), "--bundle-root", str(ROOT), "--apply"],
            text=True,
            capture_output=True,
            check=True,
        )
        return target

    def write_json(self, path, value):
        path.write_text(
            json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        return path

    def test_canonical_hash_is_stable_across_key_order(self):
        with TempDirectory() as raw:
            folder = Path(raw)
            first = self.write_json(folder / "a.json", {"b": 2, "a": {"y": 1, "x": 0}})
            second = self.write_json(folder / "b.json", {"a": {"x": 0, "y": 1}, "b": 2})
            first_hash = json.loads(self.run_cli("canonical-hash", first).stdout)["sha256"]
            second_hash = json.loads(self.run_cli("canonical-hash", second).stdout)["sha256"]
            self.assertEqual(first_hash, second_hash)

    def test_verify_hash_accepts_or_rejects_canonical_hashes(self):
        with TempDirectory() as raw:
            document = self.write_json(Path(raw) / "record.json", {"schema_version": "1.0", "items": []})
            expected = json.loads(self.run_cli("canonical-hash", document).stdout)["sha256"]
            self.run_cli("verify-hash", document, "--expected", expected)
            result = self.run_cli("verify-hash", document, "--expected", "0" * 64, expected=2)
            self.assertIn("Hash mismatch", result.stderr)

    def test_transition_check_handles_normal_and_typed_exception_states(self):
        with TempDirectory() as raw:
            state = self.write_json(
                Path(raw) / "state.json",
                {"schema_version": "1.0", "state": "evidence_extracted", "return_target": None},
            )
            self.run_cli("check-transition", state, "--to", "evidence_approved")
            result = self.run_cli("check-transition", state, "--to", "evaluated", expected=2)
            self.assertIn("Illegal workflow transition", result.stderr)
            self.run_cli(
                "check-transition",
                state,
                "--to",
                "needs_decision",
                "--return-target",
                "evidence_extracted",
            )

    def test_validate_setup_accepts_a_scaffold(self):
        target = self.scaffold()
        result = self.run_cli("validate-setup", "--root", target)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual("setup_pending", payload["state"])

    def test_validate_setup_rejects_invalid_state(self):
        target = self.scaffold()
        state_path = target / ".paper2code/state.yaml"
        self.write_json(state_path, {"schema_version": "1.0", "state": "made_up", "return_target": None})
        result = self.run_cli("validate-setup", "--root", target, expected=2)
        self.assertIn("made_up", result.stderr)

    def test_validate_setup_rejects_a_modified_skill(self):
        target = self.scaffold()
        skill = target / "skills/tdd/SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\nlocal change\n", encoding="utf-8")
        result = self.run_cli("validate-setup", "--root", target, expected=2)
        self.assertIn("tdd", result.stderr)


if __name__ == "__main__":
    unittest.main()
