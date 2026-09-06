import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "skills" / "setup-paper2code" / "scripts" / "setup.py"


class SetupCliTests(unittest.TestCase):
    def run_setup(self, target: Path, *args: str, env=None, expected: int = 0):
        completed = subprocess.run(
            [
                sys.executable,
                str(SETUP),
                "--target",
                str(target),
                "--bundle-root",
                str(ROOT),
                *args,
            ],
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(expected, completed.returncode, completed.stderr or completed.stdout)
        return json.loads(completed.stdout)

    def run_capabilities(self, output: Path | None = None):
        command = [sys.executable, str(SETUP.parent / "check_capabilities.py")]
        if output:
            command.extend(["--output", str(output)])
        return subprocess.run(command, cwd=ROOT, text=True, capture_output=True)

    def git(self, target: Path, *args: str):
        return subprocess.run(["git", *args], cwd=target, text=True, capture_output=True, check=True)

    def fake_gh(self, folder: Path) -> tuple[dict[str, str], Path]:
        env = os.environ.copy()
        if os.name == "nt":
            executable = folder / "gh.cmd"
            executable.write_text("@exit /b 0\n", encoding="utf-8")
        else:
            executable = folder / "gh"
            executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            executable.chmod(executable.stat().st_mode | stat.S_IEXEC)
        env["PAPER2CODE_GH"] = str(executable)
        return env, executable

    def test_plan_is_non_mutating(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "paper"
            result = self.run_setup(target)
            self.assertEqual("plan", result["mode"])
            self.assertFalse(target.exists())
            paths = {item["path"] for item in result["operations"]}
            self.assertIn(".gitignore", paths)
            self.assertIn(".paper2code/state.yaml", paths)
            self.assertIn("dossier/scope-matrix.yaml", paths)
            self.assertIn("skills-lock.yaml", paths)

    def test_apply_preserves_user_files_and_is_idempotent_without_remote(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "paper"
            target.mkdir()
            user_file = target / "notes.txt"
            user_file.write_text("mine", encoding="utf-8")
            first = self.run_setup(target, "--apply")
            self.assertEqual("setup_pending", first["state"])
            self.assertEqual("mine", user_file.read_text(encoding="utf-8"))
            self.assertTrue((target / ".git").is_dir())
            self.assertTrue((target / "skills" / "paper2code" / "SKILL.md").is_file())
            self.assertFalse((target / "skills" / "underwater-acoustics").exists())
            self.assertTrue((target / "dossier" / "scope-matrix.yaml").is_file())
            second = self.run_setup(target, "--apply")
            self.assertEqual([], second["conflicts"])
            self.assertEqual("mine", user_file.read_text(encoding="utf-8"))

    def test_existing_github_remote_and_gh_access_make_repository_ready(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            target = folder / "paper"
            target.mkdir()
            self.git(target, "init")
            self.git(target, "remote", "add", "origin", "https://github.com/example/paper.git")
            env, _ = self.fake_gh(folder)
            result = self.run_setup(target, "--apply", "--provision-labels", env=env)
            self.assertEqual("ready_for_extraction", result["state"])
            self.assertEqual(9, result["labels_provisioned"])
            state = yaml.safe_load((target / ".paper2code" / "state.yaml").read_text(encoding="utf-8"))
            self.assertEqual("ready_for_extraction", state["state"])

    def test_github_access_without_label_authorization_stays_pending(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            target = folder / "paper"
            target.mkdir()
            self.git(target, "init")
            self.git(target, "remote", "add", "origin", "https://github.com/example/paper.git")
            env, _ = self.fake_gh(folder)
            result = self.run_setup(target, "--apply", env=env)
            self.assertEqual("setup_pending", result["state"])
            self.assertTrue(result["github_ready"])

    def test_selected_profile_is_copied_and_locked(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "paper"
            result = self.run_setup(target, "--apply", "--profile", "underwater-acoustics")
            self.assertEqual("setup_pending", result["state"])
            self.assertTrue((target / "skills" / "underwater-acoustics" / "SKILL.md").is_file())
            lock = yaml.safe_load((target / "skills-lock.yaml").read_text(encoding="utf-8"))
            self.assertIn("underwater-acoustics", lock["skills"])

    def test_capability_check_can_write_recovery_oriented_report(self):
        with tempfile.TemporaryDirectory() as raw:
            output = Path(raw) / "capability-report.yaml"
            completed = self.run_capabilities(output)
            self.assertEqual(0, completed.returncode, completed.stderr)
            report = yaml.safe_load(output.read_text(encoding="utf-8"))
            self.assertEqual("setup-paper2code", report["stage"])
            self.assertIn("available", report)
            self.assertIn("missing", report)

    def test_plan_detects_a_managed_skill_conflict(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "paper"
            self.run_setup(target, "--apply")
            skill = target / "skills" / "setup-paper2code" / "SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + "\nlocal change\n", encoding="utf-8")
            result = self.run_setup(target)
            operations = {item["path"]: item["action"] for item in result["operations"]}
            self.assertEqual("conflict", operations["skills/setup-paper2code"])

    def test_invalid_scientific_record_template_blocks_scaffold(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "paper"
            self.run_setup(target, "--apply")
            scope = target / "dossier" / "scope-matrix.yaml"
            scope.write_text("claims: not-a-list\n", encoding="utf-8")
            preview = self.run_setup(target)
            operations = {item["path"]: item["action"] for item in preview["operations"]}
            self.assertEqual("conflict", operations["dossier/scope-matrix.yaml"])
            applied = self.run_setup(target, "--apply")
            self.assertFalse(applied["scaffold_valid"])
            self.assertIn("dossier/scope-matrix.yaml", applied["conflicts"])


if __name__ == "__main__":
    unittest.main()
