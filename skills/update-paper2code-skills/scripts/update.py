#!/usr/bin/env python3
"""Preview and apply a safe Paper-to-Code Skill Closure upgrade."""

import argparse
import datetime as _datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


SCHEMA_VERSION = "1.0"
PREVIEW_RELATIVE = ".paper2code/skill-upgrade-preview.yaml"
RECORD_RELATIVE = ".paper2code/skill-upgrade.yaml"
VERIFY_RELATIVE = "skills/paper2code-core/scripts/verify_closure.py"
REQUIRED_DISTRIBUTION = {"LICENSE", "THIRD_PARTY_NOTICES.md", "licenses/mattpocock-skills-LICENSE", ".gitattributes"}


class ContractError(ValueError):
    pass


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"Cannot read {path}: {exc}") from exc


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def canonical_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def raw_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_relative(relative):
    path = Path(relative)
    if (
        not isinstance(relative, str)
        or not relative
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in relative
    ):
        raise ContractError(f"Unsafe closure path: {relative!r}")
    return relative


def safe_child(root, relative):
    safe_relative(relative)
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ContractError(f"Closure path escapes repository: {relative}")
    return path


def load_lock(root):
    path = root / "skills-lock.yaml"
    lock = load_json(path)
    if lock.get("version") != 1 or not isinstance(lock.get("skills"), dict):
        raise ContractError("Unsupported or malformed skills-lock.yaml")
    if not isinstance(lock.get("distribution_files"), dict):
        raise ContractError("skills-lock.yaml is missing distribution_files")
    if not REQUIRED_DISTRIBUTION <= set(lock["distribution_files"]):
        raise ContractError("skills-lock.yaml is missing required distribution files")
    return lock


def verify_closure(root):
    script = root / VERIFY_RELATIVE
    if not script.is_file():
        raise ContractError(f"Missing closure verifier: {VERIFY_RELATIVE}")
    completed = subprocess.run(
        [sys.executable, str(script), "--root", str(root)],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ContractError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout.strip()


def skill_files(root, name):
    directory = safe_child(root, f"skills/{name}")
    if not directory.is_dir():
        return {}
    result = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            relative = path.relative_to(directory).as_posix()
            result[relative] = raw_hash(path)
    return result


def current_conflicts(root, lock):
    conflicts = []
    for name, entry in lock["skills"].items():
        directory = safe_child(root, f"skills/{name}")
        expected = entry["files"]
        actual = skill_files(root, name)
        for relative, expected_hash in expected.items():
            path = directory / relative
            full = f"skills/{name}/{relative}"
            if not path.is_file():
                conflicts.append({"path": full, "reason": "managed file is missing"})
            elif raw_hash(path) != expected_hash:
                conflicts.append(
                    {
                        "path": full,
                        "reason": "managed file was modified locally",
                        "current_sha256": raw_hash(path),
                        "expected_sha256": expected_hash,
                    }
                )
        for relative in sorted(set(actual) - set(expected)):
            conflicts.append(
                {"path": f"skills/{name}/{relative}", "reason": "untracked closure file"}
            )

    skills_root = root / "skills"
    if skills_root.is_dir():
        for directory in sorted(skills_root.iterdir()):
            if directory.is_dir() and directory.name not in lock["skills"]:
                conflicts.append(
                    {"path": f"skills/{directory.name}", "reason": "untracked skill directory"}
                )

    for relative, expected_hash in lock["distribution_files"].items():
        path = safe_child(root, relative)
        if not path.is_file():
            conflicts.append({"path": relative, "reason": "managed distribution file is missing"})
        elif raw_hash(path) != expected_hash:
            conflicts.append(
                {
                    "path": relative,
                    "reason": "managed distribution file was modified locally",
                    "current_sha256": raw_hash(path),
                    "expected_sha256": expected_hash,
                }
            )
    return conflicts


def file_changes(current, candidate):
    current_files = current.get("files", {})
    candidate_files = candidate.get("files", {})
    return {
        "added": sorted(set(candidate_files) - set(current_files)),
        "removed": sorted(set(current_files) - set(candidate_files)),
        "modified": sorted(
            relative
            for relative in set(current_files) & set(candidate_files)
            if current_files[relative] != candidate_files[relative]
        ),
    }


PROVENANCE_FIELDS = (
    "classification",
    "origin",
    "license",
    "dependencies",
    "source_files",
    "source_hash",
    "modifications",
)


def build_plan(root, candidate_root):
    root = root.resolve()
    candidate_root = candidate_root.resolve()
    if root == candidate_root:
        raise ContractError("Candidate bundle must be different from the target repository")
    current_lock = load_lock(root)
    verify_closure(candidate_root)
    candidate_lock = load_lock(candidate_root)

    current_names = set(current_lock["skills"])
    candidate_names = set(candidate_lock["skills"])
    additions = sorted(candidate_names - current_names)
    removals = sorted(current_names - candidate_names)
    changes = []
    provenance_changes = []
    for name in sorted(current_names & candidate_names):
        current = current_lock["skills"][name]
        candidate = candidate_lock["skills"][name]
        files = file_changes(current, candidate)
        if files["added"] or files["removed"] or files["modified"] or current.get("content_hash") != candidate.get("content_hash"):
            changes.append({"skill": name, **files})
        changed_fields = [
            field for field in PROVENANCE_FIELDS if current.get(field) != candidate.get(field)
        ]
        if changed_fields:
            provenance_changes.append(
                {
                    "skill": name,
                    "fields": changed_fields,
                    "before": {field: current.get(field) for field in changed_fields},
                    "after": {field: candidate.get(field) for field in changed_fields},
                }
            )

    current_distribution = current_lock["distribution_files"]
    candidate_distribution = candidate_lock["distribution_files"]
    distribution_changes = {
        "added": sorted(set(candidate_distribution) - set(current_distribution)),
        "removed": sorted(set(current_distribution) - set(candidate_distribution)),
        "modified": sorted(
            relative
            for relative in set(current_distribution) & set(candidate_distribution)
            if current_distribution[relative] != candidate_distribution[relative]
        ),
    }
    conflicts = current_conflicts(root, current_lock)
    plan = {
        "current_lock_sha256": raw_hash(root / "skills-lock.yaml"),
        "candidate_lock_sha256": raw_hash(candidate_root / "skills-lock.yaml"),
        "additions": additions,
        "changes": changes,
        "removals": removals,
        "provenance_changes": provenance_changes,
        "distribution_changes": distribution_changes,
        "local_conflicts": conflicts,
    }
    return plan, current_lock, candidate_lock


def command_preview(root, candidate_root):
    root = root.resolve()
    candidate_root = candidate_root.resolve()
    plan, _current_lock, _candidate_lock = build_plan(root, candidate_root)
    result = {
        "schema_version": SCHEMA_VERSION,
        "stage": "skill_upgrade",
        "status": "preview",
        "approval_required": True,
        "candidate_root": str(candidate_root),
        **plan,
    }
    result["plan_sha256"] = canonical_hash(plan)
    write_json(root / PREVIEW_RELATIVE, result)
    return result


def validate_preview(root, plan):
    preview_path = root / PREVIEW_RELATIVE
    if not preview_path.is_file():
        raise ContractError(f"Run preview first: {PREVIEW_RELATIVE}")
    preview = load_json(preview_path)
    if preview.get("status") != "preview":
        raise ContractError("Skill upgrade preview is not a preview record")
    if preview.get("plan_sha256") != canonical_hash(plan):
        raise ContractError("Skill upgrade preview is stale; run preview again")
    if plan["local_conflicts"]:
        raise ContractError("Skill upgrade has local conflicts; resolve them before approval")
    return preview


def remove_exact(path, root):
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()) or resolved == root.resolve():
        raise ContractError(f"Refusing to remove path outside the target repository: {path}")
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def apply_closure(root, candidate_root, current_lock, candidate_lock):
    root = root.resolve()
    candidate_root = candidate_root.resolve()
    current_names = set(current_lock["skills"])
    candidate_names = set(candidate_lock["skills"])
    for name in sorted(current_names - candidate_names):
        remove_exact(root / "skills" / name, root / "skills")
    for name in sorted(candidate_names):
        destination = root / "skills" / name
        if destination.exists():
            remove_exact(destination, root / "skills")
        shutil.copytree(
            candidate_root / "skills" / name,
            destination,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

    current_distribution = set(current_lock["distribution_files"])
    candidate_distribution = set(candidate_lock["distribution_files"])
    for relative in sorted(current_distribution - candidate_distribution):
        remove_exact(safe_child(root, relative), root)
    for relative in sorted(candidate_distribution):
        source = safe_child(candidate_root, relative)
        destination = safe_child(root, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    shutil.copy2(candidate_root / "skills-lock.yaml", root / "skills-lock.yaml")


def command_approve(root, candidate_root, approver):
    if not approver:
        raise ContractError("--approver is required for an approved Skill Closure upgrade")
    root = root.resolve()
    candidate_root = candidate_root.resolve()
    plan, current_lock, candidate_lock = build_plan(root, candidate_root)
    preview = validate_preview(root, plan)
    apply_closure(root, candidate_root, current_lock, candidate_lock)
    verify_closure(root)
    record = {
        "schema_version": SCHEMA_VERSION,
        "stage": "skill_upgrade",
        "status": "applied",
        "approved_at": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
        "approved_by": approver,
        "preview_plan_sha256": preview["plan_sha256"],
        "candidate_lock_sha256": plan["candidate_lock_sha256"],
        "changed_paths": sorted(
            {
                *[f"skills/{name}" for name in set(plan["additions"]) | set(plan["removals"])],
                *[f"skills/{item['skill']}" for item in plan["changes"]],
                *plan["distribution_changes"]["added"],
                *plan["distribution_changes"]["modified"],
                *plan["distribution_changes"]["removed"],
                "skills-lock.yaml",
            }
        ),
    }
    write_json(root / RECORD_RELATIVE, record)
    return {**record, "candidate_root": str(candidate_root)}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    preview = commands.add_parser("preview", help="write a Skill Closure upgrade preview")
    preview.set_defaults(handler=lambda args: command_preview(args.root, args.candidate_root))
    approve = commands.add_parser("approve", help="apply an approved Skill Closure upgrade")
    approve.add_argument("--approver", required=True)
    approve.set_defaults(
        handler=lambda args: command_approve(args.root, args.candidate_root, args.approver)
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = args.handler(args)
    except (ContractError, OSError, shutil.Error, subprocess.CalledProcessError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
