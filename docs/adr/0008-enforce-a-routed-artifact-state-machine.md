# Enforce a routed artifact state machine

The workflow will use small stage-specific skills plus a lightweight `paper2code` router. The router reads `.paper2code/state.yaml`, validates required artifacts and Gate Records, and recommends or invokes only the next legal stage; it does not reproduce the behavior of the underlying skills.

Core repository paths and machine contracts are stable across papers, while Domain Profiles may add fields and checks without redefining core meanings. Downstream skills refuse stale or missing approvals by validating the approved artifact hashes. This makes the workflow resumable and prevents conversation memory, an apparently complete Markdown document, or manually skipped stages from silently authorizing implementation or experiments.

The normal state chain is `setup_pending`, `ready_for_extraction`, `evidence_extracted`, `evidence_approved`, `specification_ready`, `specification_approved`, `implementation_active`, `cpu_validated`, `full_run_approved`, `full_run_complete`, and `evaluated`. Exception states `needs_decision`, `diagnosing`, and `revision_required` retain a typed return target. State, contracts, and approvals use YAML validated by versioned JSON Schemas; approval identity hashes are computed from a canonical JSON representation rather than presentation-sensitive YAML text.

A lightweight Deterministic Toolkit performs those mechanical checks and is normally called by stage skills rather than by the researcher. It validates but does not interpret paper evidence, choose Reconstruction Decisions, write implementations, train models, or determine Replication Outcomes. Keeping judgment in skills and repeatable mechanics in tested scripts prevents the command layer from becoming a second workflow engine.

Major lifecycle transitions remain user-invoked Stage Skills in the style of the upstream Matt Pocock workflow. The router may explain the next legal action, and Stage Skills may invoke Support Skills and deterministic checks, but they do not silently chain into the next major stage or consume an Approval Gate on the researcher's behalf.
