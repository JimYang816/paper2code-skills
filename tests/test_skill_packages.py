import re
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
STAGE_SKILLS = {
    "paper2code",
    "setup-paper2code",
    "extract-paper",
    "grill-paper",
    "paper-wayfinder",
    "scientific-prototype",
    "specify-paper",
    "scientific-validation",
    "cpu-validate",
    "prepare-full-run",
    "execute-full-run",
    "evaluate-reproduction",
    "diagnose-reproduction",
    "update-paper2code-skills",
}
UPSTREAM = {
    "grilling",
    "domain-modeling",
    "research",
    "to-tickets",
    "implement",
    "tdd",
    "codebase-design",
    "code-review",
    "diagnosing-bugs",
}


class SkillPackageTests(unittest.TestCase):
    def parse_frontmatter(self, path: Path) -> tuple[dict, str]:
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
        self.assertIsNotNone(match, path)
        return yaml.safe_load(match.group(1)), match.group(2)

    def test_required_skill_closure_exists(self):
        present = {path.name for path in SKILLS.iterdir() if path.is_dir()}
        self.assertTrue(STAGE_SKILLS <= present)
        self.assertTrue(UPSTREAM <= present)
        self.assertIn("paper2code-core", present)
        self.assertIn("underwater-acoustics", present)

    def test_stage_skills_are_explicitly_invoked_and_have_no_scaffolding(self):
        unfinished = re.compile(r"TODO|TBD|\[TODO|coming soon", re.I)
        for name in STAGE_SKILLS:
            frontmatter, body = self.parse_frontmatter(SKILLS / name / "SKILL.md")
            self.assertEqual(name, frontmatter["name"])
            self.assertTrue(frontmatter.get("disable-model-invocation"), name)
            self.assertFalse(unfinished.search(body), name)

    def test_local_markdown_references_resolve(self):
        for skill_file in SKILLS.glob("*/SKILL.md"):
            text = skill_file.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^]]+\]\(([^)#]+)(?:#[^)]+)?\)", text):
                if "://" in target or target.startswith("/"):
                    continue
                resolved = (skill_file.parent / target).resolve()
                self.assertTrue(resolved.exists(), f"{skill_file}: missing {target}")

    def test_contract_schemas_are_versioned(self):
        schemas = list((SKILLS / "paper2code-core" / "references" / "schemas" / "v1").glob("*.schema.json"))
        self.assertGreaterEqual(len(schemas), 8)
        for path in schemas:
            self.assertIn("/v1/", path.as_posix())
            self.assertIn('"$schema"', path.read_text(encoding="utf-8"))

    def test_upstream_skills_match_the_inventory_hashes(self):
        import hashlib

        inventory = yaml.safe_load((ROOT / "skills-lock.yaml").read_text(encoding="utf-8"))
        for name in UPSTREAM:
            expected = inventory["skills"][name]["content_hash"]
            digest = hashlib.sha256()
            folder = SKILLS / name
            for path in sorted(p for p in folder.rglob("*") if p.is_file()):
                digest.update(path.relative_to(folder).as_posix().encode())
                digest.update(b"\0")
                digest.update(path.read_bytes())
                digest.update(b"\0")
            self.assertEqual(expected, digest.hexdigest(), name)


if __name__ == "__main__":
    unittest.main()
