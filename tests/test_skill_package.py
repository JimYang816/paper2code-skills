"""Check published skill interfaces independently of their locked hashes."""

import json
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]


class SkillPackageTests(unittest.TestCase):
    def test_entrypoints_have_names_descriptions_and_invocation_policy(self):
        lock = json.loads((ROOT / "skills-lock.yaml").read_text())
        for name in lock["skills"]:
            with self.subTest(skill=name):
                text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
                parts = text.split("---", 2)
                self.assertEqual("", parts[0])
                self.assertEqual(3, len(parts))
                fields = dict(re.findall(r"^([a-z-]+):\s*(.+)$", parts[1], re.MULTILINE))
                self.assertEqual(name, fields.get("name"))
                self.assertTrue(fields.get("description", "").strip('"\''))
                if name.startswith("paper-") or name in {
                    "setup-paper2code", "extract-paper2code", "update-paper2code-skills",
                    "paper2code-router",
                }:
                    self.assertEqual("true", fields.get("disable-model-invocation"))
                self.assertTrue(parts[2].strip())

    def test_relative_markdown_resources_exist_in_distribution(self):
        for path in (ROOT / "skills").rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            # Code examples contain illustrative links, not package dependencies.
            text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
            for link in re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", text):
                parsed = urlsplit(link)
                if parsed.scheme or not parsed.path or parsed.path.startswith("/"):
                    continue
                with self.subTest(file=str(path.relative_to(ROOT)), link=link):
                    target = (path.parent / unquote(parsed.path)).resolve()
                    self.assertTrue(target.is_relative_to(ROOT))
                    self.assertTrue(target.exists(), str(target))


if __name__ == "__main__":
    unittest.main()
