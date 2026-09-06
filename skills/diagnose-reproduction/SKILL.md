---
name: diagnose-reproduction
description: Classify and route a reproduction failure without moving scientific goalposts.
disable-model-invocation: true
---

# Diagnose a reproduction

Start with the tight failing command or artifact and classify it as `software`, `scientific`, `result`, `environment`, or `evidence`. Record the class, evidence, owning loop, and typed return target before proposing work.

Route software to unchanged `diagnosing-bugs`; scientific failures to `scientific-validation`; result mismatches to reproduction analysis; environment failures to Run Bundle repair; and evidence failures to the dossier and its Approval Gate. Preserve preregistered thresholds and approved contracts. Return only to the recorded target after the repair validates.
