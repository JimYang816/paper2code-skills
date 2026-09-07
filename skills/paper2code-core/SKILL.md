---
name: paper2code-core
description: Verify the pinned Skill Closure and validate deterministic Paper-to-Code artifacts.
---

Run `python skills/paper2code-core/scripts/verify_closure.py --root .` from
the Skill Bundle Repository root. A nonzero exit means the bundle is incomplete
or differs from its lock; resolve the reported differences before copying it.

For source verification, add `--upstream /path/to/mattpocock-skills-checkout`.
The verifier reads Git objects at the locked revision without changing that checkout.
See [the closure contract](references/skill-closure.md) for copying and provenance rules.

To validate extracted dossier artifacts in a Reproduction Repository, run
`python skills/paper2code-core/scripts/paper2code.py validate-dossier --root .`.
This command checks the Markdown dossier, `evidence.yaml`, `audit.yaml`, and
their versioned JSON Schemas without installing dependencies or interpreting
scientific claims.
