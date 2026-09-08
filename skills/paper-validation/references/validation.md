# CPU Validation Contract

`validation/validation.yaml` is a JSON-compatible YAML record. It is the
machine-checkable boundary between an implementation and Scientific
Validation. The deterministic runner does not infer missing scientific checks
from source code or from a successful downstream metric.

## Independent numerical references

Each `critical_math` item points to a small, deliberately separate reference
under `validation/references/`. Its command should calculate known examples or
an analytic result without importing the production implementation. The
declared check groups mean:

- `invariants`: conservation, symmetry, monotonicity, normalization, or other
  formula-level properties;
- `units`: dimensional and scale checks;
- `shapes`: input, output, batch, and boundary shapes; and
- `gradients`: finite-difference or analytic gradient checks where the module
  is differentiable.

If a group truly does not apply, list its name in `not_applicable` and leave
that group empty. Every other group needs at least one stable check identifier.

The reference command prints this shape:

```json
{
  "status": "passed",
  "checks": {
    "invariants": ["INV-0001"],
    "units": ["UNIT-0001"],
    "shapes": ["SHAPE-0001"],
    "gradients": ["GRAD-0001"]
  }
}
```

The runner requires every applicable identifier from the contract to be
present in the command output. This makes a passing production test suite
insufficient on its own.

## Reduced CPU paths

Every declared path has one of the required kinds: `data`, `model`, `baseline`,
`metric`, or `reporting`. The command must exercise the reduced deterministic
configuration and return zero. Declared artifacts must exist after the command
returns. A path may have no artifact when its observable result is fully
captured by its exit status, but reporting paths should normally leave a small
machine-readable report.

The runner supplies these environment variables in addition to the normal
process environment: `PAPER2CODE_DEVICE=cpu`, `PAPER2CODE_SEED`,
`PAPER2CODE_WORKERS`, `PYTHONHASHSEED`, `CUDA_VISIBLE_DEVICES`,
`OMP_NUM_THREADS`, and `MKL_NUM_THREADS`.

## Failure routing

The first observed failure is classified in the report, while all declared
commands are still attempted:

| Class | Meaning | Typed route |
| --- | --- | --- |
| `software` | implementation or ordinary command failure | `diagnosing`, return to `implementation_active` |
| `scientific` | independent reference, invariant, unit, shape, or gradient failure | `diagnosing`, return to `implementation_active` |
| `evidence` | missing/invalid approved contract or required output artifact | `needs_decision`, return to the interrupted `implementation_active` stage |
| `environment` | executable or runtime capability unavailable | `diagnosing`, return to `implementation_active` |

The route is a workflow state, not a replacement for the detailed failure
message. Diagnosis must not tune the implementation or acceptance criteria to
make the expected answer pass.
