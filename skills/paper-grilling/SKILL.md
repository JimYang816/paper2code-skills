---
name: paper-grilling
description: Resolve Paper Dossier ambiguities to terminal Evidence Resolutions and record the researcher-approved Evidence Gate.
disable-model-invocation: true
---

# Resolve the Evidence Gate

Work at the target Reproduction Repository root. The Evidence Gate closes the
gap between `evidence_extracted` and `evidence_approved`.

First inspect the audited dossier:

```sh
python skills/paper2code-core/scripts/paper2code.py validate-dossier --root .
python skills/paper2code-core/scripts/paper2code.py validate-ambiguities --root .
```

Read `dossier/paper.md`, `dossier/evidence.yaml`, `dossier/audit.yaml`, and
`dossier/ambiguities.yaml`. Every `must` ambiguity must reach a terminal
Evidence Resolution before approval. The possible resolutions and their
provenance are in [grilling.md](references/grilling.md).

Use the unchanged `grilling` skill to interview the researcher. Work the
decision frontier in rounds; find facts from the dossier and cited sources
yourself, and ask only decisions the researcher can make. Do not guess a
resolution, and do not record conversation memory as the Scientific Record:
after each decision, update `dossier/ambiguities.yaml` so the resolution,
basis, and Evidence Item or Reconstruction Decision references are committed.

If the ambiguity set is large, run `paper-wayfinding` first. Its
`decisions/frontier.yaml` and GitHub sub-issues keep dependent research,
decision, and prototype work visible without dropping unresolved edges. Return
here to record the resolutions those work products supply.

Before approval, validate the current inputs:

```sh
python skills/paper-grilling/scripts/gate.py --root . validate
```

Then ask the researcher to explicitly approve the versioned artifact set.
Only after that assent, record the hash-bound Gate Record and advance state:

```sh
python skills/paper-grilling/scripts/gate.py --root . approve --approver "<identity>"
python skills/paper-grilling/scripts/gate.py --root . verify-gate
```

`approve` binds `dossier/paper.md`, `dossier/evidence.yaml`,
`dossier/audit.yaml`, `dossier/ambiguities.yaml`, and
`dossier/scope-matrix.yaml` by canonical hash and writes
`.paper2code/gates/evidence-gate.yaml`. It does not open the next stage or
consume the researcher's later Specification Gate.
