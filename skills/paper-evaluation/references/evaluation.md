# Claim Evaluation Contract

results/evaluation.yaml is the frozen Result Preregistration consumed by the
evaluation runner. It lists every in-scope claim, the CPU Validation results
that establish implementation correctness, the Full Run command ids that
establish execution completeness, and the metric extraction and comparison
rule. The target and tolerance are read from this file and are never inferred
from the observed result.

For each claim, evaluation reads the declared JSON metric once per selected
seed, applies the declared aggregation, and compares the aggregate using the
declared tolerance. A digitization uncertainty may be recorded as part of the
preregistered evidence and is included in the comparison without changing the
stored tolerance.

Evidence Strength is computed from the observed seed count and provenance:
one seed is low, two seeds are moderate, and three or more independent seeds
may be high. Reconstructed, derived, empirical, excluded, or digitized
evidence is capped at moderate. This is a reporting rule, not a confidence
interval or a replacement for a statistical analysis.

The aggregate outcome considers must claims only. A decisive, adequately
supported metric mismatch is not replicated; partial support is partially
replicated; missing power or insufficient evidence is inconclusive.
