# Wayfinding map

`decisions/frontier.yaml` is the machine-checkable representation of the
decision frontier:

```yaml
schema_version: "1.0"
ambiguities:
  - id: AMB-0001
    work:
      - id: AMB-0001:decision
        kind: decision
        title: Choose the imperfect-CSI variance model
        issue: "42"
frontier:
  - id: AMB-0001:decision
    kind: decision
    title: Choose the imperfect-CSI variance model
    issue: "42"
    blocked_by: []
```

`ambiguities[*].work` records every dependent work item for one ambiguity.
`frontier` is the set whose blockers are all complete and that can be worked
now. An item leaves the frontier only when its outcome is recorded as an
Evidence Resolution; the dependency edge remains visible in the issue graph.

Do not use this file as a substitute for GitHub Issues. It is the Scientific
Record copy of the Operational Task Graph and must agree with the tracker.
