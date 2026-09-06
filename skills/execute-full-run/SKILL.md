---
name: execute-full-run
description: Execute or ingest approved Full Run Bundles without changing preregistered contracts.
disable-model-invocation: true
---

# Execute Full Runs

Require a current Full Run Gate Record. Revalidate the immutable Resolved Run Configuration, clean code revision, dataset hashes, environment, and seeds before execution. Run only the approved commands locally or hand the same bundle to the approved compute environment.

Preserve raw per-seed logs, metrics, checkpoints, outputs, failures, and final bundle validation. Change neither implementation nor thresholds during the run. Classify failures and enter `diagnosing` with return target `full_run_approved`; otherwise advance only to `full_run_complete`.
