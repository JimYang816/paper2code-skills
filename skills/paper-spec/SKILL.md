---
name: paper-spec
description: Produce and approve an implementation-ready paper specification from the approved Paper Dossier.
disable-model-invocation: true
---

# Produce the Paper Specification

Work at the target Reproduction Repository root. This Stage Skill closes the
gap from `evidence_approved` to `specification_approved`, first producing a
`specification_ready` specification and then recording the researcher-approved
Specification Gate.

Start by confirming the Evidence Gate is still current:

```sh
python skills/paper2code-core/scripts/paper2code.py validate-evidence-gate --root .
python skills/paper-spec/scripts/spec.py --root . verify-evidence
```

Read `dossier/paper.md`, `dossier/evidence.yaml`, `dossier/audit.yaml`,
`dossier/ambiguities.yaml`, `dossier/scope-matrix.yaml`, and
`decisions/frontier.yaml`. Reuse approved Evidence Items and Reconstruction
Decisions; do not invent new scientific details.

Write two specification artifacts plus one contract file for each baseline and
dataset:

- `specification/paper-spec.md` is the researcher-readable specification that
  the unchanged `to-tickets` skill consumes.
- `specification/specification.yaml` is the machine-checkable record validated
  against the versioned schema.
- `contracts/baselines/<BASE-####>.yaml` and
  `contracts/datasets/<DATA-####>.yaml` hold the hash-bound Baseline and Dataset
  Contracts.

See [the authoring rules](references/specification.md) for the required
sections and the prohibition on unresolved `must` values.

Validate and advance to `specification_ready`:

```sh
python skills/paper-spec/scripts/spec.py --root . prepare
```

Ask the researcher to explicitly approve the versioned specification. Only
after that assent, record the hash-bound Gate Record and advance state:

```sh
python skills/paper-spec/scripts/spec.py --root . approve --approver "<identity>"
python skills/paper-spec/scripts/spec.py --root . verify-gate
```

`approve` binds the approved dossier, decision frontier, specification, schema
identities, and every contract file by canonical hash. It does not create
tickets, open implementation, or consume a later Approval Gate. After
`specification_approved`, point the unchanged `to-tickets` skill at
`specification/paper-spec.md`.
