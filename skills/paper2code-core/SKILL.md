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

Use `validate-ambiguities --root .` to enforce terminal Evidence Resolutions
for every `must` ambiguity, `validate-wayfinding --root .` to check the
decision frontier, `validate-evidence-gate --root .` to validate a recorded
Evidence Gate, and `validate-scope-matrix --root .`,
`validate-specification --root .`, and `validate-specification-gate --root .`
to validate the specification stage artifacts and approval record. The CPU
Gate stage adds `validate-cpu-contract --root .` and
`validate-cpu-report --root .`; the latter refuses a stale or failed report
before the `cpu_validated` transition. The Full Run stage adds
`validate-run-bundle --root .`, `validate-full-run-gate --root .`, and
`validate-full-run-report --root .`; these commands share the same contract
for local and imported bundles and refuse stale hashes or missing artifacts.
Stage skills own the approval conversation and state transition; these commands
only perform deterministic checks.

For the final stage, validate-evaluation --root . checks the frozen Result
Preregistration and validate-evaluation-report --root . checks the claim-level
report, its Full Run identity, and its outcome. Evaluation requires the Result
Preregistration hash to be bound by the Full Run Gate before execution. The
paper-evaluation Stage Skill advances full_run_complete to evaluated only with
a current report; paper-diagnosis records typed failure routes and does not
edit preregistered criteria.

The lifecycle router is read-only:

```sh
python skills/paper2code-core/scripts/paper2code.py route --root .
```

It validates the current boundary and reports only legal next Stage Skills;
`validate-diagnosis --root .` checks an exception state's recorded route.
