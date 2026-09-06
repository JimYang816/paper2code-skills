---
name: cpu-validate
description: Prove the entire approved reproduction pipeline in a reduced deterministic CPU configuration.
disable-model-invocation: true
---

# CPU Validation Gate

Require approved specification, completed implementation tickets, software tests, code review, and required Scientific Validation. Run one reduced fixed-seed CPU path through every accepted dataset adapter, channel, model, baseline, metric, checkpoint, and plot/report output.

Validate manifests and resolved configuration; preserve commands, logs, metrics, and outputs. Classify failures before creating follow-up work. Advance `implementation_active` to `cpu_validated` only when every required path completes. This gate does not claim paper-scale result agreement.
