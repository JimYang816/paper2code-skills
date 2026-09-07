# Extraction provenance rules

The target PDF is authoritative for `paper_evidence`. A `supporting_source`
may clarify a cited paper or official document but cannot silently fill a
target-paper omission. `derived`, `reconstructed`, and `empirically_selected`
items must name the Paper Evidence or Reconstruction Decisions they depend on.

Use the six Evidence Item classes for all material claims: `formula`,
`parameter`, `dataset`, `network_component`, `baseline`, and `result_claim`.
Keep identifiers stable across reruns and refer only to identifiers that exist.

The Evidence Audit is a second pass. It checks omissions, contradictions, unit
problems, indexing problems, citation dependencies, and unsupported
inferences. Every generated finding is visible in `dossier/audit.yaml`; a
finding may only be `open` or `triaged`, and the dossier cannot finalize while
any finding remains `open`.
