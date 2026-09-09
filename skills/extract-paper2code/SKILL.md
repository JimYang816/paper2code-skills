---
name: extract-paper2code
description: Turn a target PDF into traceable, audited Paper Dossier evidence.
disable-model-invocation: true
---

# Extract a Paper Dossier

Work at the target Reproduction Repository root. Pass the target PDF as
`--pdf`. Use available tools without installing dependencies.

First check capabilities:

```sh
python skills/extract-paper2code/scripts/check_capabilities.py \
  --pdf <target.pdf> \
  --output .paper2code/capability-reports/extraction.yaml
```

Proceed when page rendering and either native text extraction or OCR are
available. The command exits 3 when this minimum is missing; report the
Capability Report and stop. Missing optional OCR does not block native-text
pages. For scanned pages that need OCR, report missing OCR and stop before
finalizing; preserve the incomplete dossier for recovery. Resolve only
capabilities the researcher approves, then rerun.

Extract raw, page-scoped artifacts and the human-readable dossier:

```sh
python skills/extract-paper2code/scripts/extract.py extract \
  --pdf <target.pdf> --root .
```

Review the extracted text and rendered figures, then populate
`dossier/evidence.yaml` with stable Evidence Items. Every material formula,
parameter, dataset setting, network component, baseline, and result claim gets
an `EVID-####` identifier, source locator, faithful text, units, confidence,
provenance, dependencies, and status. See `references/extraction.md` for the
provenance rules.

Run the separate adversarial audit:

```sh
python skills/extract-paper2code/scripts/extract.py audit --root .
```

Open findings are not hidden. Triage every finding in `dossier/audit.yaml` to
`triaged` with a `triage_note`, rerunning the audit after changing evidence.
Then validate and advance only when the dossier is clean:

```sh
python skills/extract-paper2code/scripts/extract.py validate --root .
python skills/extract-paper2code/scripts/extract.py finalize --root .
```

`finalize` records the `ready_for_extraction -> evidence_extracted` transition.
It does not approve the evidence, open the next stage, or install dependencies.
