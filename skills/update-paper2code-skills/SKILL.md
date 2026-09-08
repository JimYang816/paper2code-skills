---
name: update-paper2code-skills
description: Preview and apply an approved, conflict-aware Paper-to-Code Skill Closure upgrade.
disable-model-invocation: true
---

# Upgrade the Skill Closure

Work at the target Reproduction Repository root. Point the preview at a
candidate bundle checkout:

```sh
python skills/update-paper2code-skills/scripts/update.py \
  --root . --candidate-root <candidate-bundle> preview
```

Inspect `.paper2code/skill-upgrade-preview.yaml`. It reports additions,
content changes, removals, provenance changes, distribution-file changes, and
local conflicts. Resolve every conflict before asking the researcher to
approve the exact preview.

After explicit approval, apply the unchanged candidate closure and lock:

```sh
python skills/update-paper2code-skills/scripts/update.py \
  --root . --candidate-root <candidate-bundle> approve \
  --approver "<identity>"
```

The upgrade replaces only `skills/`, the pinned `skills-lock.yaml`, and the
closure's distribution files. It preserves dossier, decisions, specification,
contracts, validation, runs, results, and implementation files. It verifies
the candidate before preview and the installed closure after approval.
