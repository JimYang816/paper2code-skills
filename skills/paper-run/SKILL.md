---
name: paper-run
description: Prepare, approve, execute, or import a portable Full Run bundle.
disable-model-invocation: true
---

# Execute a portable Full Run

Work at the target Reproduction Repository root. A Full Run begins only after
the repository is `cpu_validated` and its CPU Validation Report is current.
The bundle is the portable contract: it records resolved configuration, code
revision, locked environment capabilities, dataset identities and hashes,
seeds, commands, and the log, metric, and output paths each command must leave.

Create `runs/<run-id>/bundle.yaml` as JSON-compatible YAML using the schema
under `skills/paper2code-core/references/schemas/v1/run.schema.json`. Dataset
paths are repository-relative and commands are argument arrays. Commands may
use `{python}`, `{root}`, `{run_dir}`, `{seed}`, and `{workers}` substitutions.
Declare every executable or locked dependency in `environment.capabilities` or
`environment.dependencies`; the runner reports missing capabilities and never
installs them.

Validate the bundle without advancing state:

```sh
python skills/paper-run/scripts/run.py --root . --run-id <id> prepare
```

Ask the researcher to approve the resolved bundle explicitly. Record the
hash-bound gate only after that approval:

```sh
python skills/paper-run/scripts/run.py --root . --run-id <id> approve --approver "<identity>"
```

Execute locally or validate a returned bundle with the same report contract:

```sh
python skills/paper-run/scripts/run.py --root . --run-id <id> execute
python skills/paper-run/scripts/run.py --root . --run-id <id> import
python skills/paper-run/scripts/run.py --root . --run-id <id> verify
```

`execute` refuses stale approvals, dirty code, changed datasets, incomplete
artifacts, and missing capabilities. It writes `runs/<run-id>/report.yaml`
with command results and hashes every produced log, metric, and output. An
external worker must return the same bundle directory plus a report; `import`
uses the same deterministic validator and advances to `full_run_complete` only
when every declared command, seed, and artifact is covered.
