---
name: paper2code-router
description: Report the validated Paper-to-Code state and its legal next Stage Skills.
disable-model-invocation: true
---

# Route the Paper-to-Code lifecycle

Work at the target Reproduction Repository root. Run the read-only router:

```sh
python skills/paper2code-core/scripts/paper2code.py route --root .
```

The result validates the current state and the artifacts needed at that
boundary, then lists only legal next Stage Skills. A `ready: false` route is
blocked by the reported validation errors; repair the named artifacts with the
appropriate Stage Skill and route again. `paper-diagnosis` routes include the
typed exception `return_target` from `.paper2code/state.yaml`.

The router never invokes a Stage Skill, edits state, consumes an approval, or
changes the Scientific Record. Approval gates remain explicit researcher
actions.
