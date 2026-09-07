---
name: paper2code-core
description: Verify the pinned Skill Closure before copying or auditing a Paper-to-Code bundle.
---

Run `python skills/paper2code-core/scripts/verify_closure.py --root .` from
the Skill Bundle Repository root. A nonzero exit means the bundle is incomplete
or differs from its lock; resolve the reported differences before copying it.

For source verification, add `--upstream /path/to/mattpocock-skills-checkout`.
The verifier reads Git objects at the locked revision without changing that checkout.
See [the closure contract](references/skill-closure.md) for copying and provenance rules.
