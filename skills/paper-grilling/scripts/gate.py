#!/usr/bin/env python3
"""Resolve paper ambiguities and record a hash-bound Evidence Gate."""

import argparse
import datetime as _datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path


SCHEMA_VERSION = "1.0"
SOURCE_STATE = "evidence_extracted"
TARGET_STATE = "evidence_approved"
TRANSITION = f"{SOURCE_STATE} -> {TARGET_STATE}"

GATE_RELATIVE = ".paper2code/gates/evidence-gate.yaml"
STATE_RELATIVE = ".paper2code/state.yaml"

ARTIFACTS = [
    "dossier/paper.md",
    "dossier/evidence.yaml",
    "dossier/audit.yaml",
    "dossier/ambiguities.yaml",
    "dossier/scope-matrix.yaml",
]


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


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_hash(document):
    return hashlib.sha256(canonical_json(load_json(document)).encode("utf-8")).hexdigest()


def raw_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact_hash(root, relative):
    path = root / relative
    if not path.is_file():
        raise ContractError(f"Missing {relative}")
    if relative.endswith(".md"):
        return raw_hash(path)
    return canonical_hash(path)


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


def current_hashes(root):
    return {relative: artifact_hash(root, relative) for relative in ARTIFACTS}


def read_state(root):
    state_path = root / STATE_RELATIVE
    if not state_path.is_file():
        raise ContractError(f"Missing {STATE_RELATIVE}")
    state = load_json(state_path)
    if state.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("Unsupported state schema version")
    return state


def validate_gate(root):
    run_core(root, "validate-dossier", "--root", str(root))
    ambiguities = run_core(root, "validate-ambiguities", "--root", str(root))
    return ambiguities


def command_validate(root):
    state = read_state(root)
    if state.get("state") != SOURCE_STATE:
        raise ContractError(
            f"Evidence Gate requires state {SOURCE_STATE}, got {state.get('state')}"
        )
    ambiguities = validate_gate(root)
    return {
        "stage": "paper-grilling",
        "state": state["state"],
        "hashes": current_hashes(root),
        "ambiguities": ambiguities,
    }


def command_approve(root, approver):
    if not approver:
        raise ContractError("--approver is required for a researcher-approved Evidence Gate")
    state = read_state(root)
    if state.get("state") != SOURCE_STATE:
        raise ContractError(
            f"Evidence Gate requires state {SOURCE_STATE}, got {state.get('state')}"
        )

    run_core(root, "validate-dossier", "--root", str(root))
    ambiguities = run_core(root, "validate-ambiguities", "--root", str(root))
    run_core(root, "check-transition", str(root / STATE_RELATIVE), "--to", TARGET_STATE)

    hashes = current_hashes(root)
    gate = {
        "schema_version": SCHEMA_VERSION,
        "gate": "evidence",
        "transition": TRANSITION,
        "approved_at": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
        "approved_by": approver,
        "artifacts": hashes,
        "must_ambiguities": {
            "total": ambiguities["must_total"],
            "resolved": ambiguities["must_resolved"],
        },
    }
    write_json(root / GATE_RELATIVE, gate)
    write_json(
        root / STATE_RELATIVE,
        {
            "schema_version": SCHEMA_VERSION,
            "state": TARGET_STATE,
            "return_target": None,
        },
    )
    return {
        "stage": "paper-grilling",
        "state": TARGET_STATE,
        "gate": GATE_RELATIVE,
        "approved_by": approver,
        "artifacts": hashes,
        "must_ambiguities": gate["must_ambiguities"],
    }


def command_verify_gate(root):
    run_core(root, "validate-evidence-gate", "--root", str(root))
    gate_path = root / GATE_RELATIVE
    gate = load_json(gate_path)
    current = current_hashes(root)
    if current != gate["artifacts"]:
        raise ContractError(
            "stale Evidence Gate: current artifacts do not match the approved hashes"
        )
    state = read_state(root)
    if state.get("state") != TARGET_STATE:
        raise ContractError(
            f"Evidence Gate approves {TARGET_STATE}, got {state.get('state')}"
        )
    return {
        "stage": "paper-grilling",
        "valid": True,
        "gate": GATE_RELATIVE,
        "approved_by": gate["approved_by"],
        "artifacts": current,
    }


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate current gate inputs")
    validate.set_defaults(handler=lambda args: command_validate(args.root))

    approve = commands.add_parser("approve", help="record approval and advance state")
    approve.add_argument("--approver", required=True)
    approve.set_defaults(
        handler=lambda args: command_approve(args.root, args.approver)
    )

    verify = commands.add_parser("verify-gate", help="verify the approved gate is still current")
    verify.set_defaults(handler=lambda args: command_verify_gate(args.root))
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
