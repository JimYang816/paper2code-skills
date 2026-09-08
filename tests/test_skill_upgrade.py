"""Exercise previewed, conflict-aware skill-closure upgrades."""

import hashlib
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from _tmp import TempDirectory


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "skills/setup-paper2code/scripts/setup.py"
UPGRADE = ROOT / "skills/update-paper2code-skills/scripts/update.py"


def content_hash(files):
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def inventory(directory):
    return {
        path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


class SkillUpgradeTests(unittest.TestCase):
    def run_upgrade(self, target, candidate, command, expected=0, approver=None):
        args = [
            sys.executable,
            str(UPGRADE),
            "--root",
            str(target),
            "--candidate-root",
            str(candidate),
            command,
        ]
        if approver:
            args.extend(["--approver", approver])
        completed = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
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

    def candidate(self, target):
        candidate = target.parent / "candidate"
        candidate.mkdir()
        shutil.copytree(ROOT / "skills", candidate / "skills", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(ROOT / "licenses", candidate / "licenses")
        for relative in ("skills-lock.yaml", "LICENSE", "THIRD_PARTY_NOTICES.md", ".gitattributes"):
            shutil.copy2(ROOT / relative, candidate / relative)
        return candidate

    def load_lock(self, root):
        return json.loads((root / "skills-lock.yaml").read_text(encoding="utf-8"))

    def refresh_skill_entry(self, lock, candidate, name):
        files = inventory(candidate / "skills" / name)
        lock["skills"][name]["files"] = files
        lock["skills"][name]["content_hash"] = content_hash(files)

    def save_lock(self, root, lock):
        (root / "skills-lock.yaml").write_text(
            json.dumps(lock, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )

    def test_preview_reports_content_and_provenance_changes(self):
        target = self.scaffold()
        candidate = self.candidate(target)
        skill_path = candidate / "skills/paper2code-router/SKILL.md"
        skill_path.write_text(skill_path.read_text(encoding="utf-8") + "\nPreviewed change.\n", encoding="utf-8")
        lock = self.load_lock(candidate)
        self.refresh_skill_entry(lock, candidate, "paper2code-router")
        lock["skills"]["update-paper2code-skills"]["dependencies"].append("paper2code-router")
        self.save_lock(candidate, lock)

        result = self.run_upgrade(target, candidate, "preview")

        self.assertEqual("preview", result["status"])
        self.assertIn("paper2code-router", [item["skill"] for item in result["changes"]])
        self.assertIn(
            "update-paper2code-skills",
            [item["skill"] for item in result["provenance_changes"]],
        )
        self.assertTrue((target / ".paper2code/skill-upgrade-preview.yaml").is_file())

    def test_preview_reports_additions_and_removals(self):
        target = self.scaffold()
        candidate = self.candidate(target)
        removed = "paper2code-router"
        shutil.rmtree(candidate / "skills" / removed)
        lock = self.load_lock(candidate)
        lock["skills"].pop(removed)
        lock["roots"].remove(removed)
        added = "candidate-skill"
        (candidate / "skills" / added).mkdir()
        (candidate / "skills" / added / "SKILL.md").write_text(
            "---\nname: candidate-skill\ndisable-model-invocation: true\n---\n\nCandidate.\n",
            encoding="utf-8",
        )
        files = inventory(candidate / "skills" / added)
        lock["skills"][added] = {
            "classification": "new",
            "origin": {"repository": "https://example.invalid/bundle", "path": "skills/candidate-skill"},
            "license": "MIT",
            "dependencies": ["paper2code-core"],
            "files": files,
            "content_hash": content_hash(files),
        }
        lock["roots"].append(added)
        self.save_lock(candidate, lock)

        result = self.run_upgrade(target, candidate, "preview")

        self.assertEqual([added], result["additions"])
        self.assertEqual([removed], result["removals"])

    def test_conflict_blocks_approval(self):
        target = self.scaffold()
        candidate = self.candidate(target)
        target_skill = target / "skills/paper2code-router/SKILL.md"
        target_skill.write_text(target_skill.read_text(encoding="utf-8") + "\nLocal change.\n", encoding="utf-8")
        candidate_skill = candidate / "skills/paper2code-router/SKILL.md"
        candidate_skill.write_text(candidate_skill.read_text(encoding="utf-8") + "\nCandidate change.\n", encoding="utf-8")
        lock = self.load_lock(candidate)
        self.refresh_skill_entry(lock, candidate, "paper2code-router")
        self.save_lock(candidate, lock)

        preview = self.run_upgrade(target, candidate, "preview")
        self.assertTrue(any(item["path"] == "skills/paper2code-router/SKILL.md" for item in preview["local_conflicts"]))
        result = self.run_upgrade(target, candidate, "approve", expected=2, approver="researcher@example.com")
        self.assertIn("conflict", result["error"].lower())
        self.assertIn("Local change", target_skill.read_text(encoding="utf-8"))

    def test_approved_upgrade_changes_only_the_skill_closure(self):
        target = self.scaffold()
        candidate = self.candidate(target)
        target_skill = target / "skills/paper2code-router/SKILL.md"
        candidate_skill = candidate / "skills/paper2code-router/SKILL.md"
        candidate_skill.write_text(candidate_skill.read_text(encoding="utf-8") + "\nApproved change.\n", encoding="utf-8")
        lock = self.load_lock(candidate)
        self.refresh_skill_entry(lock, candidate, "paper2code-router")
        self.save_lock(candidate, lock)
        scientific_record = target / "dossier/evidence.yaml"
        implementation = target / "implementation.py"
        scientific_record.write_text("record", encoding="utf-8")
        implementation.write_text("implementation", encoding="utf-8")

        self.run_upgrade(target, candidate, "preview")
        result = self.run_upgrade(
            target,
            candidate,
            "approve",
            approver="researcher@example.com",
        )

        self.assertEqual("applied", result["status"])
        self.assertEqual(candidate_skill.read_text(encoding="utf-8"), target_skill.read_text(encoding="utf-8"))
        self.assertEqual("record", scientific_record.read_text(encoding="utf-8"))
        self.assertEqual("implementation", implementation.read_text(encoding="utf-8"))
        self.assertEqual(
            (candidate / "skills-lock.yaml").read_bytes(),
            (target / "skills-lock.yaml").read_bytes(),
        )
        self.assertTrue((target / ".paper2code/skill-upgrade.yaml").is_file())


if __name__ == "__main__":
    unittest.main()
