# Use portable manifests and tool-agnostic runs

The Reproduction Core will not require Hydra, MLflow, DVC, or another experiment platform. A project specification may select them, but every accepted run must export the same portable evidence: a Resolved Run Configuration, code revision, locked environment, random seeds, Dataset Manifest identities and hashes, commands, logs, metrics, and outputs.

Large raw and derived data stay outside Git. The Scientific Record commits official source locations, license findings, expected file hashes, preparation recipes, and small deterministic fixtures; a DVC Domain Profile may add storage orchestration without becoming a core dependency.

The PDF extraction skill is self-contained at the skill-package level: it carries or declares the extraction, rendering, OCR, equation, and figure-processing resources it needs and runs a Capability Check before changing state. It must not assume that a particular globally installed PDF skill exists on the researcher's machine.

Workflow skills never install dependencies. A failed Capability Check produces a Capability Report with pinned requirements and commands for the researcher to run, then stops in a recoverable state. This applies to open-source packages as well as licensed software; MATLAB, accounts, licenses, and restricted downloads remain explicitly user-managed.
