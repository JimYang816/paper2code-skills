# Lifecycle and Approval Gates

Normal states advance one edge at a time:

`setup_pending → ready_for_extraction → evidence_extracted → evidence_approved → specification_ready → specification_approved → implementation_active → cpu_validated → full_run_approved → full_run_complete → evaluated`

`needs_decision`, `diagnosing`, and `revision_required` are typed exception states. Enter one with `return_target` equal to the interrupted normal state; recovery may return only there.

The researcher alone authorizes Approval Gates. Record scope, canonical artifact hashes, schema versions, identity, timestamp, and the exact transition. Conversation assent is input to the Gate Record, not a substitute for it. Required gates are:

- Paper Dossier approval: `evidence_extracted → evidence_approved`
- Paper specification approval: `specification_ready → specification_approved`
- Full Run budget and preregistration approval: `cpu_validated → full_run_approved`

Stage Skills validate incoming artifacts and current Gate Records, do only their named stage, then stop. The router reports the next Stage Skill but never invokes it.
