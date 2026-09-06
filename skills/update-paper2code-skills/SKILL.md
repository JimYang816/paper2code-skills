---
name: update-paper2code-skills
description: Preview and apply an explicitly approved Paper-to-Code Skill Closure upgrade.
disable-model-invocation: true
---

# Update Paper-to-Code skills

Read the reproduction repository's `skills-lock.yaml` and candidate canonical lock. Resolve both closures, verify hashes, and preview added, removed, unchanged, upstream-changed, locally modified, and conflicting files. Preserve modification classification and dependency edges.

Stop after preview until the researcher explicitly approves the exact candidate. On approval, replace only verified skill files without touching the Scientific Record or implementation, write the new lock, validate the closure, and commit the upgrade. A conflict remains pending for researcher resolution.
