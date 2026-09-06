---
name: prepare-full-run
description: Preregister result criteria and package portable self-describing Full Run Bundles.
disable-model-invocation: true
---

# Prepare Full Runs

Require `cpu_validated`. Read [the run rules](../paper2code-core/references/scientific-validation.md). Freeze target points, metrics, Digitization Records and uncertainty, tolerances, repeats, seeds, and aggregation before target-model final results are inspected.

Create a Run Bundle with fully resolved configuration, clean code revision, locked environment, Dataset Manifest identities, seeds, commands, expected logs, metrics, and outputs. Default learned methods to at least three seeds; mark an explicitly budget-approved single seed for reduced Evidence Strength.

Validate each bundle. Only a researcher-authored budget/preregistration Gate Record advances to `full_run_approved`; stop before execution.
