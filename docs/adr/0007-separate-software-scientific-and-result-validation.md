# Separate software, scientific, and result validation

Implementation tickets will use the unchanged TDD discipline for ordinary software correctness, while a dedicated scientific-validation skill will own formula examples, invariants, reference-oracle equivalence, statistical checks, and paper-result evaluation. A deterministic reduced configuration must exercise every pipeline path at the CPU Validation Gate before any Full Run is accepted. Paper-scale training may run on local accelerators or through an exported Run Bundle.

Result agreement will use a two-stage preregistration process. Paper curves are digitized with extraction uncertainty, then channel generation and deterministic baselines are calibrated. Metrics, tolerances, repeat counts, and target points are frozen before final UDNet training results are inspected, so the acceptance rule cannot be moved to fit the observed outcome.

Failures are classified before work is generated. Software failures enter the deterministic diagnosis and implementation-ticket loop; formula, invariant, statistical, or Reference Oracle failures return to scientific validation; result mismatches enter reproduction diagnosis; environment failures repair the Run Bundle; and evidence failures reopen the dossier or an Approval Gate. No loop may tune implementation or acceptance criteria merely to approach a published curve.

Evaluation first produces a Claim Verdict for every item in the Scope Matrix. The overall outcome is `replicated` only when every `must` claim meets its approved criteria; it is `partially replicated` when only part of that required set is supported, `not replicated` when a successfully executed and adequately powered comparison decisively contradicts a required result, and `inconclusive` when missing evidence, unavailable data, unresolved source ambiguity, or inadequate statistical power prevents a decision.

Critical mathematical modules require an Independent Numerical Reference, invariants, shape and unit checks, and gradient checks where differentiable. Successful PyTorch execution and downstream training curves cannot serve as self-validation.

Development and the CPU Validation Gate may use one fixed seed. Full Runs of learned methods default to at least three independent seeds and preserve every raw run as well as aggregate variability. A budget-approved single run remains reportable but cannot receive the highest Evidence Strength. Paper curves used for comparison require a Digitization Record with a second extraction or human cross-check for critical target points.
