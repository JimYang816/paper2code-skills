---
name: grill-paper
description: Resolve a Paper Dossier's scientific ambiguities and prepare researcher approval.
disable-model-invocation: true
---

# Grill the paper

Require `evidence_extracted` or `needs_decision`. Read [the evidence policy](../paper2code-core/references/evidence-policy.md). Use the unchanged `grilling` discipline, but ground every question in Evidence Item IDs and preserve answers in `decisions/`, not only in conversation.

Drive every `must` ambiguity to `confirmed`, `derived`, `reconstructed`, `empirically_selected`, or `excluded`. If the set needs parallel decision, research, or prototype work, stop and direct the researcher to `paper-wayfinder`; do not silently start those stages.

Validate the dossier and researcher-authored Gate Record. Only explicit researcher approval may advance `evidence_extracted` to `evidence_approved`.
