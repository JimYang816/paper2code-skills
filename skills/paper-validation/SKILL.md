---
name: paper-validation
description: Run independent numerical checks and the reduced deterministic CPU Validation Gate.
disable-model-invocation: true
---

# Validate the CPU Gate

Work at the target Reproduction Repository root. This stage is deliberately
separate from ordinary implementation completion: it runs the approved
Scientific Validation contract and is the only workflow path that can advance
`implementation_active` to `cpu_validated`.

The contract in `validation/validation.yaml` must declare:

- an independent numerical reference for every critical mathematical module;
- applicable invariant, unit, shape, and gradient checks for each reference;
- executable reduced-CPU paths for data, model, baseline, metric, and
  reporting; and
- the artifacts each path is required to produce.

Commands are argument arrays, never shell strings. Use `{python}`, `{root}`,
`{seed}`, `{workers}`, and `{device}` as portable substitutions. Each command
runs with a fixed seed, CPU device, one worker, and CUDA disabled. A numerical
reference command must print JSON with `status: "passed"` and the identifiers
of every declared check in its `checks` object.

First inspect and validate the contract without mutating state:

```sh
python skills/paper-validation/scripts/validate.py --root . validate
```

Run the complete gate only from `implementation_active`:

```sh
python skills/paper-validation/scripts/validate.py --root . run
```

The runner executes every critical reference and every declared data, model,
baseline, metric, and reporting path before writing
`validation/reports/cpu-validation.yaml`. A passing report advances to
`cpu_validated`. A failure is recorded with one of `software`, `scientific`,
`evidence`, or `environment` and enters its typed exception route; it never
advances the CPU state.

Verify a completed gate before handing work to the Full Run stage:

```sh
python skills/paper-validation/scripts/validate.py --root . verify
```

Do not edit `state.yaml` to claim CPU validation. The core transition checker
also refuses `cpu_validated` unless the current, passing CPU Validation Report
matches the current contract.
