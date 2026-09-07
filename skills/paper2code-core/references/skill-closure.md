# Skill Closure contract

`skills-lock.yaml` is the distribution lock; its JSON syntax is a YAML 1.2 subset
that permits verification with Python's standard library. `skills-lock.json`
is the pre-existing development installation inventory, not a distribution input.

Copy the entire `skills/` directory, `skills-lock.yaml`, `LICENSE`,
`THIRD_PARTY_NOTICES.md`, `.gitattributes`, and `licenses/` together. Verify the destination with
the same command before exposing the skill directories to Codex. Repository
setup and later paper-specific Stage Skills are delivered by separate tickets;
this initial closure supplies the agreed upstream workflow and its verifier.

The supplied `.gitattributes` preserves locked bytes after Git checkout. For an
existing destination attributes file, preserve its rules and merge the supplied
rules as a reviewed local adaptation; update its distribution hash explicitly
only after checking that the effective attributes preserve all locked files.

The lock lists explicit roots and all required dependency edges. Conditional
recovery instructions count as dependencies (ticketing/review to upstream setup).
Setup's examples of other skills, and its triage branch that only runs when
triage is already installed, are optional mentions, not required edges.
All resources within each selected upstream skill directory are included.

Every file hash is SHA-256 of raw bytes. A skill's content hash is SHA-256 of
the UTF-8 JSON encoding of its relative-path-to-hash map, with keys sorted,
ASCII escaping enabled and separators `,` and `:` (no whitespace or newline).
Git attributes preserve upstream bytes across checkout platforms.

Each entry records classification (`unchanged`, `adapted`, or `new`), origin,
dependencies, local file hashes and aggregate content hash. Upstream entries
also record the source file map and aggregate source hash at a full commit ID.
An adapted entry retains the original source map and adds a modification note;
a new entry has no upstream source map. There are currently no adapted skills.
The core verifier is new and MIT licensed.

To update deliberately, audit dependencies and license changes first, read files
from the chosen Git commit as raw bytes, then regenerate the file maps and
aggregate hashes. The verifier never refreshes hashes or repairs changed files.
Review the resulting diff before accepting a new lock. Reproduction Repository
upgrades require their own preview and user approval.

Offline verification proves agreement with the committed lock, including exact
file inventory and licensing files. `--upstream` additionally proves source
maps and unchanged files against the locked Git objects. The lock itself is a
reviewed trust input, not a cryptographic signature of upstream authorship.
