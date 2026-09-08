#!/usr/bin/env python3
"""Route a recorded reproduction failure to its typed workflow loop."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


SCHEMA_VERSION = "1.0"
STATE_RELATIVE = ".paper2code/state.yaml"
EVALUATION_REPORT = "results/evaluation-report.yaml"


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


def canonical_hash(path):
    value = load_json(path)
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def run_core(root, *arguments):
    completed = subprocess.run(
        [sys.executable, str(root / "skills/paper2code-core/scripts/paper2code.py"), *arguments],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ContractError(completed.stderr.strip() or completed.stdout.strip())
    return json.loads(completed.stdout)


def read_state(root):
    state = load_json(root / STATE_RELATIVE)
    if state.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("Unsupported state schema version")
    return state


def source_failure(root, failure_class, identifier, message):
    path = root / EVALUATION_REPORT
    if path.is_file():
        document = load_json(path)
        failure = document.get("failure")
        if failure:
            return EVALUATION_REPORT, failure, path
        if document.get("status") == "failed":
            raise ContractError("Evaluation report is failed but does not classify a failure")
    for candidate in sorted((root / "runs").glob("*/report.yaml")):
        document = load_json(candidate)
        failure = document.get("failure")
        if failure:
            return candidate.relative_to(root).as_posix(), failure, candidate
    if not failure_class:
        raise ContractError("No recorded reproduction failure; pass --failure-class for an external failure")
    return "external", {"class": failure_class, "id": identifier or "external", "message": message or "External failure"}, None


def command_diagnose(root, failure_class=None, identifier=None, message=None):
    root = root.resolve()
    current = read_state(root)
    source, failure, source_path = source_failure(root, failure_class, identifier, message)
    if failure["class"] not in {"software", "scientific", "result", "environment", "evidence"}:
        raise ContractError(f"Unsupported failure class: {failure['class']}")

    routes = {
        "software": "diagnosing",
        "scientific": "diagnosing",
        "environment": "diagnosing",
        "result": "revision_required",
        "evidence": "needs_decision",
    }
    if current["state"] in {"diagnosing", "needs_decision", "revision_required"}:
        state = current["state"]
        return_target = current["return_target"]
    else:
        state = routes[failure["class"]]
        return_target = current["state"]
        run_core(
            root,
            "check-transition",
            str(root / STATE_RELATIVE),
            "--to",
            state,
            "--return-target",
            return_target,
        )
        write_json(
            root / STATE_RELATIVE,
            {"schema_version": SCHEMA_VERSION, "state": state, "return_target": return_target},
        )

    diagnosis = {
        "schema_version": SCHEMA_VERSION,
        "stage": "diagnosis",
        "source_report": source,
        "source_sha256": canonical_hash(source_path) if source_path else "0" * 64,
        "failure": {
            "class": failure["class"],
            "id": failure["id"],
            "message": failure["message"],
        },
        "route": {"state": state, "return_target": return_target},
    }
    write_json(root / "results/diagnosis.yaml", diagnosis)
    return {"stage": "paper-diagnosis", "status": "recorded", **diagnosis}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--failure-class",
        choices=["software", "scientific", "result", "environment", "evidence"],
    )
    parser.add_argument("--id")
    parser.add_argument("--message")
    commands = parser.add_subparsers(dest="command", required=True)
    diagnose = commands.add_parser("diagnose", help="record and route a reproduction failure")
    diagnose.add_argument(
        "--failure-class",
        choices=["software", "scientific", "result", "environment", "evidence"],
        default=argparse.SUPPRESS,
    )
    diagnose.add_argument("--id", default=argparse.SUPPRESS)
    diagnose.add_argument("--message", default=argparse.SUPPRESS)
    diagnose.set_defaults(
        handler=lambda args: command_diagnose(args.root, args.failure_class, args.id, args.message)
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = args.handler(args)
    except (ContractError, OSError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
