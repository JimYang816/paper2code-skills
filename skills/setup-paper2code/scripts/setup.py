#!/usr/bin/env python3
"""Plan or apply an idempotent Paper-to-Code repository scaffold."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]


RECORD_DIRECTORIES = [
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
RECORD_SCHEMAS = {
    "dossier/evidence.yaml": "evidence",
    "dossier/ambiguities.yaml": "ambiguities",
    "dossier/scope-matrix.yaml": "scope-matrix",
    ".paper2code/state.yaml": "state",
}


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True)


def directory_hash(folder: Path) -> str:
    digest = hashlib.sha256()
    files = (
        item
        for item in folder.rglob("*")
        if item.is_file() and "__pycache__" not in item.parts and item.suffix != ".pyc"
    )
    for path in sorted(files):
        digest.update(path.relative_to(folder).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def gh_base_command() -> list[str]:
    executable = os.environ.get("PAPER2CODE_GH", "gh")
    if os.name == "nt" and executable.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", executable]
    return [executable]


def run_gh(arguments: list[str], target: Path) -> subprocess.CompletedProcess[str]:
    return run([*gh_base_command(), *arguments], target)


def github_ready(target: Path) -> bool:
    remote = run(["git", "remote", "get-url", "origin"], target)
    if remote.returncode != 0 or "github.com" not in remote.stdout.lower():
        return False
    try:
        return run_gh(["auth", "status"], target).returncode == 0
    except OSError:
        return False


def load_bundle(bundle_root: Path) -> dict[str, Any]:
    return yaml.safe_load((bundle_root / "skills-lock.yaml").read_text(encoding="utf-8"))


def selected_skills(lock: dict[str, Any], profiles: list[str]) -> set[str]:
    bundle = lock.get("bundle")
    if not isinstance(bundle, dict):
        raise RuntimeError("Bundle lock does not declare core/profile roots")
    configured_profiles = bundle["profiles"]
    unknown = sorted(set(profiles) - set(configured_profiles))
    if unknown:
        raise RuntimeError("Unknown Domain Profiles: " + ", ".join(unknown))
    roots = list(bundle["core_roots"])
    for profile in profiles:
        roots.extend(configured_profiles[profile])
    records = lock["skills"]
    closure: set[str] = set()

    def visit(name: str) -> None:
        if name in closure:
            return
        if name not in records:
            raise RuntimeError(f"Skill lock is missing {name}")
        closure.add(name)
        for dependency in records[name]["dependencies"]:
            visit(dependency)

    for root in roots:
        visit(root)
    return closure


def selected_lock(lock: dict[str, Any], names: set[str], profiles: list[str]) -> dict[str, Any]:
    bundle = lock["bundle"]
    return {
        "schema_version": lock["schema_version"],
        "bundle": {
            "core_roots": bundle["core_roots"],
            "profiles": {name: bundle["profiles"][name] for name in profiles},
        },
        "skills": {name: lock["skills"][name] for name in sorted(names)},
    }


def lock_bytes(lock: dict[str, Any]) -> bytes:
    return yaml.safe_dump(lock, sort_keys=False).encode("utf-8")


def file_action(path: Path) -> str:
    return "preserve" if path.exists() else "create"


def record_valid(path: Path, schema_name: str, bundle_root: Path) -> bool:
    if not path.is_file():
        return False
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        schema_path = (
            bundle_root
            / "skills"
            / "paper2code-core"
            / "references"
            / "schemas"
            / "v1"
            / f"{schema_name}.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        return not list(Draft202012Validator(schema).iter_errors(value))
    except (OSError, json.JSONDecodeError, yaml.YAMLError):
        return False


def record_action(path: Path, relative: str, bundle_root: Path) -> str:
    if not path.exists():
        return "create"
    schema = RECORD_SCHEMAS.get(relative)
    return "preserve" if not schema or record_valid(path, schema, bundle_root) else "conflict"


def plan(
    target: Path, bundle_root: Path, provision_labels: bool, profiles: list[str]
) -> dict[str, Any]:
    lock = load_bundle(bundle_root)
    names = selected_skills(lock, profiles)
    generated_lock = lock_bytes(selected_lock(lock, names, profiles))
    operations: list[dict[str, str]] = [
        {"path": ".git", "action": file_action(target / ".git")},
    ]
    operations.extend(
        {"path": relative, "action": file_action(target / relative)}
        for relative in RECORD_DIRECTORIES
    )
    template_root = bundle_root / "skills" / "paper2code-core" / "assets" / "reproduction"
    for source in sorted(item for item in template_root.rglob("*") if item.is_file()):
        relative = source.relative_to(template_root).as_posix()
        operations.append(
            {"path": relative, "action": record_action(target / relative, relative, bundle_root)}
        )
    for name in sorted(names):
        source = bundle_root / "skills" / name
        expected = lock["skills"][name]["content_hash"]
        if directory_hash(source) != expected:
            raise RuntimeError(f"Canonical skill content hash mismatch: {name}")
        destination = target / "skills" / name
        action = "create" if not destination.exists() else (
            "preserve" if directory_hash(destination) == expected else "conflict"
        )
        operations.append({"path": f"skills/{name}", "action": action})
    target_lock = target / "skills-lock.yaml"
    lock_action = "create" if not target_lock.exists() else (
        "preserve" if target_lock.read_bytes() == generated_lock else "conflict"
    )
    operations.append({"path": "skills-lock.yaml", "action": lock_action})
    ignore_path = target / ".gitignore"
    if not ignore_path.exists():
        ignore_action = "create"
    elif "# Paper-to-Code large or restricted artifacts" in ignore_path.read_text(encoding="utf-8"):
        ignore_action = "preserve"
    else:
        ignore_action = "update"
    operations.extend(
        [
            {"path": ".gitignore", "action": ignore_action},
            {
                "path": ".paper2code/state.yaml",
                "action": record_action(
                    target / ".paper2code/state.yaml", ".paper2code/state.yaml", bundle_root
                ),
            },
        ]
    )
    return {
        "mode": "plan",
        "target": str(target),
        "profiles": profiles,
        "skills": sorted(names),
        "operations": operations,
        "preserve_existing": True,
        "external_writes": ["create or update nine GitHub labels"] if provision_labels else [],
    }


def apply(
    target: Path, bundle_root: Path, provision_labels: bool, profiles: list[str]
) -> dict[str, Any]:
    preview = plan(target, bundle_root, provision_labels, profiles)
    target.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    conflicts = [
        item["path"] for item in preview["operations"] if item["action"] == "conflict"
    ]

    if not (target / ".git").is_dir():
        completed = run(["git", "init"], target)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr or "git init failed")
        created.append(".git")

    for relative in RECORD_DIRECTORIES:
        path = target / relative
        if not path.exists():
            path.mkdir(parents=True)
            created.append(relative)

    template_root = bundle_root / "skills" / "paper2code-core" / "assets" / "reproduction"
    for source in sorted(item for item in template_root.rglob("*") if item.is_file()):
        template_relative = source.relative_to(template_root)
        destination = target / template_relative
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            created.append(template_relative.as_posix())

    lock = load_bundle(bundle_root)
    names = selected_skills(lock, profiles)
    generated_lock = lock_bytes(selected_lock(lock, names, profiles))
    target_skills = target / "skills"
    target_skills.mkdir(exist_ok=True)
    for name in sorted(names):
        source = bundle_root / "skills" / name
        destination = target_skills / name
        if not destination.exists():
            shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            created.append(f"skills/{name}")

    target_lock = target / "skills-lock.yaml"
    if not target_lock.exists():
        target_lock.write_bytes(generated_lock)
        created.append("skills-lock.yaml")

    ignore_path = target / ".gitignore"
    old_ignore = ignore_path.read_text(encoding="utf-8") if ignore_path.exists() else ""
    if "# Paper-to-Code large or restricted artifacts" not in old_ignore:
        separator = "" if not old_ignore or old_ignore.endswith("\n") else "\n"
        ignore_path.write_text(old_ignore + separator + IGNORE_BLOCK, encoding="utf-8")
        created.append(".gitignore:block")

    state_path = target / ".paper2code" / "state.yaml"
    existing = yaml.safe_load(state_path.read_text(encoding="utf-8")) if state_path.exists() else None
    if existing is None:
        state_path.write_text(
            yaml.safe_dump(
                {"schema_version": "1.0", "state": "setup_pending", "return_target": None},
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        created.append(".paper2code/state.yaml")
        existing = {"state": "setup_pending", "return_target": None}

    github_access = github_ready(target)

    labels_provisioned = 0
    if provision_labels:
        if not github_access or conflicts:
            raise RuntimeError("GitHub labels require an existing GitHub origin and usable gh access")
        for name, (description, color) in LABELS.items():
            completed = run_gh(
                ["label", "create", name, "--description", description, "--color", color, "--force"],
                target,
            )
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr or f"Failed to provision GitHub label {name}")
            labels_provisioned += 1

    scaffold_valid = not conflicts and all(
        directory_hash(target_skills / name) == lock["skills"][name]["content_hash"]
        for name in names
    ) and target_lock.read_bytes() == generated_lock and all(
        record_valid(target / relative, schema, bundle_root)
        for relative, schema in RECORD_SCHEMAS.items()
    )
    was_ready = existing.get("state") == "ready_for_extraction"
    ready = scaffold_valid and github_access and (labels_provisioned == len(LABELS) or was_ready)
    if existing.get("state") not in {"setup_pending", "ready_for_extraction"}:
        state_name = existing["state"]
        return_target = existing.get("return_target")
    else:
        state_name = "ready_for_extraction" if ready else "setup_pending"
        return_target = None
        state_path.write_text(
            yaml.safe_dump(
                {"schema_version": "1.0", "state": state_name, "return_target": return_target},
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    return {
        "mode": "apply",
        "target": str(target),
        "state": state_name,
        "created": created,
        "conflicts": conflicts,
        "github_ready": github_access,
        "scaffold_valid": scaffold_valid,
        "labels_provisioned": labels_provisioned,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--provision-labels", action="store_true")
    parser.add_argument("--profile", action="append", default=[])
    args = parser.parse_args()
    try:
        result = (
            apply(args.target, args.bundle_root, args.provision_labels, args.profile)
            if args.apply
            else plan(args.target, args.bundle_root, args.provision_labels, args.profile)
        )
    except (OSError, RuntimeError, yaml.YAMLError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
