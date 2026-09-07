"""Exercise setup-paper2code in isolated repositories without third-party imports."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from _tmp import TempDirectory


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "skills/setup-paper2code/scripts/setup.py"


class SetupTests(unittest.TestCase):
    def run_setup(self, target, *args, env=None, expected=0):
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

    def git(self, target, *args):
        subprocess.run(["git", *args], cwd=target, text=True, capture_output=True, check=True)

    def fake_gh(self, folder):
        env = os.environ.copy()
        if os.name == "nt":
            executable = folder / "gh.cmd"
            executable.write_text("@exit /b 0\n", encoding="utf-8")
        else:
            executable = folder / "gh"
            executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            executable.chmod(0o755)
        env["PAPER2CODE_GH"] = str(executable)
        return env

    def missing_gh(self):
        env = os.environ.copy()
        env["PAPER2CODE_GH"] = str(ROOT / ".scratch/missing-gh.exe")
        return env

    def test_plan_is_non_mutating(self):
        with TempDirectory() as raw:
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
        with TempDirectory() as raw:
            target = Path(raw) / "paper"
            target.mkdir()
            user_file = target / "notes.txt"
            user_file.write_text("mine", encoding="utf-8")

            first = self.run_setup(target, "--apply")
            self.assertEqual("setup_pending", first["state"])
            self.assertEqual("mine", user_file.read_text(encoding="utf-8"))
            self.assertTrue((target / ".git").is_dir())
            self.assertTrue((target / "skills/setup-paper2code/SKILL.md").is_file())
            self.assertTrue((target / "dossier/scope-matrix.yaml").is_file())
            self.assertFalse(first["github_ready"])

            second = self.run_setup(target, "--apply")
            self.assertEqual([], second["conflicts"])
            self.assertEqual("mine", user_file.read_text(encoding="utf-8"))
            self.assertEqual("setup_pending", second["state"])

    def test_existing_github_remote_and_gh_access_make_repository_ready(self):
        with TempDirectory() as raw:
            folder = Path(raw)
            target = folder / "paper"
            target.mkdir()
            self.git(target, "init")
            self.git(target, "remote", "add", "origin", "https://github.com/example/paper.git")

            result = self.run_setup(target, "--apply", "--provision-labels", env=self.fake_gh(folder))
            self.assertEqual("ready_for_extraction", result["state"])
            self.assertEqual(9, result["labels_provisioned"])
            self.assertTrue(result["github_ready"])
            self.assertTrue(result["scaffold_valid"])

    def test_missing_gh_writes_capability_report_and_stays_pending(self):
        with TempDirectory() as raw:
            target = Path(raw) / "paper"
            target.mkdir()
            self.git(target, "init")
            self.git(target, "remote", "add", "origin", "https://github.com/example/paper.git")

            result = self.run_setup(target, "--apply", env=self.missing_gh())
            self.assertEqual("setup_pending", result["state"])
            self.assertFalse(result["github_ready"])
            report = json.loads(Path(result["capability_report"]).read_text(encoding="utf-8"))
            self.assertEqual("setup-paper2code", report["stage"])
            self.assertIn("GitHub CLI", [item["name"] for item in report["missing"]])
            self.assertFalse((target / "docs/agents/issue-tracker-local.md").exists())

    def test_plan_detects_a_managed_skill_conflict(self):
        with TempDirectory() as raw:
            target = Path(raw) / "paper"
            self.run_setup(target, "--apply")
            skill = target / "skills/setup-paper2code/SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + "\nlocal change\n", encoding="utf-8")

            result = self.run_setup(target)
            actions = {item["path"]: item["action"] for item in result["operations"]}
            self.assertEqual("conflict", actions["skills/setup-paper2code"])

    def test_invalid_scientific_record_template_blocks_scaffold(self):
        with TempDirectory() as raw:
            target = Path(raw) / "paper"
            self.run_setup(target, "--apply")
            scope = target / "dossier/scope-matrix.yaml"
            scope.write_text('{"schema_version":"1.0","claims":"not-a-list"}\n', encoding="utf-8")

            preview = self.run_setup(target)
            actions = {item["path"]: item["action"] for item in preview["operations"]}
            self.assertEqual("conflict", actions["dossier/scope-matrix.yaml"])

            applied = self.run_setup(target, "--apply")
            self.assertFalse(applied["scaffold_valid"])
            self.assertIn("dossier/scope-matrix.yaml", applied["conflicts"])

    def test_gitignore_merge_preserves_existing_rules(self):
        with TempDirectory() as raw:
            target = Path(raw) / "paper"
            target.mkdir()
            ignore = target / ".gitignore"
            ignore.write_text("node_modules/\n", encoding="utf-8")

            self.run_setup(target, "--apply")
            content = ignore.read_text(encoding="utf-8")
            self.assertTrue(content.startswith("node_modules/\n"))
            self.assertIn("# Paper-to-Code large or restricted artifacts", content)


if __name__ == "__main__":
    unittest.main()
