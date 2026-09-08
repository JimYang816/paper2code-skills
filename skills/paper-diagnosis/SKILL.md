---
name: paper-diagnosis
description: Route Full Run and claim-evaluation failures to the correct diagnostic loop.
disable-model-invocation: true
---

# Diagnose reproduction failures

Work at the target Reproduction Repository root after a Full Run or
evaluation failure. Read the failure class from the validated report, or pass
`--failure-class` for an externally recorded failure. Write the durable
`results/diagnosis.yaml` record and route the current state to its typed
exception state without changing the approved Full Run or evaluation
contract.

```sh
python skills/paper-diagnosis/scripts/diagnose.py --root . diagnose
```

Software and scientific failures use `diagnosing`, result mismatches use
`revision_required`, environment failures use `diagnosing`, and evidence
failures use `needs_decision`. The state retains the interrupted normal state
as its return target. Diagnosis may propose work, but it must not modify
preregistered metrics or tolerances merely to approach a published result.
