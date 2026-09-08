---
name: paper-evaluation
description: Evaluate an imported or local Full Run against preregistered claim criteria.
disable-model-invocation: true
---

# Evaluate Full Run claims

Work at the target Reproduction Repository root. Evaluation begins only from
`full_run_complete` and consumes the validated Full Run report plus the
preregistered contract at `results/evaluation.yaml`.

The contract names every scoped claim, the CPU Validation identifiers that
establish implementation correctness, the Full Run commands that establish
execution completeness, and a frozen metric path, aggregation, target, and
tolerance. It also records provenance, digitization uncertainty, and the
minimum Evidence Strength. Evaluation reads this contract; it never edits
metrics, tolerances, or the Full Run report.

Run and verify evaluation with:

```sh
python skills/paper-evaluation/scripts/evaluate.py --root . evaluate
python skills/paper-evaluation/scripts/evaluate.py --root . verify
```

The report at `results/evaluation-report.yaml` assesses each claim separately
on implementation correctness, execution completeness, result agreement, and
Evidence Strength. It reports `replicated`, `partially replicated`, `not
replicated`, or `inconclusive`; a single stochastic seed can be reported but
cannot receive `high` Evidence Strength. A decisive result mismatch is a
claim outcome, not permission to tune the implementation or tolerance.
