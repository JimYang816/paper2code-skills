# Test skills at format, contract, behavior, and anchor levels

The v1 bundle requires four distinct checks: skill-package validation; automated tests of schemas, hashes, state transitions, manifests, and the Deterministic Toolkit; isolated behavioral scenarios in temporary repositories; and an anchor acceptance path using the UDNet paper. Tests assert observable decisions, invariants, and artifact validity rather than exact generated prose.

Complex or scientifically risky skills receive Behavioral Forward Tests from independent subagents that are given no intended answer. These tests may write only to isolated temporary repositories and may not mutate real GitHub projects, fetch restricted data, or operate licensed tools. The initial platform target is Codex skill packaging, while the Scientific Record, schemas, CLI contracts, and repository layout remain platform-neutral for possible future adapters.
