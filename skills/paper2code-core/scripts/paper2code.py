#!/usr/bin/env python3
"""Deterministic mechanics for Paper-to-Code repositories.

This command validates records and mechanical invariants. Scientific judgement
remains in the stage skills and with the researcher.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
    from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
except ImportError as exc:  # pragma: no cover - exercised by capability checks
    print(
        "Missing toolkit capability. Install the pinned Python requirements from "
        "skills/paper2code-core/references/requirements.txt.",
        file=sys.stderr,
    )
    raise SystemExit(3) from exc


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "references" / "schemas" / "v1"
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
NEXT_SKILL = {
    "setup_pending": "setup-paper2code",
    "ready_for_extraction": "extract-paper",
    "evidence_extracted": "grill-paper",
    "evidence_approved": "specify-paper",
    "specification_ready": "specify-paper",
    "specification_approved": "to-tickets, then implement",
    "implementation_active": "cpu-validate",
    "cpu_validated": "prepare-full-run",
    "full_run_approved": "execute-full-run",
    "full_run_complete": "evaluate-reproduction",
    "evaluated": None,
    "needs_decision": "grill-paper or paper-wayfinder",
    "diagnosing": "diagnose-reproduction",
    "revision_required": "diagnose-reproduction",
}


class ContractError(ValueError):
    pass


def load_record(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            if path.suffix.lower() == ".json":
                return json.load(handle)
            return yaml.safe_load(handle)
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ContractError(f"Cannot read {path}: {exc}") from exc


def canonical_bytes(path: Path) -> bytes:
    if path.suffix.lower() in {".yaml", ".yml", ".json"}:
        value = load_record(path)
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ContractError(f"Cannot read {path}: {exc}") from exc


def content_hash(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def validate_record(value: Any, schema_name: str) -> None:
    schema_path = SCHEMA_DIR / f"{schema_name}.schema.json"
    if not schema_path.exists():
        raise ContractError(f"Unknown schema: {schema_name}")
    schema = load_record(schema_path)
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        rendered = []
        for error in errors:
            location = ".".join(map(str, error.path)) or "$"
            rendered.append(f"{location}: {error.message}")
        raise ContractError("; ".join(rendered))


def command_validate(args: argparse.Namespace) -> dict[str, Any]:
    value = load_record(args.document)
    validate_record(value, args.schema)
    return {"valid": True, "schema": args.schema, "document": str(args.document)}


def command_canonical_hash(args: argparse.Namespace) -> dict[str, str]:
    return {"path": str(args.document), "sha256": content_hash(args.document)}


def transition_allowed(current: str, target: str, return_target: str | None) -> bool:
    if target in EXCEPTION_STATES:
        return current in NORMAL_STATES and return_target == current
    if current in EXCEPTION_STATES:
        return bool(return_target) and target == return_target
    try:
        return NORMAL_STATES.index(target) == NORMAL_STATES.index(current) + 1
    except ValueError:
        return False


def command_check_transition(args: argparse.Namespace) -> dict[str, Any]:
    state = load_record(args.state_file)
    validate_record(state, "state")
    current = state["state"]
    return_target = args.return_target or state.get("return_target")
    if not transition_allowed(current, args.target, return_target):
        raise ContractError(
            f"Illegal workflow transition: {current} -> {args.target}"
            + (f" (return target {return_target})" if return_target else "")
        )
    return {"legal": True, "from": current, "to": args.target, "return_target": return_target}


def command_route(args: argparse.Namespace) -> dict[str, Any]:
    state = load_record(args.state_file)
    validate_record(state, "state")
    current = state["state"]
    return {
        "state": current,
        "return_target": state.get("return_target"),
        "next_skill": NEXT_SKILL[current],
    }


def safe_child(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    root = root.resolve()
    if candidate != root and root not in candidate.parents:
        raise ContractError(f"Path escapes record root: {relative}")
    return candidate


def command_verify_gate(args: argparse.Namespace) -> dict[str, Any]:
    gate = load_record(args.gate)
    validate_record(gate, "gate-record")
    stale = []
    missing = []
    for relative, expected in gate["artifact_hashes"].items():
        artifact = safe_child(args.root, relative)
        if not artifact.is_file():
            missing.append(relative)
        elif content_hash(artifact) != expected:
            stale.append(relative)
    if missing or stale:
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if stale:
            details.append("stale: " + ", ".join(stale))
        raise ContractError("Gate Record is not current (" + "; ".join(details) + ")")
    return {"valid": True, "gate": str(args.gate), "artifacts": len(gate["artifact_hashes"])}


def command_verify_manifest(args: argparse.Namespace) -> dict[str, Any]:
    manifest = load_record(args.manifest)
    validate_record(manifest, "dataset-manifest")
    checked = 0
    for item in manifest["expected_files"]:
        path = safe_child(args.root, item["path"])
        if not path.is_file():
            if manifest["availability"] in {"available", "fixture"}:
                raise ContractError(f"Expected dataset file is missing: {item['path']}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != item["sha256"]:
            raise ContractError(f"Dataset hash mismatch: {item['path']}")
        checked += 1
    return {"valid": True, "manifest": str(args.manifest), "files_checked": checked}


def command_verify_run_bundle(args: argparse.Namespace) -> dict[str, Any]:
    bundle = load_record(args.bundle)
    validate_record(bundle, "run-bundle")
    if bundle["learned_method"] and len(set(bundle["seeds"])) < 3:
        if not bundle["budget_approved_single_run"] or len(bundle["seeds"]) != 1:
            raise ContractError(
                "Learned Full Runs require at least three independent seeds, or one explicitly "
                "budget-approved seed."
            )
    if bundle["code_dirty"]:
        raise ContractError("Run Bundle code revision is dirty")
    paths = [bundle["resolved_configuration"], bundle["environment"]]
    for key in ("dataset_manifests", "logs", "metrics", "outputs"):
        paths.extend(bundle[key])
    missing = [relative for relative in paths if not safe_child(args.root, relative).is_file()]
    if missing:
        raise ContractError("Run Bundle paths are missing: " + ", ".join(missing))
    return {"valid": True, "run_id": bundle["run_id"], "seed_count": len(bundle["seeds"])}


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


def command_verify_closure(args: argparse.Namespace) -> dict[str, Any]:
    lock = load_record(args.lock)
    validate_record(lock, "skills-lock")
    skills = lock["skills"]
    roots = args.root_skill
    missing_roots = [name for name in roots if name not in skills]
    if missing_roots:
        raise ContractError("Missing root skills in lock: " + ", ".join(missing_roots))

    closure: set[str] = set()
    visiting: set[str] = set()

    def visit(name: str) -> None:
        if name in closure:
            return
        if name in visiting:
            raise ContractError(f"Dependency cycle includes {name}")
        visiting.add(name)
        for dependency in skills[name]["dependencies"]:
            if dependency not in skills:
                raise ContractError(f"Missing dependency {dependency} required by {name}")
            visit(dependency)
        visiting.remove(name)
        closure.add(name)

    for root in roots:
        visit(root)
    for name in sorted(closure):
        folder = args.skills_dir / name
        if not (folder / "SKILL.md").is_file():
            raise ContractError(f"Missing skill package: {name}")
        actual = directory_hash(folder)
        if actual != skills[name]["content_hash"]:
            raise ContractError(f"Skill content hash mismatch: {name}")
    return {"valid": True, "roots": roots, "closure": sorted(closure)}


def command_check_specification_readiness(args: argparse.Namespace) -> dict[str, Any]:
    record = load_record(args.ambiguities)
    validate_record(record, "ambiguities")
    terminal = {"confirmed", "derived", "reconstructed", "empirically_selected", "excluded"}
    open_must = [
        item["ambiguity_id"]
        for item in record["ambiguities"]
        if item["scope"] == "must" and item["resolution"] not in terminal
    ]
    undocumented = [
        item["ambiguity_id"]
        for item in record["ambiguities"]
        if item["scope"] == "must"
        and item["resolution"] in {"derived", "reconstructed", "empirically_selected"}
        and not item.get("decision_record")
    ]
    if open_must or undocumented:
        details = []
        if open_must:
            details.append("open must ambiguities: " + ", ".join(open_must))
        if undocumented:
            details.append("missing decision records: " + ", ".join(undocumented))
        raise ContractError("Specification is blocked (" + "; ".join(details) + ")")
    return {"ready": True, "must_ambiguities": sum(1 for item in record["ambiguities"] if item["scope"] == "must")}


def command_evaluate(args: argparse.Namespace) -> dict[str, Any]:
    record = load_record(args.verdicts)
    validate_record(record, "claim-verdicts")
    must = [claim for claim in record["claims"] if claim["scope"] == "must"]
    if not must:
        raise ContractError("At least one must claim is required for an overall outcome")
    decisive = [
        claim
        for claim in must
        if claim["execution"] == "complete"
        and claim["result_agreement"] == "contradicted"
        and claim["evidence_strength"] in {"adequate", "strong"}
    ]
    supported = [
        claim
        for claim in must
        if claim["implementation"] == "supported"
        and claim["execution"] == "complete"
        and claim["result_agreement"] == "supported"
        and claim["evidence_strength"] in {"adequate", "strong"}
    ]
    if decisive:
        outcome = "not_replicated"
    elif len(supported) == len(must):
        outcome = "replicated"
    elif supported:
        outcome = "partially_replicated"
    else:
        outcome = "inconclusive"
    return {
        "outcome": outcome,
        "must_claims": len(must),
        "supported_must_claims": len(supported),
        "decisive_mismatches": [claim["claim_id"] for claim in decisive],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate a YAML or JSON contract")
    validate.add_argument("document", type=Path)
    validate.add_argument("--schema", required=True)
    validate.set_defaults(handler=command_validate)

    canonical_hash = commands.add_parser("canonical-hash", help="hash canonical JSON")
    canonical_hash.add_argument("document", type=Path)
    canonical_hash.set_defaults(handler=command_canonical_hash)

    transition = commands.add_parser("check-transition", help="check a lifecycle edge")
    transition.add_argument("state_file", type=Path)
    transition.add_argument("--to", dest="target", required=True)
    transition.add_argument("--return-target")
    transition.set_defaults(handler=command_check_transition)

    route = commands.add_parser("route", help="report the next legal stage skill")
    route.add_argument("state_file", type=Path)
    route.set_defaults(handler=command_route)

    gate = commands.add_parser("verify-gate", help="detect stale Gate Records")
    gate.add_argument("gate", type=Path)
    gate.add_argument("--root", type=Path, required=True)
    gate.set_defaults(handler=command_verify_gate)

    manifest = commands.add_parser("verify-manifest", help="verify dataset file identities")
    manifest.add_argument("manifest", type=Path)
    manifest.add_argument("--root", type=Path, required=True)
    manifest.set_defaults(handler=command_verify_manifest)

    run = commands.add_parser("verify-run-bundle", help="verify portable run evidence")
    run.add_argument("bundle", type=Path)
    run.add_argument("--root", type=Path, required=True)
    run.set_defaults(handler=command_verify_run_bundle)

    closure = commands.add_parser("verify-closure", help="verify a transitive Skill Closure")
    closure.add_argument("lock", type=Path)
    closure.add_argument("--skills-dir", type=Path, required=True)
    closure.add_argument("--root-skill", action="append", required=True)
    closure.set_defaults(handler=command_verify_closure)

    readiness = commands.add_parser(
        "check-specification-readiness", help="require terminal must ambiguities"
    )
    readiness.add_argument("ambiguities", type=Path)
    readiness.set_defaults(handler=command_check_specification_readiness)

    evaluate = commands.add_parser("evaluate", help="aggregate must-claim verdicts")
    evaluate.add_argument("verdicts", type=Path)
    evaluate.set_defaults(handler=command_evaluate)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = args.handler(args)
    except ContractError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
