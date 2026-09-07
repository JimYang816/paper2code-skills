# Paper-to-Code Skill Bundle

The canonical reusable Skill Closure is in `skills/`. It currently contains the
nine unchanged upstream skills selected by ADR-0005, their required setup skill,
and the new `paper2code-core` verification support skill. Paper-specific stages
and the rest of the Deterministic Toolkit are subsequent implementation work.

With Python 3.9 or later and no third-party packages:

```sh
python skills/paper2code-core/scripts/verify_closure.py --root .
python -m unittest discover -s tests -v
```

To independently audit upstream bytes, fetch Matt Pocock's skills repository
and pass its checkout to the verifier:

```sh
python skills/paper2code-core/scripts/verify_closure.py --root . --upstream /path/to/upstream
```

The checkout must contain the commit pinned in `skills-lock.yaml`; its working
tree and current branch do not affect verification. No network calls or file
writes occur during verification.

See [the closure contract](skills/paper2code-core/references/skill-closure.md)
for distribution contents, dependency audit rules and hash encoding, and
[third-party notices](THIRD_PARTY_NOTICES.md) for attribution and boundaries.
The `.agents/skills/` directory and `skills-lock.json` remain the separate
development installation; they are not the canonical release bundle.
