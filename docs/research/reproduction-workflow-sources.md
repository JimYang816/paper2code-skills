# Paper-to-code workflow: primary-source findings

Researched on 2026-09-06 to inform the design of this repository's paper-replication skills.

## Findings that should shape the workflow

### Grade code, execution, and scientific results separately

OpenAI's PaperBench evaluates paper replication with a hierarchical rubric whose leaves are divided into three requirement types: **Code Development**, **Execution**, and **Result Match**. It runs agent development, fresh-environment reproduction, and rubric grading as separate stages. Its paper package also keeps the paper in PDF and Markdown, supporting assets, an author addendum, and a machine-readable rubric together. This is the strongest directly relevant model for this project.

Design implication: do not let an implementation ticket or CPU smoke test claim scientific replication. Use separate gates and preserve partial credit.

Sources:

- [PaperBench overview](https://openai.com/index/paperbench/)
- [PaperBench repository and pipeline](https://github.com/openai/frontier-evals/tree/main/project/paperbench)
- [PaperBench paper](https://cdn.openai.com/papers/22265bac-3191-44e5-b057-7aaacd8e90cd/paperbench.pdf)

### Make every accepted claim traceable to evidence

The NeurIPS paper checklist asks for stated assumptions and limitations, exact commands and environments, data splits, hyperparameters and how they were chosen, statistical significance, sources of variation, and compute resources. It also says that the reproducible subset should be stated when only part of the experiments can be reproduced.

Design implication: extraction should create an evidence ledger with source locations and provenance, not only a prose summary. Unknown details chosen by the user remain explicit reconstruction assumptions; discussion cannot turn them into facts about the authors' implementation.

Sources:

- [NeurIPS Paper Checklist Guidelines](https://neurips.cc/public/guides/PaperChecklist)
- [NeurIPS Code and Data Submission Guidelines](https://neurips.cc/public/guides/CodeSubmissionPolicy)

### Treat partial and failed replications as valid outcomes

ReScience C requires rigorous methodology, original source code, and substantial evidence for replication or an explanation of why replication failed. Its review criterion is practical: independent reviewers must be able to run the code and obtain the advertised results. The NeurIPS/MLRC reproducibility track likewise accepts positive, partial, and failed replications.

Design implication: acceptance must support `replicated`, `partially replicated`, `not replicated`, and `inconclusive`; repeatedly regenerating implementation tickets is wrong when the gap is caused by missing information, inaccessible data, insufficient compute, or an unsupported paper claim.

Sources:

- [ReScience C submission process and criteria](https://rescience.github.io/write/)
- [NeurIPS/MLRC Call for Reproducibility](https://neurips.cc/Conferences/2026/CallForReproducibility)

### Require a complete research-code package

The Papers With Code/NeurIPS research-code checklist requires dependency specification, training code, evaluation code, pretrained models, and a README with a result table plus exact reproduction commands. Yahoo's training-recipe guidance adds raw-data provenance, preprocessing and split construction, optimization details, training dynamics, target metrics, hardware/timing, and commit identifiers.

Design implication: the workflow's final artifact is more than `src/`; it includes executable recipes, manifests, logs, result tables, and provenance.

Sources:

- [ML Code Completeness Checklist](https://github.com/paperswithcode/releasing-research-code)
- [Training Recipes for Reproducible Machine Learning Models](https://github.com/yahoo/ml-reproducibility-guidelines)

### Version experiment inputs and outputs together

DVC models data pipelines as stages with dependencies and outputs and provides experiment comparison/versioning. Hydra provides hierarchical, composable configuration and command-line overrides for multi-run experiments. MLflow Tracking records run metadata, parameters, code versions, metrics, and artifacts.

Design implication: define a small, optional experiment-provenance interface in the skills rather than hard-coding one heavy MLOps stack. A target repository may implement the interface with plain manifests first, then DVC/Hydra/MLflow when scale justifies them.

Sources:

- [DVC data pipelines](https://doc.dvc.org/start/data-pipelines/data-pipelines)
- [DVC experiment management](https://doc.dvc.org/start/experiments)
- [Hydra getting started](https://hydra.cc/docs/intro/)
- [MLflow Tracking](https://mlflow.org/docs/latest/tracking)

## Recommended synthesis

Use Matt Pocock's skills for conversation discipline, domain language, specifications, dependency-aware tickets, test-first implementation, and code review. Add a scientific layer inspired by PaperBench and reproducibility checklists:

1. Evidence extraction with page/equation/table/figure citations and an ambiguity ledger.
2. A human decision gate that resolves every blocking ambiguity without erasing its provenance.
3. A machine-readable replication contract and hierarchical acceptance rubric.
4. Scientific tracer-bullet tickets organized around claims and experiments.
5. Separate code-development, execution, and result-match gates.
6. Gap diagnosis that can produce implementation fixes, assumption revisions, scope changes, or a documented negative/inconclusive result.
7. A clean-environment reproduction entry point and a final evidence-backed replication report.

## Anchor-paper source audit: UDNet

The anchor paper is *Model-Driven Based Deep Unfolding Equalizer for Underwater Acoustic OFDM Communications* (IEEE Transactions on Vehicular Technology, 2023, DOI 10.1109/TVT.2022.3230143).

The paper identifies the NOF and NCS channel impulse responses as measurements from the Watermark benchmark. FFI's official Watermark page currently offers WatermarkV1 as a free download and says that the release contains measured channels in three frequency bands and four environments. The Watermark manual identifies the benchmark as MATLAB software, requiring MATLAB R2012b or newer and the Signal Processing Toolbox. It is therefore a measurement-driven channel replay system rather than a purely synthetic dataset generator, and any Python adapter or port needs an explicit equivalence check against the official implementation before it can be described as Watermark-faithful.

The BELLHOP manual confirms that an environment file must specify the sound-speed profile, bottom properties, source and receiver geometry, frequency, and run options. The UDNet paper reports only a subset of those inputs for SIM-B. Using BELLHOP can preserve simulator provenance, but absent the original environment files it cannot establish identity with the authors' exact SIM-B samples. The authors' self-collected Nanpeng offshore noise remains a separate unavailable source and is excluded from the simulation-only anchor scope.

Sources:

- [FFI Watermark benchmark and download](https://www.ffi.no/en/research/watermark)
- [FFI Watermark manual and user's guide](https://www.ffi.no/en/publications-archive/the-watermark-manual-and-users-guide-version-1.0)
- [Watermark benchmark paper](https://ieeexplore.ieee.org/document/7932436)
- [BELLHOP manual](https://oalib-acoustics.org/website_resources/Rays/HLS-2010-1.pdf)
- [arlpy BELLHOP interface documentation](https://arlpy.readthedocs.io/en/latest/uwapm.html)
