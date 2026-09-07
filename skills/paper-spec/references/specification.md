# Paper specification authoring rules

`specification/paper-spec.md` and `specification/specification.yaml` are the
Scientific Record contract between the approved Paper Dossier and
implementation. The unchanged `to-tickets` skill reads the Markdown form; the
Deterministic Toolkit validates the YAML form.

The Markdown document must contain these sections:

```text
# Paper Specification
## Scope
## Method
## Data
## Baselines
## Experiments
## Figures
## Metrics
## Uncertainty
## Budget
## Acceptance
```

Every `must` item must be complete. A `must` item may not contain a value that
is `open`, `unknown`, `TBD`, `TODO`, `FIXME`, or `PLACEHOLDER`. `should` items
may remain less precise, and `out` items must match the Scope Matrix and keep
their exclusion rationale visible.

Machine item identifiers are stable and section-scoped:

- `CLM-####` for Scope Matrix claims
- `MTH-####` for method contracts
- `DATA-####` for dataset contracts
- `BASE-####` for Baseline Contracts
- `EXP-####` for experiment plans
- `FIG-####` for figure targets
- `MET-####` for result metrics
- `ACC-####` for acceptance rules

Reference only identifiers that already exist. Acceptance rules must point at a
`MET-####` metric and at least one `CLM-####` claim. A baseline or dataset item
has a matching file under `contracts/baselines/` or `contracts/datasets/` so
the Specification Gate can hash each contract independently.

Keep the prose forms aligned with the machine record. If a scientific choice is
still unresolved, return to `paper-grilling` or `paper-wayfinding` before
preparing the specification; never leave the placeholder in the specification
and rely on an implementation agent to fill it.
