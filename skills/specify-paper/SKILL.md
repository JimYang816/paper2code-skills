---
name: specify-paper
description: Convert an approved Paper Dossier and Reconstruction Decisions into an implementation-ready reproduction specification.
disable-model-invocation: true
---

# Specify the reproduction

Require a current dossier Gate Record and run `python ../paper2code-core/scripts/paper2code.py check-specification-readiness <ambiguities.yaml>`. Produce method, data, Baseline, experiment, validation, result-preregistration, and acceptance contracts. Freeze the Scope Matrix as `must`, `should`, and `out`; cite Evidence Item and decision IDs for every scientific requirement.

Learned baselines without released code get a one-hop mini dossier. Classical baselines get equations, paper-specific settings, expected behavior, and independent checks. Implementation tickets may not invent or alter these contracts.

Validate the specification artifacts, advance to `specification_ready`, and stop for explicit researcher approval. After a current researcher Gate Record is present, advance only to `specification_approved` and direct the researcher to `to-tickets`.
