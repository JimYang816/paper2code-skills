# Use target-paper authority and a hybrid dossier

The target PDF is authoritative for claims about its reported method and experiments, while cited publications and official technical documentation may clarify concepts without silently filling omitted target-paper settings. Extraction will produce a Paper Dossier combining researcher-readable Markdown, machine-checkable records, and visual assets because prose alone cannot reliably gate unresolved fields or generate acceptance rubrics.

The dossier is not eligible for its first Approval Gate until it passes two distinct passes: systematic extraction and an adversarial Evidence Audit. Every material item needs a source locator, and the audit must leave no untriaged omissions, contradictions, unit conflicts, or unsupported inferences.

Every material formula, parameter, dataset setting, network component, and result claim receives a stable Evidence Item identifier with locator, faithful text, units, confidence, provenance, dependencies, and status. Before specification approval, each `must` ambiguity must have an Evidence Resolution of `confirmed`, `derived`, `reconstructed`, `empirically_selected`, or `excluded`; the implementation phase may not inherit `open`, `unknown`, or `TBD` fields.
