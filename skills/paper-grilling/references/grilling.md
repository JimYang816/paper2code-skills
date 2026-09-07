# Evidence Resolution provenance

The Evidence Gate separates author facts from reconstruction work. An open
`must` ambiguity blocks `evidence_approved`; `should` and `out` ambiguities do
not block the gate but still need a recorded disposition before a later
specification can rely on them.

Use exactly these terminal resolutions:

- `confirmed`: the dossier already contains Paper Evidence or a Supporting
  Source that answers the ambiguity. Reference the `EVID-####` items.
- `derived`: the answer follows mathematically or logically from committed
  Paper Evidence. Record the derivation and the Evidence Item it starts from.
- `reconstructed`: the paper omits the detail and the researcher chooses a
  reconstruction. Record it as a Reconstruction Decision and never label it as
  an author fact.
- `empirically_selected`: the researcher chooses between plausible values from
  evidence or constrained experiments. Record the alternatives considered and
  the selection rule.
- `excluded`: the ambiguity is removed from scope. The Scope Matrix must move
  the affected claim to `out`, and the rationale must stay visible.

Every resolved ambiguity keeps `basis` prose plus `evidence_ids` and
`decision_ids`. Resolutions are Scientific Record artifacts, not issue-comment
memory. A Scientific Prototype may contribute an Evidence Item or
Reconstruction Decision but cannot silently become production code.
