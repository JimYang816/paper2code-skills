# Generic Skill Bundle validation — issue #11

Scope: the generic Skill Bundle before the UDNet anchor. The pre-agreed test
seams are the public commands and Scientific Record artifacts in the parent
specification's Testing Decisions. ADR-0011 distinguishes package checks,
deterministic checks, independent behavior, and anchor acceptance.

## Repeatable automated checks

From the bundle root, using existing Python and Git:

```sh
python skills/paper2code-core/scripts/verify_closure.py --root .
python -m unittest discover -s tests -v
git diff --check
```

Final stable-bundle run after review fixes: **86 tests passed** in 154.708
seconds. The offline
verifier accepted all **22 skills**, closure hashes and licenses; `git diff
--check` passed. An earlier run overlapped edits to the extraction skill and
failed on transient lock mismatches; it is superseded by this complete run.

There is no configured type checker. The package and CLI tests import/execute
the changed Python paths. Tests use `.scratch/test-tmp/<unique-id>` disposable
repositories. GitHub-facing setup tests substitute the external CLI; experiments
use tiny local scripts and data. They perform no dependency installation,
restricted download, or real GitHub mutation. Assertions concern decisions,
artifact validity and invariants, rather than exact agent-generated prose.

| Coverage | Executable evidence |
| --- | --- |
| Package frontmatter, invocation policy, linked resources | `test_skill_package.py` |
| Closure, licenses, byte identity, tampering | `test_skill_closure.py` and verifier |
| Hashes, schemas, legal/illegal transitions | `test_setup_toolkit.py` |
| Empty/local/GitHub-backed setup, reruns, preserved files | `test_setup.py` (GitHub mocked) |
| Native/scanned page paths, OCR provenance, missing capabilities | `test_extract.py` and synthetic PDFs |
| Contradictions, missing references, inference and audit findings | `test_extract.py` |
| All terminal Evidence Resolutions, required unknowns, stale gates | `test_evidence_gate.py`, `test_specification.py` |
| Every normal/exception route, upgrade conflicts | `test_router.py`, `test_skill_upgrade.py` |
| CPU paths, scientific faults, implementation-only gate rejection | `test_validation.py` |
| Dirty revisions, stale approval, datasets, seeds, logs | `test_full_run.py` |
| All four Replication Outcomes, single-seed downgrade, typed diagnosis | `test_evaluation.py` |

Review identified two missing numerical scenarios, subsequently added:
`test_validation.py` now runs the DFT channel against an independent time-domain
reference, checking impulse/zero/scaling invariants, shapes, analytic versus
finite-difference gradients and seeded Gaussian output variance. A 10% gain
fault must route to scientific diagnosis. `test_evaluation.py` now tests a
hash-bound digitization record with nonzero uncertainty: a target at the
uncertainty boundary agrees, one outside does not, and evidence is capped at
moderate strength. Focused validation/evaluation suites passed (9 and 12 tests).

Independent code review after these additions: Standards **0 findings**;
Spec **0 remaining findings**. The two initial Spec findings (real numerical
validation and nonzero digitization uncertainty) were resolved and re-reviewed.

## Independent Behavioral Forward Tests

Run date: 2026-09-09. Actors were separate agents started with no inherited
conversation. Each received only a realistic request, candidate skills, its raw
inputs and disposable workspace, plus operational restrictions. They were
explicitly excluded from tests, issue specifications and other actors' work.
No desired verdict, diagnosis or expected artifact prose was included.

To repeat, provision fresh disposable inputs, dispatch the corresponding request
to a fresh agent with read access only to those inputs and candidate skills, and
permit writes only within that disposable workspace. Require commands,
observations and artifact verification in `forward-observations.md`. Evaluate
the observation against the specification only after the actor finishes; keep
this report and the automated assertions out of the acting agent's context.

All actors were instructed to stay offline, use installed tools, avoid real
GitHub operations, installs, restricted data and licensed tools, and preserve
researcher approval boundaries. Prepared Gate Records were synthetic fixture
inputs, not approval of a real scientific experiment.

| Raw input and request | Observed result |
| --- | --- |
| Folder containing `notes.txt`: “Set up this folder as a Reproduction Repository with the local Skill Bundle, preserve my notes, and tell me which stage I can invoke next.” | Setup applied without conflicts; notes preserved; 22-skill closure verified. State `setup_pending`; router selected setup; no remote or labels created. |
| Completed local Run Bundle, one seed, metric 6, target 6, high minimum strength: “The run is complete. Evaluate whether this paper claim was replicated and explain the evidence.” | Evaluation and verification succeeded. Implementation, execution and result agreement passed; Evidence Strength low; outcome `inconclusive`; state `evaluated`. |
| Native/scanned PDFs: “Extract and audit these two versions of my paper into separate dossiers, preserving unresolved scientific details.” | Initial actor stopped both paths for missing OCR, exposing disagreement between blanket skill wording and the native-or-OCR requirement. Fixed the checker and wording; added a regression that first failed with exit 3 and then passed. |

The same extraction actor repeated the request against the revised candidate in
fresh repositories, without being given an intended outcome. Native extraction
used real installed parsing/rendering tools: two text pages, eight Evidence
Items and seven triaged audit findings; validation and finalization reached
`evidence_extracted`. Conflicting training rates and missing citations remained
explicitly unresolved rather than silently filled. The scanned version yielded
two renders and no text; the actor retained its incomplete dossier and open
audit finding in `ready_for_extraction` because OCR was unavailable. Extraction
finalization did not approve an Evidence Gate.

The PDF fixtures subsequently gained original vector panel curves (and matching
scanned raster pages) during review. The independent extraction observations
above apply to the initial text/caption fixture; automated extraction checks
also cover the final illustrated files.

Setup and evaluation actors recorded commands and inspected state/artifacts in
`.scratch/forward-11/`. The evaluation actor's initial write was sandbox-denied;
an authorized retry within its disposable workspace succeeded. No scientific
gate was fabricated in response to that execution limitation.

Automated OCR tests use external-tool doubles. They do not establish real OCR
accuracy. The UDNet anchor and paper-scale scientific replication remain
separate acceptance work; none is claimed by this generic validation.
