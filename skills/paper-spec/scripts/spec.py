#!/usr/bin/env python3
"""Prepare and approve a hash-bound paper specification."""

import argparse
import datetime as _datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path


SCHEMA_VERSION = "1.0"
SOURCE_STATE = "evidence_approved"
READY_STATE = "specification_ready"
TARGET_STATE = "specification_approved"

GATE_RELATIVE = ".paper2code/gates/specification-gate.yaml"
STATE_RELATIVE = ".paper2code/state.yaml"
EVIDENCE_GATE_RELATIVE = ".paper2code/gates/evidence-gate.yaml"

EVIDENCE_ARTIFACTS = [
    "dossier/paper.md",
    "dossier/evidence.yaml",
    "dossier/audit.yaml",
    "dossier/ambiguities.yaml",
    "dossier/scope-matrix.yaml",
]
SPEC_ARTIFACTS = [
    "decisions/frontier.yaml",
    "specification/specification.yaml",
    "specification/paper-spec.md",
]
SCHEMA_ARTIFACTS = {
    "scope": "skills/paper2code-core/references/schemas/v1/scope-matrix.schema.json",
    "specification": "skills/paper2code-core/references/schemas/v1/specification.schema.json",
}


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


def contract_hashes(root):
    directory = root / "contracts"
    if not directory.is_dir():
        raise ContractError("Missing contracts directory")
    result = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            relative = path.relative_to(root).as_posix()
            if relative.endswith((".json", ".yaml", ".yml")):
                result[relative] = canonical_hash(path)
            else:
                result[relative] = raw_hash(path)
    return result


def current_artifacts(root):
    artifacts = {
        relative: artifact_hash(root, relative)
        for relative in [*EVIDENCE_ARTIFACTS, *SPEC_ARTIFACTS]
    }
    artifacts.update(contract_hashes(root))
    return artifacts


def schema_hashes(root):
    result = {}
    for name, relative in SCHEMA_ARTIFACTS.items():
        path = root / relative
        if not path.is_file():
            raise ContractError(f"Missing schema artifact: {relative}")
        result[name] = {"path": relative, "sha256": raw_hash(path)}
    return result


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
    state_path = root / STATE_RELATIVE
    if not state_path.is_file():
        raise ContractError(f"Missing {STATE_RELATIVE}")
    state = load_json(state_path)
    if state.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("Unsupported state schema version")
    return state


def verify_evidence_gate(root):
    run_core(root, "validate-evidence-gate", "--root", str(root))
    gate = load_json(root / EVIDENCE_GATE_RELATIVE)
    current = {
        relative: artifact_hash(root, relative) for relative in EVIDENCE_ARTIFACTS
    }
    if current != gate["artifacts"]:
        raise ContractError(
            "stale Evidence Gate: approved dossier artifacts no longer match current hashes"
        )
    return current


def validate_specification_inputs(root):
    run_core(root, "validate-scope-matrix", "--root", str(root))
    run_core(root, "validate-specification", "--root", str(root))


def command_verify_evidence(root):
    return {
        "stage": "paper-spec",
        "valid": True,
        "evidence_gate": EVIDENCE_GATE_RELATIVE,
        "artifacts": verify_evidence_gate(root),
    }


def command_prepare(root):
    state = read_state(root)
    if state.get("state") != SOURCE_STATE:
        raise ContractError(
            f"Specification preparation requires state {SOURCE_STATE}, got {state.get('state')}"
        )
    verify_evidence_gate(root)
    validate_specification_inputs(root)
    run_core(root, "check-transition", str(root / STATE_RELATIVE), "--to", READY_STATE)

    write_json(
        root / STATE_RELATIVE,
        {
            "schema_version": SCHEMA_VERSION,
            "state": READY_STATE,
            "return_target": None,
        },
    )
    return {
        "stage": "paper-spec",
        "state": READY_STATE,
        "artifacts": current_artifacts(root),
        "schemas": schema_hashes(root),
    }


def command_approve(root, approver):
    if not approver:
        raise ContractError("--approver is required for a researcher-approved Specification Gate")
    state = read_state(root)
    if state.get("state") != READY_STATE:
        raise ContractError(
            f"Specification approval requires state {READY_STATE}, got {state.get('state')}"
        )
    verify_evidence_gate(root)
    validate_specification_inputs(root)
    run_core(root, "check-transition", str(root / STATE_RELATIVE), "--to", TARGET_STATE)

    artifacts = current_artifacts(root)
    schemas = schema_hashes(root)
    gate = {
        "schema_version": SCHEMA_VERSION,
        "gate": "specification",
        "transition": f"{READY_STATE} -> {TARGET_STATE}",
        "approved_at": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
        "approved_by": approver,
        "artifacts": artifacts,
        "schemas": schemas,
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
        "stage": "paper-spec",
        "state": TARGET_STATE,
        "gate": GATE_RELATIVE,
        "approved_by": approver,
        "artifacts": artifacts,
        "schemas": schemas,
    }


def command_verify_gate(root):
    run_core(root, "validate-specification-gate", "--root", str(root))
    gate = load_json(root / GATE_RELATIVE)
    verify_evidence_gate(root)
    if current_artifacts(root) != gate["artifacts"]:
        raise ContractError("stale Specification Gate: current artifacts differ from approved hashes")
    if schema_hashes(root) != gate["schemas"]:
        raise ContractError("stale Specification Gate: schema identities differ from approved hashes")
    state = read_state(root)
    if state.get("state") != TARGET_STATE:
        raise ContractError(
            f"Specification Gate approves {TARGET_STATE}, got {state.get('state')}"
        )
    return {
        "stage": "paper-spec",
        "valid": True,
        "gate": GATE_RELATIVE,
        "approved_by": gate["approved_by"],
        "artifacts": gate["artifacts"],
        "schemas": gate["schemas"],
    }


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)

    verify_evidence = commands.add_parser("verify-evidence", help="verify the Evidence Gate is current")
    verify_evidence.set_defaults(handler=lambda args: command_verify_evidence(args.root))

    prepare = commands.add_parser("prepare", help="validate the specification and move to specification_ready")
    prepare.set_defaults(handler=lambda args: command_prepare(args.root))

    approve = commands.add_parser("approve", help="record approval and advance state")
    approve.add_argument("--approver", required=True)
    approve.set_defaults(handler=lambda args: command_approve(args.root, args.approver))

    verify = commands.add_parser("verify-gate", help="verify the approved Specification Gate is current")
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
