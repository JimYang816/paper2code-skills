# V1 Paper-to-Code Skill Bundle

## Problem Statement

Researchers often need to reconstruct a paper from its PDF when the authors released neither code nor a complete experiment package. Ordinary coding workflows do not distinguish statements in the paper from inferred settings, do not force scientific ambiguities to close before implementation, and often treat code execution as proof of reproduction. This is especially risky for AI-based underwater-acoustic channel estimation and equalization, where measured channel replay, propagation simulation, stochastic training, learned baselines, and digitized result curves have different provenance and validation requirements.

The researcher needs a reusable Codex skill workflow that creates one independently managed repository per paper, preserves every scientific decision, supports GitHub Issues as the task graph, produces runnable code through the existing Matt Pocock implementation workflow, and evaluates paper claims without overstating what missing evidence permits.

## Solution

Build a canonical Paper-to-Code Skill Bundle consisting of a domain-independent Reproduction Core, an underwater-acoustics Domain Profile, a deterministic validation toolkit, and a minimal closure of unchanged upstream engineering skills. Major lifecycle stages remain explicitly invoked by the researcher. Versioned YAML contracts and JSON Schemas govern evidence, approvals, state, datasets, runs, and results. The workflow separates paper extraction, ambiguity resolution, specification, implementation, CPU validation, full execution, and claim-level evaluation.

Validate the bundle with isolated fixtures and with the UDNet paper as the anchor reproduction. The anchor uses official Watermark NOF/NCS measurement-driven replay and a source-faithful BELLHOP reconstruction for SIM-B, while excluding unavailable at-sea noise measurements. It reports code correctness, execution completeness, and result agreement separately.

## User Stories

1. As a researcher, I want each paper reproduction to live in an independent Git repository, so that its code, decisions, data manifests, and results can evolve without contaminating the reusable skill bundle.
2. As a researcher, I want setup to scaffold a stable repository structure, so that every stage can find its inputs and outputs predictably.
3. As a researcher, I want setup to initialize local Git when needed, so that a new project begins version-controlled.
4. As a researcher, I want setup to avoid creating GitHub repositories or remotes, so that external repository ownership stays under my control.
5. As a researcher, I want setup to remain pending until an existing GitHub remote and usable GitHub CLI access are verified, so that later skills never silently switch issue trackers.
6. As a researcher, I want GitHub Issues to track decisions, implementation, validation, experiments, and defects, so that work and dependencies remain visible.
7. As a researcher, I want the repository artifacts rather than issue comments to be the scientific record, so that evidence and conclusions are versioned and reviewable.
8. As a researcher, I want one lightweight router to report the current state and legal next stage, so that I do not need to memorize the entire workflow.
9. As a researcher, I want major stages to require explicit invocation, so that extraction, approval, implementation, and costly experiments do not chain unexpectedly.
10. As a researcher, I want machine-checked lifecycle states, so that no stage can proceed on conversational memory alone.
11. As a researcher, I want approvals tied to canonical artifact hashes, so that a later edit invalidates stale approval automatically.
12. As a researcher, I want PDF extraction to preserve page, equation, figure, table, and citation locators, so that every important claim is traceable.
13. As a researcher, I want extraction to produce both readable Markdown and validated structured records, so that I can review the science while tools can enforce completeness.
14. As a researcher, I want every material formula, parameter, dataset setting, network component, and result claim to have a stable evidence identifier, so that later decisions and tests can refer to it unambiguously.
15. As a researcher, I want a second adversarial evidence audit, so that omissions, contradictions, unit errors, and unsupported inferences are found before approval.
16. As a researcher, I want paper evidence distinguished from supporting literature, derivations, user choices, and empirical choices, so that reconstructed details are never presented as author facts.
17. As a researcher, I want all required ambiguities closed as confirmed, derived, reconstructed, empirically selected, or excluded, so that implementation receives no unresolved placeholders.
18. As a researcher, I want a paper-focused grilling stage, so that unresolved scientific decisions are discussed exhaustively before a specification is written.
19. As a researcher, I want large ambiguity sets mapped into decision, research, and scientific-prototype work, so that complex papers can be resolved without losing dependencies.
20. As a researcher, I want scientific prototypes isolated from production code, so that exploratory success cannot bypass specification and testing.
21. As a researcher, I want a Scope Matrix of must, should, and out claims, so that the promised reproduction scope is explicit.
22. As a researcher, I want the paper specification to include method, data, baseline, experiment, and acceptance contracts, so that implementation tickets cannot invent scientific requirements.
23. As a researcher, I want unchanged upstream ticketing and implementation skills, so that the proven vertical-slice, TDD, and code-review workflow remains intact.
24. As a researcher, I want implementation agents forbidden from changing approved scientific contracts, so that tuning code cannot move the goalposts.
25. As a researcher, I want classical baselines governed by explicit Baseline Contracts, so that their equations and paper-specific settings are testable.
26. As a researcher, I want learned baselines without code to receive one-hop mini dossiers, so that comparisons are credible without creating unbounded recursive projects.
27. As a researcher, I want critical mathematical modules checked against independent analytic or NumPy references, so that a PyTorch implementation cannot validate itself.
28. As a researcher, I want mathematical invariants, units, shapes, and gradients checked where applicable, so that scientifically wrong but runnable code fails early.
29. As a researcher, I want every data, model, baseline, metric, and plotting path to run in a reduced deterministic CPU configuration, so that pipeline completeness is established before expensive training.
30. As a researcher, I want paper-scale experiments packaged as self-describing Run Bundles, so that they can run locally or on another approved compute environment.
31. As a researcher, I want runs to preserve resolved configuration, environment, code revision, dataset hashes, seeds, logs, metrics, and outputs, so that results can be audited and repeated.
32. As a researcher, I want learned Full Runs to use multiple seeds by default, so that result variability is visible rather than hidden behind one favorable run.
33. As a researcher, I want a budget-approved single run to remain reportable with lower evidence strength, so that limited compute does not force a false claim of certainty.
34. As a researcher, I want paper curves digitized with calibration, raw points, cross-checks, and uncertainty, so that result tolerances have documented evidence.
35. As a researcher, I want result metrics and tolerances frozen before inspecting final model results, so that acceptance is preregistered.
36. As a researcher, I want every scoped claim evaluated separately along implementation, execution, and result-agreement axes, so that one successful plot cannot hide missing work.
37. As a researcher, I want overall outcomes limited to replicated, partially replicated, not replicated, or inconclusive, so that conclusions match the available evidence.
38. As a researcher, I want failures classified before new work is created, so that software defects, scientific failures, environment failures, evidence failures, and result mismatches return to the correct loop.
39. As a researcher, I want missing capabilities reported without automatic installation, so that I retain control over environments, licenses, and downloads.
40. As a researcher, I want raw large datasets excluded from Git but identified by source, license, expected files, hashes, and preparation recipes, so that the repository remains usable without losing provenance.
41. As a researcher, I want the same named benchmark or simulator used as the target paper, so that convenient substitutes are not mislabeled as reproductions.
42. As a researcher, I want official Watermark V1 to serve as the reference oracle for Python replay work, so that portability does not erase source fidelity.
43. As a researcher, I want incompletely specified BELLHOP data labelled as a source-faithful reconstruction, so that using the same simulator is not confused with regenerating identical author samples.
44. As a researcher, I want every reproduction repository to contain its selected core skills, Domain Profiles, and full dependency closure, so that it is portable and self-describing.
45. As a researcher, I want a skills lock containing origins, hashes, dependency edges, and modification classifications, so that copied and adapted skills are auditable.
46. As a researcher, I want skill upgrades previewed and explicitly approved, so that canonical improvements do not overwrite project-specific work.
47. As a maintainer, I want repeated mechanical checks implemented once in a deterministic toolkit, so that skills do not calculate hashes or interpret schemas inconsistently.
48. As a maintainer, I want concise skill entrypoints with conditional detail in references and deterministic work in scripts, so that agent context remains focused.
49. As a maintainer, I want skill package, contract, behavioral, and anchor-level tests, so that valid frontmatter is not mistaken for a reliable workflow.
50. As a maintainer, I want independent behavioral forward tests for risky skills, so that evaluation does not leak the expected decisions to the acting agent.
51. As a researcher, I want v1 to target Codex while retaining platform-neutral scientific artifacts, so that future agent adapters do not require redesigning the reproduction record.
52. As the UDNet researcher, I want v1 to reproduce the agreed M0 through M2 simulation scope, so that the workflow is proven on the paper I currently need rather than only on artificial examples.

## Implementation Decisions

- Maintain a canonical Skill Bundle Repository and create one independent Reproduction Repository per target paper.
- Provide a Reproduction Core and additive Domain Profiles. The first profile covers underwater-acoustic communications, OFDM equalization, measured channel replay, propagation simulation, SER evaluation, and complex-to-real model checks.
- Implement user-invoked Stage Skills for setup, extraction, paper grilling, paper wayfinding, paper specification, scientific prototyping, CPU validation, full-run preparation, execution, evaluation, reproduction diagnosis, and skill upgrades. Provide a user-invoked router that reports state and points to the next Stage Skill without silently invoking it.
- Reuse the upstream grilling, domain-modeling, research, to-tickets, implement, tdd, codebase-design, code-review, and diagnosing-bugs skills unchanged. Audit their complete dependency closure before copying.
- Package shared schemas, templates, references, and the Deterministic Toolkit as a Support Skill. Other workflow skills declare and lock their dependency on it.
- Keep skill entrypoints concise. Put conditional scientific rules and schemas in references, deterministic transformations in scripts, and generated-project templates in assets only when they have a concrete consumer.
- Use YAML for editable machine records, versioned JSON Schema for validation, and canonical JSON for approval and identity hashes.
- Use the approved state chain from setup pending through evaluated, with typed exception states and validated return targets.
- Record approval scope, artifact hashes, schema versions, timestamp, and authorized transition in each Gate Record. Only the researcher may approve a gate.
- Treat Git artifacts as the Scientific Record and GitHub Issues as the Operational Task Graph. Provision reproduction-specific issue-type labels, readiness labels, sub-issues, and dependency edges with documented fallbacks.
- Make extraction self-contained at the skill-package level. It performs capability checks, extracts text and layouts, renders pages and figures, supports OCR paths, builds stable Evidence Items, and completes a second adversarial Evidence Audit.
- Use a hybrid Paper Dossier containing human-readable Markdown, structured evidence and ambiguity records, visual assets, source manifests, dataset contracts, experiment matrices, digitization records, and the preliminary Scope Matrix.
- Preserve the target PDF as the authority for what the target paper reported. Supporting sources can explain concepts but cannot silently fill target-paper omissions.
- Require every required ambiguity to reach a terminal Evidence Resolution before specification approval. Reconstruction alternatives and empirical choices retain provenance.
- Produce an implementation-ready paper specification from the approved dossier and decisions. Use the unchanged ticketing and implementation workflow only for code and ordinary implementation tests.
- Separate TDD and code review from Scientific Validation. Scientific Validation owns independent numerical references, invariants, reference-oracle comparisons, stochastic checks, digitization uncertainty, and result criteria.
- Keep project experiment tooling configurable. Every accepted run exports the same portable Resolved Run Configuration and provenance regardless of whether the project selected Hydra, MLflow, DVC, or simpler tools.
- Never install dependencies. Capability Checks produce actionable Capability Reports and leave the workflow in a recoverable state.
- Keep raw and large derived data out of Git by default. Commit Dataset Manifests, licenses, hashes, recipes, and small deterministic fixtures. DVC remains an optional profile rather than a core dependency.
- Freeze result-matching metrics, points, uncertainty, tolerances, repeat count, and aggregation rules before final target-model results are inspected.
- Aggregate Claim Verdicts only after assessing each must claim. A decisive mismatch requires successful execution and adequate evidence; unavailable information or inadequate power produces an inconclusive verdict rather than a forced failure.
- For the UDNet anchor, use official Watermark NOF/NCS replay and official Watermark output as the Reference Oracle for any Python adapter. Use BELLHOP for SIM-B but label it as a reconstructed environment because the target paper omits necessary inputs.
- The UDNet v1 scope includes UDNet, ZF, MMSE, DFE, and SCN; NOF, NCS, and reconstructed SIM-B; quasi-static and time-varying channels; imperfect CSI, clipping, subcarrier-count, and complexity comparisons. SDRNet, modified DetNet, exact synchronization-offset reproduction, and unavailable author-recorded noise are outside v1.
- License new skills and code under MIT, preserve upstream attribution and modification status, and keep paper, dataset, simulator, and licensed-tool terms separate.
- Target Codex skill packaging in v1 while avoiding an OpenAI API dependency in the Scientific Record and deterministic tooling.

## Testing Decisions

- Validate each skill package for correct naming, frontmatter, referenced resources, invocation policy, and absence of unfinished scaffolding.
- Test the Deterministic Toolkit at its external command and artifact seams: valid and invalid schemas, canonical hash stability, stale approval detection, legal and illegal state transitions, dependency-closure resolution, manifest verification, and Run Bundle completeness.
- Test setup in isolated repositories representing an empty directory, a local Git repository without a remote, a GitHub-backed repository, a rerun, and a repository containing user files. External GitHub writes use mocks or disposable isolated fixtures rather than production repositories.
- Test extraction against small representative PDFs covering native text, scanned pages, equations, multi-panel plots, tables, missing metadata, conflicting statements, and incomplete citations. Assert evidence coverage and artifact validity rather than exact prose.
- Test paper grilling and specification with ambiguity fixtures that require confirmed, derived, reconstructed, empirically selected, and excluded resolutions. Assert that required unknowns and stale approvals block downstream stages.
- Test state routing from every normal and exception state, including recovery to the typed return target.
- Test implementation boundaries by confirming that implementation tickets cannot alter approved scientific contracts and that code completion does not advance scientific or result gates.
- Test Scientific Validation with analytic communication-system fixtures, independent numerical references, gradient checks, controlled random distributions, known-equivalent waveforms, and intentional scientific faults.
- Test Run Bundles with missing seeds, changed datasets, dirty code revisions, incomplete logs, and non-identical resolved configurations.
- Test result evaluation with replicated, partial, decisive mismatch, and inconclusive fixtures, including digitization uncertainty and single-run evidence downgrades.
- Run Behavioral Forward Tests in isolated temporary repositories for complex Stage Skills. Give the evaluator only the realistic request, skill bundle, and raw inputs; do not provide the desired decision or previous diagnosis.
- Dogfood v1 on the UDNet paper. The first anchor checkpoint covers extraction through approved specification; the second covers tickets through the complete reduced CPU pipeline; final scientific acceptance uses approved Full Runs and claim-level reports.

## Out of Scope

- Automatically creating or connecting GitHub repositories and accounts.
- Automatically installing open-source, proprietary, or licensed dependencies.
- Committing or redistributing large raw datasets, paper PDFs, restricted artifacts, or third-party software without applicable rights.
- Treating Watermark replay as a purely synthetic channel generator.
- Claiming identity with the authors' SIM-B samples without their original BELLHOP environment.
- Reconstructing the unavailable Nanpeng Island at-sea noise experiment.
- UDNet SDRNet, modified DetNet, and exact synchronization-offset experiments in v1.
- Replacing the unchanged upstream ticketing, implementation, TDD, or code-review semantics with a monolithic paper workflow.
- Requiring Hydra, MLflow, DVC, MATLAB, or a particular compute service for every reproduction project.
- Full production support for non-Codex agent platforms in v1.
- Automatically tuning implementations or acceptance thresholds to match published curves.

## Further Notes

- The v1 build should optimize for a thin, coherent vertical workflow rather than maximizing skill count. A proposed skill may be folded into a neighboring Stage Skill when its responsibility remains explicit and invocation semantics improve.
- The current upstream skills lock is an inventory input, not the final Skill Closure; unrelated entries must be removed after dependency analysis.
- The target paper is the anchor and first consumer, not a template whose underwater-specific assumptions should leak into the Reproduction Core.
- Full scientific replication remains contingent on access to official Watermark, suitable BELLHOP tooling, approved compute, and the final stochastic runs. Missing licensed capabilities produce explicit pending or inconclusive states rather than fabricated substitutes.
