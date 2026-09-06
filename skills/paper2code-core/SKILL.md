---
name: paper2code-core
description: Validate Paper-to-Code scientific records, approvals, lifecycle state, manifests, skill closure, and run evidence when a reproduction stage needs deterministic checks.
---

# Paper-to-Code Core

This Support Skill owns mechanical contracts only. Keep evidence interpretation, Reconstruction Decisions, approvals, implementation, training, and Replication Outcomes in the calling Stage Skill or with the researcher.

Before acting, read the branch you need:

- Repository paths and artifact ownership: [repository-layout.md](references/repository-layout.md)
- Legal states and Approval Gates: [lifecycle.md](references/lifecycle.md)
- Evidence and ambiguity provenance: [evidence-policy.md](references/evidence-policy.md)
- Run and claim rules: [scientific-validation.md](references/scientific-validation.md)
- GitHub Operational Task Graph: [github-graph.md](references/github-graph.md)

Use `python scripts/paper2code.py --help` for deterministic validation. Run a Capability Check before the selected stage mutates state. If requirements are missing, write a `capability-report.yaml` with exact recovery commands and stop in the recoverable current state; install nothing.

Gate Records are researcher-authored approvals. Compute artifact identities with `canonical-hash`, validate the Gate Record, and use `verify-gate` before any gated transition. A changed artifact makes approval stale.
