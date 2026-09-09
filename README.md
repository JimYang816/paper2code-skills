# Paper-to-Code Skill Bundle

The canonical reusable Skill Closure is in `skills/`. It currently contains the
nine unchanged upstream skills selected by ADR-0005, their required setup skill,
the new `paper2code-core` deterministic support skill, the new
`setup-paper2code` scaffold skill, the new `extract-paper2code` extraction
Stage Skill, the new `paper-grilling` Evidence Gate Stage Skill, and the new
`paper-wayfinding` decision-frontier Stage Skill, and the new `paper-spec`
Specification Gate Stage Skill, the new `paper-validation` CPU Gate Stage
Skill, the new `paper-run` Full Run Stage Skill, the new `paper-evaluation`
claim-level evaluation Stage Skill, and the new `paper-diagnosis` failure
routing Stage Skill. The CPU stage demonstrates
the independent-reference and deterministic reduced-run boundary; the Full Run
stage carries that boundary into an approved, hash-bound, locally executable or
externally importable bundle, and evaluation turns its output into separate
claim verdicts without changing preregistered result criteria.

With Python 3.9 or later and no third-party packages:

```sh
python skills/paper2code-core/scripts/verify_closure.py --root .
python -m unittest discover -s tests -v
```

See [generic validation evidence](docs/validation/issue-11.md) for scenario
coverage, independent Behavioral Forward Tests, and real-tool limitations.

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
