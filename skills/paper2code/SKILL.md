---
name: paper2code
description: Report a reproduction repository's validated state and next legal paper-to-code stage.
disable-model-invocation: true
---

# Paper-to-Code router

Read [the lifecycle contract](../paper2code-core/references/lifecycle.md). Run `python skills/paper2code-core/scripts/paper2code.py route .paper2code/state.yaml`, then validate the artifacts and Gate Record required by the current state. Report blockers and the named next Stage Skill.

Stop after routing. Do not invoke the next stage, approve a gate, create tickets, run experiments, or change lifecycle state.
