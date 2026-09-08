# Portable Full Run Bundle

`runs/<run-id>/bundle.yaml` is the immutable input contract for a Full Run.
It is intentionally tool-agnostic and contains the resolved configuration,
the source revision, the locked environment declaration, source and hash for
every dataset, a Dataset Manifest with expected files and a preparation
recipe, the independent seeds, and argument-array commands. Execution settings
are resolved in `resolved_config.execution` rather than inferred by the
runner.

Each command expands once per seed. Its `log`, `metrics`, and `outputs` fields
are required artifact templates. A completed `report.yaml` records the
expanded portable command, exit status, artifact paths, and SHA-256 hashes.
The report is valid for either `execution_mode: local` or
`execution_mode: imported`; no second import-only contract exists.

The Full Run Gate binds the canonical bundle hash, current CPU Validation
Report hash, code revision, and schema identities. Editing any bound artifact
requires a new preparation and approval cycle.
