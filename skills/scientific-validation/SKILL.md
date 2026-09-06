---
name: scientific-validation
description: Define and run formula, invariant, oracle, statistical, unit, shape, and gradient checks for a paper implementation.
disable-model-invocation: true
---

# Scientific Validation

Read [the scientific validation rules](../paper2code-core/references/scientific-validation.md) and the approved contracts. Build Independent Numerical References that do not reuse production logic. Test worked examples, invariants, units, shapes, gradients, controlled distributions, known-equivalent waveforms, and Reference Oracle equivalence where required.

Write versioned reports under `validation/`. A failure enters the typed `diagnosing` state with its original return target and a `scientific` classification. Do not change approved contracts or result thresholds.
