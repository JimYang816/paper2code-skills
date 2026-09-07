# Paper-to-Code Workflow

A reusable workflow for independently reconstructing and evaluating research-paper implementations when the original code or data may be unavailable.

## Language

**Skill Bundle Repository**:
The repository that owns the canonical reusable paper-to-code skills and their domain profiles. It contains no paper-specific implementation or experimental results.
_Avoid_: Paper project, reproduction project

**Reproduction Repository**:
An independently managed repository devoted to reconstructing and evaluating one paper.
_Avoid_: Skill repository, shared workspace

**Reproduction Core**:
The domain-independent workflow for evidence collection, decision making, specification, implementation, execution, and evaluation.
_Avoid_: Underwater-only workflow, paper template

**Domain Profile**:
A collection of domain-specific vocabulary, evidence fields, scientific checks, and acceptance guidance layered onto the Reproduction Core.
_Avoid_: Core workflow, paper template

**Evidence Item**:
A traceable statement extracted or derived from a source, with its source location and provenance class preserved.
_Avoid_: Note, known fact

**Paper Evidence**:
Evidence stated directly in the target paper PDF, which is authoritative for claims about that paper's reported method and experiments.
_Avoid_: Supporting source, inferred setting

**Supporting Source**:
A cited publication or official technical document used to interpret Paper Evidence but not to silently supply settings absent from the target paper.
_Avoid_: Paper evidence, implementation truth

**Paper Dossier**:
The combined human-readable and machine-checkable account of Paper Evidence, Supporting Sources, figures, tables, ambiguities, and provenance for one paper.
_Avoid_: Paper summary, notes

**Reconstruction Decision**:
An explicitly approved choice that fills information absent or ambiguous in the available evidence without presenting that choice as an original-paper fact.
_Avoid_: Paper setting, confirmed fact, guess

**Replication Outcome**:
The evidence-backed conclusion `replicated`, `partially replicated`, `not replicated`, or `inconclusive` for an agreed scope.
_Avoid_: Pass/fail, code complete

**Scope Matrix**:
The approved classification of paper claims, methods, baselines, ablations, and results as `must`, `should`, or `out` for a Reproduction Repository.
_Avoid_: To-do list, implementation plan

**Approval Gate**:
A boundary that prevents work from proceeding until the researcher approves the scientific decisions, replication contract, or full-experiment budget that gate the next stage.
_Avoid_: Status update, optional review

**Run Bundle**:
A self-describing full-experiment package whose configuration, environment, commands, logs, and outputs can be executed locally or handed to another compute environment and later evaluated.
_Avoid_: Script, checkpoint folder

**Source-Faithful Dataset**:
A dataset obtained from the same named released benchmark or generated with the same named simulator as the target paper, with any unrecoverable configuration differences explicitly recorded.
_Avoid_: Similar dataset, representative data

**Measurement-Driven Channel Replay**:
A repeatable channel simulation driven by released impulse responses measured at sea, such as Watermark's Mime-based replay.
_Avoid_: Synthetic channel, at-sea experiment

**Propagation-Synthesized Channel**:
A channel constructed from an explicit propagation environment using a numerical model such as BELLHOP.
_Avoid_: Measured channel, exact author dataset

**At-Sea Measurement Experiment**:
An experiment that depends on signals, noise, or channel observations collected by physical equipment at sea rather than on a released replay benchmark.
_Avoid_: Watermark replay, simulated channel

**Skill Closure**:
The minimal set containing every workflow skill selected for this project and every skill it transitively requires, stored canonically under this repository's `skills/` directory.
_Avoid_: All upstream skills, externally installed dependency

**Reference Oracle**:
An authoritative implementation or independently trusted calculation used to test whether a reconstructed or ported component is numerically equivalent within an approved tolerance. For the anchor paper, official Watermark V1 is the Reference Oracle for any Python replay implementation.
_Avoid_: Example output, presumed equivalent implementation

**Baseline Contract**:
The evidence, equations, paper-specific settings, expected behavior, and acceptance checks that define one comparison method without requiring every baseline to become a full reproduction project.
_Avoid_: Baseline name, approximate implementation

**Result Preregistration**:
The frozen result-matching metrics, tolerances, random-repeat policy, and target points approved after evidence extraction and baseline calibration but before inspecting the target model's final results.
_Avoid_: Post-hoc threshold, visual similarity

**CPU Validation Gate**:
The requirement that every data, model, baseline, metric, and reporting path complete end to end under a deterministic reduced configuration on a local CPU. It does not require paper-scale training on the CPU.
_Avoid_: Import test, full experiment

**Full Run**:
An experiment executed at the approved paper-scale or declared reconstruction scale after the CPU Validation Gate passes, normally through a reproducible Run Bundle on suitable compute.
_Avoid_: Smoke test, development run

**Scientific Validation**:
Evidence that scientific software satisfies formula-level examples, invariants, reference-oracle comparisons, statistical expectations, and preregistered result criteria beyond ordinary software correctness.
_Avoid_: Unit testing, code review, successful execution

**Workflow State**:
The machine-checkable current lifecycle stage and exception state of a Reproduction Repository, recorded in `.paper2code/state.yaml` and advanced only when its required artifacts and approvals validate.
_Avoid_: Progress note, inferred project status

**Gate Record**:
The durable record of a researcher's approval of a versioned artifact set, including the approved scope, artifact hashes, approval time, and the workflow transition it authorizes.
_Avoid_: Conversation memory, unchecked checkbox

**Evidence Audit**:
The second, adversarial pass over a Paper Dossier that checks every paper section, page, equation, figure, table, citation dependency, unit, contradiction, and inference for omissions or misclassification.
_Avoid_: Initial extraction, proofreading

**Failure Class**:
The first routing decision after a failed check or run: `software`, `scientific`, `result`, `environment`, or `evidence`. The class determines which diagnostic loop may propose a change.
_Avoid_: Failed test, implementation bug

**Resolved Run Configuration**:
The fully expanded, immutable configuration actually used by a run, accompanied by code revision, environment, seed, and dataset hashes independently of the configuration framework that produced it.
_Avoid_: Default settings, command-line history

**Scientific Record**:
The version-controlled Paper Dossier, decisions, specifications, contracts, configurations, and reports that are authoritative for what was known, approved, executed, and concluded.
_Avoid_: Issue body, chat history, task status

**Operational Task Graph**:
The GitHub Issues graph used to coordinate decisions, implementation, validation, experiments, and defects while linking back to versioned Scientific Record artifacts.
_Avoid_: Scientific record, paper dossier

**Dataset Manifest**:
The committed record of a dataset's identity, origin, license, expected files, hashes, preparation recipe, and availability without committing restricted or large raw payloads.
_Avoid_: Data folder, download note

**Claim Verdict**:
The three-axis assessment of one scoped paper claim: implementation correctness, execution completeness, and result agreement, together with its evidence and uncertainty.
_Avoid_: Paper score, test status

**Capability Check**:
A startup check that proves the executables, libraries, formats, and optional licensed tools required by a skill's selected path are available before the skill mutates project state.
_Avoid_: Dependency assumption, failed runtime import

**Evidence Resolution**:
The terminal disposition of an ambiguity as `confirmed`, `derived`, `reconstructed`, `empirically_selected`, or `excluded`. Every `must` item needs a terminal resolution before specification approval.
_Avoid_: Resolved, probably known, implementation choice

**Independent Numerical Reference**:
A deliberately separate analytic or small-scale implementation, commonly NumPy or hand-calculated, used to test a production mathematical component without reusing that component's logic.
_Avoid_: Second call to the implementation under test, training curve

**Digitization Record**:
The reproducible package for a paper figure's extracted values: source page and crop, axis calibration, points, method or tool, reviewer check, and estimated extraction uncertainty.
_Avoid_: CSV, eyeballed curve

**Scientific Prototype**:
An isolated disposable experiment that answers one named scientific decision question and may contribute evidence, but cannot enter production code without specification, tickets, and implementation validation.
_Avoid_: First implementation, exploratory production code

**Evidence Strength**:
The declared strength of a Claim Verdict after accounting for provenance, repeat count, variability, digitization uncertainty, and validation coverage. A single stochastic run cannot receive the highest Evidence Strength.
_Avoid_: Confidence score without criteria, replication outcome

**Deterministic Toolkit**:
The repository-local Python utilities called by workflow skills for schema validation, canonical hashing, legal state transitions, skill-closure verification, manifests, Gate Records, and Run Bundle checks. It makes no scientific decisions and is not the workflow orchestrator.
_Avoid_: Agent, router, experiment framework, user-facing application

**Stage Skill**:
A user-invoked skill that advances one major reproduction lifecycle stage, such as extraction, grilling, specification, implementation, validation, execution, or evaluation.
_Avoid_: Automatically chained workflow, support library

**Support Skill**:
A reference, profile, or deterministic capability invoked from a Stage Skill because that stage genuinely needs it; it does not independently advance the lifecycle.
_Avoid_: User-facing stage, hidden workflow transition

**Behavioral Forward Test**:
An isolated evaluation in which an independent agent receives a realistic request, the candidate skill, and only the raw artifacts it would normally have, so its decisions and generated artifacts can be assessed without leaking the intended answer.
_Avoid_: Unit test, self-review, expected-output prompt

**Skill Upgrade**:
A previewed, user-approved change from one pinned Skill Closure to another that preserves project artifacts, reports local conflicts, and updates the skills lock only after verification.
_Avoid_: Setup rerun, overwrite, automatic update

**Capability Report**:
The non-mutating list of available and missing executables, libraries, licensed tools, versions, and next-step installation commands produced when a workflow path cannot run.
_Avoid_: Automatic dependency installation, generic error
