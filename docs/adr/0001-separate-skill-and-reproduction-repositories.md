# Separate skill and reproduction repositories

This repository will own the canonical reusable skills, while each paper will be reconstructed in an independently managed Reproduction Repository initialized by the setup skill. Mixing reusable workflow definitions with paper-specific code, data, and results would make both versioning and reuse ambiguous.

The setup skill runs at the target repository root and may initialize a local Git repository after showing its intended changes. It will not create a GitHub repository, add a remote, or connect an account. GitHub Issues is the required issue tracker, so setup remains in `setup_pending` until an existing GitHub remote and usable `gh` access can be verified; it will not silently fall back to a local tracker.

Version-controlled artifacts are the Scientific Record. GitHub Issues form the Operational Task Graph and link to exact artifact versions or hashes; issue bodies and comments must not become the only copy of evidence, scientific decisions, contracts, or conclusions.

Setup provisions the reproduction-specific issue vocabulary: `paper2code:evidence`, `paper2code:decision`, `paper2code:implementation`, `paper2code:validation`, `paper2code:experiment`, and `paper2code:defect`, together with readiness labels such as `ready-for-agent`, `ready-for-human`, and `needs-info`. It prefers GitHub sub-issues and native dependencies, with an explicit text fallback when the repository does not expose those features.
