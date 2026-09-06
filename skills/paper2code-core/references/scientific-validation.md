# Scientific validation and evaluation

Software tests and code review establish implementation correctness; they do not establish Scientific Validation. Critical mathematical modules additionally require an Independent Numerical Reference, worked formula examples, invariants, units, shapes, statistical expectations, and gradients where differentiable.

The CPU Validation Gate runs every accepted data, model, baseline, metric, and plotting path end to end with a reduced deterministic CPU configuration. It is not paper-scale training.

Before inspecting final target-model results, freeze metrics, target points, digitization uncertainty, tolerances, repeats, seeds, and aggregation. Learned Full Runs default to at least three independent seeds. A researcher-approved single run is reportable with reduced Evidence Strength.

Evaluate each scoped claim on three axes: implementation, execution, and result agreement. A decisive contradiction requires complete execution and adequate evidence. Aggregate only `must` claims into `replicated`, `partially_replicated`, `not_replicated`, or `inconclusive`.

Classify failures first: `software`, `scientific`, `result`, `environment`, or `evidence`. Route the class to its owning loop without tuning implementation or preregistered thresholds toward the paper curve.
