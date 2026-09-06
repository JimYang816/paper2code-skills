---
name: extract-paper
description: Extract and adversarially audit a traceable Paper Dossier from a target PDF.
disable-model-invocation: true
---

# Extract a Paper Dossier

Require `ready_for_extraction`. Read [the evidence policy](../paper2code-core/references/evidence-policy.md), then run a non-mutating Capability Check for text extraction, page rendering, figures, and the selected OCR path. On a missing capability, write a Capability Report and stop without installing anything.

Run `python scripts/extract_pdf.py capabilities` first. For the native-text path, use `python scripts/extract_pdf.py extract <paper.pdf> --output dossier/extraction`; visually inspect the rendered pages and route pages named in `needs_ocr_pages` through a researcher-approved OCR capability.

Preserve source identity and license findings. Extract readable Markdown plus `evidence.yaml`, `ambiguities.yaml`, preliminary `scope-matrix.yaml`, source and dataset manifests, experiment matrix, figure assets, and Digitization Records. Give every material item a stable locator and provenance class.

Perform the separate Evidence Audit with full page/section/equation/figure/table/citation coverage. Validate all records. Advance only to `evidence_extracted`; request the researcher to invoke the next stage explicitly.
