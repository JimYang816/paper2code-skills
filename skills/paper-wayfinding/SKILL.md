---
name: paper-wayfinding
description: Map unresolved Paper Dossier ambiguities into dependent research, decision, and Scientific Prototype work without losing the frontier.
disable-model-invocation: true
---

# Wayfind the Decision Frontier

Work at the target Reproduction Repository root. This Stage Skill does not
resolve ambiguities; it keeps every dependent work item and blocking edge
visible until `paper-grilling` records the terminal Evidence Resolutions.

Read `dossier/ambiguities.yaml`, `dossier/scope-matrix.yaml`, and the
Operational Task Graph rules in
`skills/paper2code-core/references/github-graph.md`.

For each unresolved `must` ambiguity, decide what would settle it:

- `decision`: a researcher choice that should become a Reconstruction Decision.
- `research`: a fact from a cited publication or official source, handled with
  the unchanged `research` skill.
- `prototype`: an isolated Scientific Prototype that answers one named
  scientific question.

Publish child issues with native blocking/sub-issue edges where available.
Give decision work `paper2code:decision`, research work `paper2code:evidence`,
and prototype work `paper2code:experiment`. Preserve the fallback `Blocked by`
and `Part of #<map>` body lines when native edges are unavailable.

Record the complete map in `decisions/frontier.yaml` using the schema in
[wayfinding.md](references/wayfinding.md). Every ambiguity and frontier item
must still point at its real issue or remain `null` only until publication.
Validate the result:

```sh
python skills/paper2code-core/scripts/paper2code.py validate-wayfinding --root .
```

Then hand the frontier to `paper-grilling`. Do not close or resolve the parent
Evidence Gate on behalf of the researcher.
