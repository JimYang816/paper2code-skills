---
name: setup-paper2code
description: Scaffold or refresh an independent Paper-to-Code Reproduction Repository.
disable-model-invocation: true
---

# Set up a Reproduction Repository

Work at the target repository root. The bundle root is the checkout containing
this skill, normally identified by the caller as `--bundle-root`.

Read the [repository layout](../paper2code-core/references/repository-layout.md)
and [GitHub graph rules](../paper2code-core/references/github-graph.md) before
making changes. First run the capability check:

```sh
python scripts/check_capabilities.py --output <target>/.paper2code/capability-reports/setup.yaml
```

Then inspect existing files and produce a create/preserve/conflict plan:

```sh
python scripts/setup.py --target <target> --bundle-root <bundle> [--provision-labels]
```

After the researcher accepts that plan, rerun with `--apply`. Include
`--provision-labels` only when the plan disclosed those GitHub writes. The
script initializes local Git only when absent, preserves existing user files,
and copies the verified Skill Closure with `skills-lock.yaml`.

Setup never creates a GitHub repository or remote and never connects an
account. The repository remains in `setup_pending` until an existing GitHub
`origin` and usable `gh` access both verify; there is no local-tracker
fallback. When GitHub is ready and labels are provisioned, validate the result
with `paper2code.py validate-setup --root <target>`.
