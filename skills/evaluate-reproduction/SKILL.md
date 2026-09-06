---
name: evaluate-reproduction
description: Evaluate scoped paper claims across implementation, execution, and result-agreement axes.
disable-model-invocation: true
---

# Evaluate the reproduction

Require `full_run_complete` and validated Run Bundles. Read [the evaluation rules](../paper2code-core/references/scientific-validation.md). Produce one Claim Verdict per Scope Matrix item with evidence links, uncertainty, repeat count, and Evidence Strength.

Run the deterministic evaluator only after the individual judgments exist. Report `replicated`, `partially_replicated`, `not_replicated`, or `inconclusive`. Missing evidence, unavailable data, or inadequate power remains inconclusive; a decisive mismatch requires complete execution and adequate evidence. Commit the report and advance only to `evaluated`.
