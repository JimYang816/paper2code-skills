# Reproduction Repository layout

The setup stage creates or preserves this stable Scientific Record layout:

```text
.paper2code/
  state.yaml
  gates/
  capability-reports/
paper/
dossier/
  evidence.yaml
  ambiguities.yaml
  scope-matrix.yaml
  figures/
decisions/
specification/
contracts/
  baselines/
  datasets/
validation/
  references/
  reports/
runs/
  <run-id>/
    bundle.yaml
    report.yaml
results/
  evaluation.yaml
  evaluation-report.yaml
  diagnosis.yaml
prototypes/
skills/
skills-lock.yaml
```

Git artifacts are the Scientific Record. GitHub Issues are links and
coordination, never the only copy of a scientific fact or conclusion. Keep raw
and large derived datasets, restricted software, model checkpoints, and the
target PDF out of Git unless redistribution rights and size policy explicitly
allow them. Commit manifests, licenses, recipes, hashes, and small
deterministic fixtures.
