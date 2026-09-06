---
name: setup-paper2code
description: Scaffold or refresh an independent Paper-to-Code Reproduction Repository.
disable-model-invocation: true
---

# Set up a Reproduction Repository

Read [the repository layout](../paper2code-core/references/repository-layout.md) and [GitHub graph rules](../paper2code-core/references/github-graph.md). Run `python scripts/check_capabilities.py --output <repo>/.paper2code/capability-reports/setup.yaml`, inspect existing files, and show the exact create/preserve/conflict plan before applying it.

Use `python scripts/setup.py --target <repo> --bundle-root <bundle> [--profile <name>]` without `--apply` for the plan. After the researcher accepts that plan, rerun with `--apply`; add `--provision-labels` only when the plan disclosed those GitHub writes. Copy only the selected profiles and the transitive Reproduction Core closure.

Initialize local Git only when absent. Preserve user files and existing history. Copy the selected Reproduction Core, Domain Profiles, and their verified closure with `skills-lock.yaml`. Add data/checkpoint exclusions without replacing existing ignore rules.

Verify an existing GitHub remote and usable `gh` access. Create neither a GitHub repository nor a remote and connect no account. Keep `setup_pending` until both checks pass. When they pass, provision the issue labels idempotently, validate the scaffold, and advance only to `ready_for_extraction`.
