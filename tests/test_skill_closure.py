"""Exercise the public verifier CLI against isolated distribution copies."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

from _tmp import TempDirectory


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "skills/paper2code-core/scripts/verify_closure.py"


class ClosureTests(unittest.TestCase):
    def setUp(self):
        self.temp = TempDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("skills", "licenses"):
            shutil.copytree(ROOT / name, self.root / name)
        for name in ("skills-lock.yaml", "LICENSE", "THIRD_PARTY_NOTICES.md", ".gitattributes"):
            shutil.copyfile(ROOT / name, self.root / name)

    def run_cli(self):
        return subprocess.run([sys.executable, str(CLI), "--root", str(self.root)],
                              capture_output=True, text=True)

    def change_lock(self, change):
        path = self.root / "skills-lock.yaml"
        lock = json.loads(path.read_text(encoding="utf-8"))
        change(lock)
        path.write_text(json.dumps(lock), encoding="utf-8")

    def assert_invalid(self, expected):
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(expected, result.stderr)

    def test_portable_copy_passes_offline(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(shutil.which("git"), "Git required for checkout portability")
    def test_consumer_git_checkout_preserves_locked_bytes(self):
        with TempDirectory() as checkout:
            checkout = Path(checkout)
            for args in (("init",), ("add", "."),
                         ("checkout-index", "--all", "--prefix=" + Path(checkout).as_posix() + "/")):
                subprocess.run(["git", "-C", str(self.root), "-c", "core.autocrlf=true", *args],
                               check=True, capture_output=True)
            result = subprocess.run([sys.executable, str(CLI), "--root", checkout],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_changed_reference_fails(self):
        path = self.root / "skills/tdd/tests.md"
        path.write_bytes(path.read_bytes() + b"\nchanged\n")
        self.assert_invalid("hash mismatch: tdd")

    def test_missing_resource_fails(self):
        (self.root / "skills/diagnosing-bugs/scripts/hitl-loop.template.sh").unlink()
        self.assert_invalid("hash mismatch: diagnosing-bugs")

    def test_missing_transitive_dependency_fails(self):
        self.change_lock(lambda lock: lock["skills"].pop("setup-matt-pocock-skills"))
        self.assert_invalid("Missing dependency: setup-matt-pocock-skills")

    def test_unrelated_locked_skill_fails(self):
        self.change_lock(lambda lock: lock["skills"].update(unrelated=lock["skills"]["grilling"]))
        self.assert_invalid("Unrelated skills")

    def test_unlisted_skill_fails(self):
        (self.root / "skills/unrelated").mkdir()
        self.assert_invalid("directory inventory")

    def test_unlisted_resource_fails(self):
        (self.root / "skills/grilling/extra.txt").write_text("unexpected")
        self.assert_invalid("hash mismatch: grilling")

    def test_license_change_fails(self):
        (self.root / "licenses/mattpocock-skills-LICENSE").write_text("removed")
        self.assert_invalid("Distribution file mismatch")

    def test_unknown_classification_fails(self):
        self.change_lock(lambda lock: lock["skills"]["grilling"].update(classification="unknown"))
        self.assert_invalid("Invalid classification")

    def test_source_hash_tampering_fails(self):
        self.change_lock(lambda lock: lock["skills"]["grilling"].update(source_hash="0" * 64))
        self.assert_invalid("Source hash mismatch")

    def test_unpinned_source_fails(self):
        self.change_lock(lambda lock: lock["skills"]["grilling"]["origin"].update(revision="main"))
        self.assert_invalid("Unpinned revision")

    def test_malformed_lock_fails_cleanly(self):
        (self.root / "skills-lock.yaml").write_text("invalid YAML")
        self.assert_invalid("INVALID:")


if __name__ == "__main__":
    unittest.main()
