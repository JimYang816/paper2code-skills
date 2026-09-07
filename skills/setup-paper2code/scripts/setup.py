#!/usr/bin/env python3
"""Plan or apply an idempotent, standard-library Paper-to-Code scaffold."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from capabilities import gh_executable, git_executable, run_gh


SCHEMA_VERSION = "1.0"
NORMAL_STATES = [
    "setup_pending",
    "ready_for_extraction",
    "evidence_extracted",
    "evidence_approved",
    "specification_ready",
    "specification_approved",
    "implementation_active",
    "cpu_validated",
    "full_run_approved",
    "full_run_complete",
    "evaluated",
]
EXCEPTION_STATES = {"needs_decision", "diagnosing", "revision_required"}

EMPTY_DIRECTORIES = [
    ".paper2code/gates",
    ".paper2code/capability-reports",
    "paper",
    "dossier/figures",
    "decisions",
    "specification",
    "contracts/baselines",
    "contracts/datasets",
    "validation/references",
    "validation/reports",
    "runs",
    "results",
    "prototypes",
]

INITIAL_RECORDS = {
    "dossier/evidence.yaml": {"schema_version": SCHEMA_VERSION, "items": []},
    "dossier/ambiguities.yaml": {"schema_version": SCHEMA_VERSION, "ambiguities": []},
    "dossier/scope-matrix.yaml": {"schema_version": SCHEMA_VERSION, "claims": []},
}
INITIAL_RECORD_KEYS = {
    "dossier/evidence.yaml": "items",
    "dossier/ambiguities.yaml": "ambiguities",
    "dossier/scope-matrix.yaml": "claims",
}

IGNORE_BLOCK = """# Paper-to-Code large or restricted artifacts
paper/*.pdf
data/
checkpoints/
runs/**/checkpoints/
*.ckpt
*.pt
*.pth
"""

LABELS = {
    "paper2code:evidence": ("Evidence extraction or audit", "1D76DB"),
    "paper2code:decision": ("Researcher decision", "D4C5F9"),
    "paper2code:implementation": ("Implementation work", "0E8A16"),
    "paper2code:validation": ("Software or scientific validation", "FBCA04"),
    "paper2code:experiment": ("Approved experiment", "5319E7"),
    "paper2code:defect": ("Reproduction defect", "D73A4A"),
    "ready-for-agent": ("Fully specified and ready for an agent", "0E8A16"),
    "ready-for-human": ("Requires researcher action", "B60205"),
    "needs-info": ("Waiting for information", "D876E3"),
}


class ContractError(ValueError):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def raw_hash(path):
    return sha256(path.read_bytes())


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def inventory(directory):
    result = {}
    for path in sorted(directory.rglob("*")):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = raw_hash(path)
    return result


def content_hash(files):
    return sha256(canonical_json(files).encode("utf-8"))


def run(command, cwd):
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True)


def valid_state(value):
    if not isinstance(value, dict):
        return False
    if set(value) != {"schema_version", "state", "return_target"}:
        return False
    if value.get("schema_version") != SCHEMA_VERSION:
        return False
    if value.get("state") not in NORMAL_STATES + sorted(EXCEPTION_STATES):
        return False
    return_target = value.get("return_target")
    if value["state"] in EXCEPTION_STATES:
        return return_target in NORMAL_STATES
    return return_target is None


def valid_initial_record(relative, value):
    expected = INITIAL_RECORDS[relative]
    return isinstance(value, dict) and value.get("schema_version") == SCHEMA_VERSION and (
        isinstance(value.get(INITIAL_RECORD_KEYS[relative]), list)
    )


def record_action(path, relative, expected):
    if not path.exists():
        return "create"
    try:
        value = load_json(path)
    except (OSError, json.JSONDecodeError):
        return "conflict"
    if relative == ".paper2code/state.yaml":
        return "preserve" if valid_state(value) else "conflict"
    if relative in INITIAL_RECORDS:
        return "preserve" if valid_initial_record(relative, value) else "conflict"
    return "preserve" if value == expected else "conflict"


def github_origin(target):
    if not git_executable():
        return False
    try:
        completed = run(["git", "remote", "get-url", "origin"], target)
    except OSError:
        return False
    return completed.returncode == 0 and "github.com" in completed.stdout.lower()


def github_access(target):
    if not github_origin(target) or not gh_executable():
        return False
    try:
        return run_gh(target, "auth", "status").returncode == 0
    except (OSError, FileNotFoundError):
        return False


def verify_bundle(bundle_root):
    verifier = bundle_root / "skills/paper2code-core/scripts/verify_closure.py"
    completed = run([sys.executable, str(verifier), "--root", str(bundle_root)], bundle_root)
    if completed.returncode != 0:
        raise ContractError(completed.stderr.strip() or completed.stdout.strip())


def load_bundle(bundle_root):
    lock_path = bundle_root / "skills-lock.yaml"
    try:
        return load_json(lock_path)
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"Cannot read bundle lock: {exc}") from exc


def file_action(path):
    if not path.exists():
        return "create"
    return "preserve"


def plan(target, bundle_root, provision_labels):
    verify_bundle(bundle_root)
    lock = load_bundle(bundle_root)
    skills = lock["skills"]
    operations = []

    def add(path, action):
        operations.append({"path": path, "action": action})

    add(".git", file_action(target / ".git"))
    for relative in EMPTY_DIRECTORIES:
        add(relative, file_action(target / relative))

    for relative, expected in sorted(INITIAL_RECORDS.items()):
        add(relative, record_action(target / relative, relative, expected))

    for name in sorted(skills):
        destination = target / "skills" / name
        if not destination.exists():
            action = "create"
        else:
            actual = content_hash(inventory(destination))
            action = "preserve" if actual == skills[name]["content_hash"] else "conflict"
        add(f"skills/{name}", action)

    for relative in sorted(lock["distribution_files"]):
        destination = target / relative
        if not destination.exists():
            action = "create"
        else:
            action = (
                "preserve"
                if raw_hash(destination) == lock["distribution_files"][relative]
                else "conflict"
            )
        add(relative, action)

    target_lock = target / "skills-lock.yaml"
    bundle_lock = bundle_root / "skills-lock.yaml"
    if not target_lock.exists():
        lock_action = "create"
    else:
        lock_action = "preserve" if raw_hash(target_lock) == raw_hash(bundle_lock) else "conflict"
    add("skills-lock.yaml", lock_action)

    ignore = target / ".gitignore"
    if not ignore.exists():
        ignore_action = "create"
    elif "# Paper-to-Code large or restricted artifacts" in ignore.read_text(encoding="utf-8"):
        ignore_action = "preserve"
    else:
        ignore_action = "update"
    add(".gitignore", ignore_action)

    state_path = target / ".paper2code/state.yaml"
    state_action = record_action(state_path, ".paper2code/state.yaml", None)
    add(".paper2code/state.yaml", state_action)

    return {
        "mode": "plan",
        "target": str(target),
        "operations": operations,
        "preserve_existing": True,
        "external_writes": ["create or update nine GitHub labels"] if provision_labels else [],
    }


def create_initial_directories(target):
    created = []
    for relative in EMPTY_DIRECTORIES:
        path = target / relative
        if not path.exists():
            path.mkdir(parents=True)
            created.append(relative)
        keep = path / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")
    return created


def copy_missing_files(target, bundle_root, preview):
    lock = load_bundle(bundle_root)
    created = []
    actions = {item["path"]: item["action"] for item in preview["operations"]}

    for relative in sorted(INITIAL_RECORDS):
        if actions.get(relative) == "create":
            write_json(target / relative, INITIAL_RECORDS[relative])
            created.append(relative)

    for name in sorted(lock["skills"]):
        if actions.get(f"skills/{name}") == "create":
            source = bundle_root / "skills" / name
            shutil.copytree(
                source,
                target / "skills" / name,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            created.append(f"skills/{name}")

    for relative in sorted(lock["distribution_files"]):
        if actions.get(relative) == "create":
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundle_root / relative, destination)
            created.append(relative)

    if actions.get("skills-lock.yaml") == "create":
        shutil.copy2(bundle_root / "skills-lock.yaml", target / "skills-lock.yaml")
        created.append("skills-lock.yaml")

    return created


def write_ignore_block(target, preview):
    actions = {item["path"]: item["action"] for item in preview["operations"]}
    if actions.get(".gitignore") == "update":
        path = target / ".gitignore"
        old = path.read_text(encoding="utf-8")
        separator = "" if not old or old.endswith("\n") else "\n"
        path.write_text(old + separator + IGNORE_BLOCK, encoding="utf-8")
        return [".gitignore:block"]
    if actions.get(".gitignore") == "create":
        (target / ".gitignore").write_text(IGNORE_BLOCK, encoding="utf-8")
        return [".gitignore"]
    return []


def write_state(target, state_name, return_target=None):
    path = target / ".paper2code/state.yaml"
    write_json(
        path,
        {
            "schema_version": SCHEMA_VERSION,
            "state": state_name,
            "return_target": return_target,
        },
    )


def capability_report(target):
    report_path = target / ".paper2code/capability-reports/setup.yaml"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    checker = Path(__file__).with_name("check_capabilities.py")
    completed = run(
        [sys.executable, str(checker), "--output", str(report_path), "--root", str(target)],
        target,
    )
    if completed.returncode not in (0, 3):
        raise ContractError(completed.stderr.strip() or completed.stdout.strip())
    return report_path


def scaffold_valid(target, bundle_root, preview):
    if any(item["action"] == "conflict" for item in preview["operations"]):
        return False
    try:
        lock = load_bundle(target)
    except ContractError:
        return False
    actions = {item["path"]: item["action"] for item in preview["operations"]}

    for name in sorted(lock["skills"]):
        if actions.get(f"skills/{name}") == "create":
            destination = target / "skills" / name
            actual = content_hash(inventory(destination))
            if actual != lock["skills"][name]["content_hash"]:
                return False

    if actions.get("skills-lock.yaml") == "create":
        bundle_lock = bundle_root / "skills-lock.yaml"
        if raw_hash(target / "skills-lock.yaml") != raw_hash(bundle_lock):
            return False

    for relative, expected in INITIAL_RECORDS.items():
        try:
            value = load_json(target / relative)
        except (OSError, json.JSONDecodeError):
            return False
        if not valid_initial_record(relative, value):
            return False

    try:
        state = load_json(target / ".paper2code/state.yaml")
    except (OSError, json.JSONDecodeError):
        return False
    return valid_state(state)


def provision_github_labels(target):
    count = 0
    for name, (description, color) in sorted(LABELS.items()):
        completed = run_gh(
            target,
            "label",
            "create",
            name,
            "--description",
            description,
            "--color",
            color,
            "--force",
        )
        if completed.returncode != 0:
            raise ContractError(completed.stderr.strip() or f"Failed to create label {name}")
        count += 1
    return count


def apply(target, bundle_root, provision_labels):
    preview = plan(target, bundle_root, provision_labels)
    target.mkdir(parents=True, exist_ok=True)
    created = []
    conflicts = [item["path"] for item in preview["operations"] if item["action"] == "conflict"]

    if not (target / ".git").is_dir():
        completed = run(["git", "init"], target)
        if completed.returncode != 0:
            raise ContractError(completed.stderr.strip() or "git init failed")
        created.append(".git")

    created.extend(create_initial_directories(target))
    created.extend(copy_missing_files(target, bundle_root, preview))
    created.extend(write_ignore_block(target, preview))

    state_path = target / ".paper2code/state.yaml"
    if not state_path.exists():
        write_state(target, "setup_pending")

    report_path = capability_report(target)
    github_ready = github_access(target)
    labels_provisioned = 0

    if provision_labels:
        if not github_ready:
            raise ContractError("GitHub labels require an existing GitHub origin and usable gh access")
        if conflicts:
            raise ContractError("Refusing external GitHub writes while managed files conflict")
        labels_provisioned = provision_github_labels(target)

    actions = {item["path"]: item["action"] for item in preview["operations"]}
    valid = scaffold_valid(target, bundle_root, preview)
    state_action = actions.get(".paper2code/state.yaml", "conflict")
    existing = None
    if state_path.exists() and state_action != "conflict":
        try:
            existing = load_json(state_path)
        except (OSError, json.JSONDecodeError):
            existing = None

    current_state = existing.get("state") if existing and valid_state(existing) else None
    labels_satisfied = labels_provisioned == len(LABELS) or current_state == "ready_for_extraction"
    ready = valid and github_ready and labels_satisfied

    if state_action == "conflict":
        state_name = existing.get("state") if current_state else "unknown"
    elif current_state is None:
        state_name = "ready_for_extraction" if ready else "setup_pending"
        write_state(target, state_name)
    elif current_state == "setup_pending" and ready:
        state_name = "ready_for_extraction"
        write_state(target, state_name)
    elif current_state == "ready_for_extraction" and not ready:
        state_name = "setup_pending"
        write_state(target, state_name)
    else:
        state_name = current_state

    return {
        "mode": "apply",
        "target": str(target),
        "state": state_name,
        "created": created,
        "conflicts": conflicts,
        "github_ready": github_ready,
        "scaffold_valid": valid,
        "labels_provisioned": labels_provisioned,
        "capability_report": str(report_path),
        "external_writes": ["create or update nine GitHub labels"] if provision_labels else [],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--provision-labels", action="store_true")
    args = parser.parse_args()
    try:
        result = (
            apply(args.target, args.bundle_root, args.provision_labels)
            if args.apply
            else plan(args.target, args.bundle_root, args.provision_labels)
        )
    except (ContractError, OSError, shutil.Error) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
