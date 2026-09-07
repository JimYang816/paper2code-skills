#!/usr/bin/env python3
"""Deterministic setup, dossier, and workflow-state checks.

This command uses only the Python standard library. Scientific judgement stays
with the stage skills and the researcher.
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


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
INITIAL_RECORDS = {
    "dossier/evidence.yaml": "items",
    "dossier/ambiguities.yaml": "ambiguities",
    "dossier/scope-matrix.yaml": "claims",
}
VERIFY_CLOSURE = Path(__file__).with_name("verify_closure.py")
SCHEMAS_DIR = Path(__file__).resolve().parents[1] / "references" / "schemas" / "v1"
EVIDENCE_SCHEMA = SCHEMAS_DIR / "evidence.schema.json"
AUDIT_SCHEMA = SCHEMAS_DIR / "evidence-audit.schema.json"
AMBIGUITIES_SCHEMA = SCHEMAS_DIR / "ambiguities.schema.json"
WAYFINDING_SCHEMA = SCHEMAS_DIR / "wayfinding.schema.json"
GATE_SCHEMA = SCHEMAS_DIR / "evidence-gate.schema.json"
SCOPE_SCHEMA = SCHEMAS_DIR / "scope-matrix.schema.json"
SPEC_SCHEMA = SCHEMAS_DIR / "specification.schema.json"
SPEC_GATE_SCHEMA = SCHEMAS_DIR / "specification-gate.schema.json"
PLACEHOLDER_RE = re.compile(r"\b(TODO|TBD|FIXME|PLACEHOLDER)\b", flags=re.IGNORECASE)
UNRESOLVED_RE = re.compile(r"\b(UNKNOWN|TBD|TODO|FIXME|PLACEHOLDER)\b", flags=re.IGNORECASE)


class ContractError(ValueError):
    pass


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError(f"Cannot read {path}: {exc}") from exc


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_hash(document):
    return hashlib.sha256(canonical_json(load_json(document)).encode("utf-8")).hexdigest()


def json_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"


def resolve_ref(root, ref):
    if not ref.startswith("#/"):
        raise ContractError(f"Unsupported schema reference: {ref}")
    node = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            raise ContractError(f"Unresolved schema reference: {ref}")
        node = node[part]
    return node


def validate_against_schema(instance, schema, path="$", root=None):
    if root is None:
        root = schema
    if "$ref" in schema:
        validate_against_schema(instance, resolve_ref(root, schema["$ref"]), path, root)
        return
    if "const" in schema and instance != schema["const"]:
        raise ContractError(f"{path} must equal {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        allowed = ", ".join(repr(item) for item in schema["enum"])
        raise ContractError(f"{path} must be one of: {allowed}")

    declared = schema.get("type")
    if declared:
        allowed_types = declared if isinstance(declared, list) else [declared]
        actual = json_type(instance)
        if not any(
            actual == expected or (expected == "number" and actual == "integer")
            for expected in allowed_types
        ):
            expected = ", ".join(allowed_types)
            raise ContractError(f"{path} must be {expected}, got {actual}")

    if isinstance(instance, dict):
        for required in schema.get("required", []):
            if required not in instance:
                raise ContractError(f"{path} is missing required field {required!r}")
        properties = schema.get("properties", {})
        pattern_properties = schema.get("patternProperties", {})
        for key, value in instance.items():
            if key in properties:
                validate_against_schema(value, properties[key], f"{path}.{key}", root)
                continue
            matched = False
            for pattern, subschema in pattern_properties.items():
                if re.search(pattern, key):
                    validate_against_schema(value, subschema, f"{path}.{key}", root)
                    matched = True
            if matched:
                continue
            elif schema.get("additionalProperties") is False:
                raise ContractError(f"{path} has unexpected field {key!r}")
    elif isinstance(instance, list):
        if "items" in schema:
            for index, item in enumerate(instance):
                validate_against_schema(item, schema["items"], f"{path}[{index}]", root)
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise ContractError(f"{path} needs at least {schema['minItems']} items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise ContractError(f"{path} has more than {schema['maxItems']} items")
    elif isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise ContractError(f"{path} must have at least {schema['minLength']} characters")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], instance):
            raise ContractError(f"{path} does not match required pattern")

    if "minimum" in schema and isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if instance < schema["minimum"]:
            raise ContractError(f"{path} must be at least {schema['minimum']}")


def validate_schema_file(value, schema_path, label):
    try:
        schema = load_json(schema_path)
    except ContractError as exc:
        raise ContractError(f"Cannot read {label} schema: {exc}") from exc
    validate_against_schema(value, schema, label, root=schema)


def validate_state(value):
    if not isinstance(value, dict):
        raise ContractError("State must be an object")
    if set(value) != {"schema_version", "state", "return_target"}:
        raise ContractError("State must contain exactly schema_version, state, and return_target")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("Unsupported state schema version")
    if value.get("state") not in NORMAL_STATES + sorted(EXCEPTION_STATES):
        raise ContractError(f"Unknown workflow state: {value.get('state')}")
    return_target = value.get("return_target")
    if value["state"] in EXCEPTION_STATES:
        if return_target not in NORMAL_STATES:
            raise ContractError(f"Exception state requires a normal return target: {value['state']}")
    elif return_target is not None:
        raise ContractError(f"Normal state must have a null return target: {value['state']}")


def validate_initial_record(relative, value):
    if not isinstance(value, dict):
        raise ContractError(f"{relative} must be an object")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"Unsupported schema version in {relative}")
    key = INITIAL_RECORDS[relative]
    if key not in value or not isinstance(value[key], list):
        raise ContractError(f"{relative} must contain a {key} list")


def validate_closure(root):
    completed = subprocess.run(
        [sys.executable, str(VERIFY_CLOSURE), "--root", str(root)],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ContractError(completed.stderr.strip() or completed.stdout.strip())


def command_validate_setup(root):
    root = root.resolve()
    state_path = root / ".paper2code/state.yaml"
    if not state_path.is_file():
        raise ContractError("Missing .paper2code/state.yaml")
    state = load_json(state_path)
    validate_state(state)
    validate_closure(root)
    for relative in INITIAL_RECORDS:
        path = root / relative
        if not path.is_file():
            raise ContractError(f"Missing initial artifact: {relative}")
        validate_initial_record(relative, load_json(path))
    return {
        "valid": True,
        "state": state["state"],
        "artifacts": [".paper2code/state.yaml", *sorted(INITIAL_RECORDS)],
    }


def command_validate_dossier(root):
    root = root.resolve()
    paper_path = root / "dossier/paper.md"
    evidence_path = root / "dossier/evidence.yaml"
    audit_path = root / "dossier/audit.yaml"
    figures_path = root / "dossier/figures"

    for path in (paper_path, evidence_path, audit_path):
        if not path.is_file():
            raise ContractError(f"Missing dossier artifact: {path.relative_to(root)}")
    if not figures_path.is_dir():
        raise ContractError("Missing dossier/figures directory")

    paper = paper_path.read_text(encoding="utf-8")
    for heading in ("# Paper Dossier", "## Source", "## Evidence", "## Figures", "## Audit"):
        if heading not in paper:
            raise ContractError(f"dossier/paper.md is missing required heading {heading!r}")
    if re.search(r"\b(TODO|TBD|FIXME|PLACEHOLDER)\b", paper, flags=re.IGNORECASE):
        raise ContractError("dossier/paper.md contains unresolved placeholders")

    evidence = load_json(evidence_path)
    validate_schema_file(evidence, EVIDENCE_SCHEMA, "dossier/evidence.yaml")
    items = evidence.get("items", [])
    identifiers = [item["id"] for item in items]
    if len(identifiers) != len(set(identifiers)):
        raise ContractError("dossier/evidence.yaml contains duplicate Evidence Item identifiers")

    audit = load_json(audit_path)
    validate_schema_file(audit, AUDIT_SCHEMA, "dossier/audit.yaml")
    open_findings = []
    for item in audit.get("items", []):
        if item["status"] == "open":
            open_findings.append(item["id"])
        elif item["status"] == "triaged" and not item.get("triage_note"):
            raise ContractError(f"Triaged audit finding {item['id']} needs a triage note")
    if open_findings:
        raise ContractError(
            "Untriaged Evidence Audit findings: " + ", ".join(sorted(open_findings))
        )

    return {
        "valid": True,
        "evidence_items": len(items),
        "audit_findings": len(audit.get("items", [])),
        "artifacts": [
            "dossier/paper.md",
            "dossier/evidence.yaml",
            "dossier/audit.yaml",
            "dossier/figures",
        ],
    }


def command_validate_ambiguities(root):
    root = root.resolve()
    path = root / "dossier/ambiguities.yaml"
    if not path.is_file():
        raise ContractError("Missing dossier/ambiguities.yaml")
    document = load_json(path)
    validate_schema_file(document, AMBIGUITIES_SCHEMA, "dossier/ambiguities.yaml")

    ambiguities = document.get("ambiguities", [])
    identifiers = [item["id"] for item in ambiguities]
    if len(identifiers) != len(set(identifiers)):
        raise ContractError("dossier/ambiguities.yaml contains duplicate ambiguity identifiers")

    must = [item for item in ambiguities if item.get("scope") == "must"]
    unresolved = [item["id"] for item in must if item.get("status") != "resolved"]
    if unresolved:
        raise ContractError(
            "unresolved must-scope ambiguity: " + ", ".join(sorted(unresolved))
        )
    missing_resolution = [
        item["id"]
        for item in must
        if item.get("status") == "resolved"
        and not isinstance(item.get("resolution"), dict)
    ]
    if missing_resolution:
        raise ContractError(
            "resolved must-scope ambiguity is missing a resolution: "
            + ", ".join(sorted(missing_resolution))
        )

    return {
        "valid": True,
        "ambiguities": len(ambiguities),
        "must_total": len(must),
        "must_resolved": len([item for item in must if item.get("status") == "resolved"]),
        "artifacts": ["dossier/ambiguities.yaml"],
    }


def command_validate_wayfinding(root):
    root = root.resolve()
    path = root / "decisions/frontier.yaml"
    if not path.is_file():
        raise ContractError("Missing decisions/frontier.yaml")
    document = load_json(path)
    validate_schema_file(document, WAYFINDING_SCHEMA, "decisions/frontier.yaml")

    mapped = set()
    work_ids = set()
    for ambiguity in document.get("ambiguities", []):
        mapped.add(ambiguity["id"])
        for work in ambiguity.get("work", []):
            work_ids.add(work["id"])

    ambiguity_path = root / "dossier/ambiguities.yaml"
    if not ambiguity_path.is_file():
        raise ContractError("Missing dossier/ambiguities.yaml")
    ambiguity_document = load_json(ambiguity_path)
    known = {item["id"] for item in ambiguity_document.get("ambiguities", [])}
    unknown = sorted(mapped - known)
    if unknown:
        raise ContractError(
            "wayfinding map references unknown ambiguities: " + ", ".join(unknown)
        )

    frontier_ids = [item["id"] for item in document.get("frontier", [])]
    missing_work = sorted(set(frontier_ids) - work_ids)
    if missing_work:
        raise ContractError(
            "frontier items have no work entry: " + ", ".join(missing_work)
        )

    return {
        "valid": True,
        "mapped_ambiguities": len(document.get("ambiguities", [])),
        "frontier_items": len(document.get("frontier", [])),
        "artifacts": ["decisions/frontier.yaml"],
    }


def command_validate_evidence_gate(root):
    root = root.resolve()
    path = root / ".paper2code/gates/evidence-gate.yaml"
    if not path.is_file():
        raise ContractError("Missing .paper2code/gates/evidence-gate.yaml")
    document = load_json(path)
    validate_schema_file(document, GATE_SCHEMA, ".paper2code/gates/evidence-gate.yaml")
    return {
        "valid": True,
        "gate": document["gate"],
        "transition": document["transition"],
        "approved_by": document["approved_by"],
        "artifacts": sorted(document["artifacts"]),
    }


def has_unresolved_value(value):
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.lower() == "open":
            return True
        return bool(UNRESOLVED_RE.search(stripped))
    if isinstance(value, list):
        return any(has_unresolved_value(item) for item in value)
    if isinstance(value, dict):
        return any(has_unresolved_value(item) for item in value.values())
    return False


def item_has_unresolved(item, keys):
    return any(key in item and has_unresolved_value(item[key]) for key in keys)


def ensure_unique_ids(items, label):
    identifiers = [item["id"] for item in items]
    if len(identifiers) != len(set(identifiers)):
        raise ContractError(f"{label} contains duplicate identifiers")


def command_validate_scope_matrix(root):
    root = root.resolve()
    path = root / "dossier/scope-matrix.yaml"
    if not path.is_file():
        raise ContractError("Missing dossier/scope-matrix.yaml")
    document = load_json(path)
    validate_schema_file(document, SCOPE_SCHEMA, "dossier/scope-matrix.yaml")

    claims = document.get("claims", [])
    ensure_unique_ids(claims, "dossier/scope-matrix.yaml claims")
    for claim in claims:
        if claim.get("scope") == "must" and item_has_unresolved(
            claim, {"title", "rationale"}
        ):
            raise ContractError(
                f"must-scope claim {claim['id']} contains an unresolved value"
            )

    return {
        "valid": True,
        "claims": len(claims),
        "must_claims": len([item for item in claims if item.get("scope") == "must"]),
        "artifacts": ["dossier/scope-matrix.yaml"],
    }


def command_validate_specification(root):
    root = root.resolve()
    spec_path = root / "specification/specification.yaml"
    paper_path = root / "specification/paper-spec.md"
    if not spec_path.is_file():
        raise ContractError("Missing specification/specification.yaml")
    if not paper_path.is_file():
        raise ContractError("Missing specification/paper-spec.md")

    document = load_json(spec_path)
    validate_schema_file(document, SPEC_SCHEMA, "specification/specification.yaml")

    sections = ("method", "data", "baselines", "experiments", "figures", "metrics")
    for section in sections:
        ensure_unique_ids(
            document.get(section, []), f"specification/specification.yaml {section}"
        )
    ensure_unique_ids(
        document["scope"]["claims"], "specification/specification.yaml scope.claims"
    )
    ensure_unique_ids(
        document["acceptance"]["rules"], "specification/specification.yaml acceptance.rules"
    )

    claim_ids = {item["id"] for item in document["scope"]["claims"]}
    metric_ids = {item["id"] for item in document["metrics"]}
    for rule in document["acceptance"]["rules"]:
        if rule.get("scope") != "must":
            continue
        if rule["metric_id"] not in metric_ids:
            raise ContractError(
                f"acceptance rule {rule['id']} references unknown metric {rule['metric_id']}"
            )
        missing_claims = sorted(set(rule["claim_ids"]) - claim_ids)
        if missing_claims:
            raise ContractError(
                f"acceptance rule {rule['id']} references unknown claims: "
                + ", ".join(missing_claims)
            )
        if item_has_unresolved(rule, {"criterion", "tolerance"}):
            raise ContractError(
                f"must-scope acceptance rule {rule['id']} contains an unresolved value"
            )

    for section in sections:
        for item in document[section]:
            if item.get("scope") == "must" and item_has_unresolved(
                item, {"title", "specification", "acceptance", "unit"}
            ):
                raise ContractError(
                    f"must-scope {section.rstrip('s')} item {item['id']} contains an unresolved value"
                )

    paper = paper_path.read_text(encoding="utf-8")
    for heading in (
        "# Paper Specification",
        "## Scope",
        "## Method",
        "## Data",
        "## Baselines",
        "## Experiments",
        "## Figures",
        "## Metrics",
        "## Uncertainty",
        "## Budget",
        "## Acceptance",
    ):
        if heading not in paper:
            raise ContractError(
                f"specification/paper-spec.md is missing required heading {heading!r}"
            )
    if PLACEHOLDER_RE.search(paper):
        raise ContractError("specification/paper-spec.md contains unresolved placeholders")

    return {
        "valid": True,
        "scope_claims": len(document["scope"]["claims"]),
        "method_items": len(document["method"]),
        "data_items": len(document["data"]),
        "baseline_items": len(document["baselines"]),
        "experiment_items": len(document["experiments"]),
        "figure_items": len(document["figures"]),
        "metric_items": len(document["metrics"]),
        "acceptance_rules": len(document["acceptance"]["rules"]),
        "artifacts": [
            "specification/specification.yaml",
            "specification/paper-spec.md",
        ],
    }


def command_validate_specification_gate(root):
    root = root.resolve()
    path = root / ".paper2code/gates/specification-gate.yaml"
    if not path.is_file():
        raise ContractError("Missing .paper2code/gates/specification-gate.yaml")
    document = load_json(path)
    validate_schema_file(
        document, SPEC_GATE_SCHEMA, ".paper2code/gates/specification-gate.yaml"
    )
    return {
        "valid": True,
        "gate": document["gate"],
        "transition": document["transition"],
        "approved_by": document["approved_by"],
        "artifacts": sorted(document["artifacts"]),
        "schemas": sorted(document["schemas"]),
    }


def transition_allowed(current, target, return_target):
    if target in EXCEPTION_STATES:
        return current in NORMAL_STATES and return_target == current
    if current in EXCEPTION_STATES:
        return bool(return_target) and target == return_target
    try:
        return NORMAL_STATES.index(target) == NORMAL_STATES.index(current) + 1
    except ValueError:
        return False


def command_check_transition(state_file, target, return_target):
    state = load_json(state_file)
    validate_state(state)
    current = state["state"]
    if current in EXCEPTION_STATES:
        effective_return = state.get("return_target")
    else:
        effective_return = return_target or state.get("return_target")
    if not transition_allowed(current, target, effective_return):
        message = f"Illegal workflow transition: {current} -> {target}"
        if effective_return:
            message += f" (return target {effective_return})"
        raise ContractError(message)
    return {
        "legal": True,
        "from": current,
        "to": target,
        "return_target": effective_return,
    }


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate-setup", help="validate initial setup artifacts")
    validate.add_argument("--root", type=Path, required=True)
    validate.set_defaults(handler=lambda args: command_validate_setup(args.root))

    dossier = commands.add_parser("validate-dossier", help="validate extracted dossier artifacts")
    dossier.add_argument("--root", type=Path, required=True)
    dossier.set_defaults(handler=lambda args: command_validate_dossier(args.root))

    ambiguities = commands.add_parser(
        "validate-ambiguities", help="validate ambiguity resolutions and must-scope closure"
    )
    ambiguities.add_argument("--root", type=Path, required=True)
    ambiguities.set_defaults(handler=lambda args: command_validate_ambiguities(args.root))

    wayfinding = commands.add_parser(
        "validate-wayfinding", help="validate the wayfinding decision frontier"
    )
    wayfinding.add_argument("--root", type=Path, required=True)
    wayfinding.set_defaults(handler=lambda args: command_validate_wayfinding(args.root))

    gate = commands.add_parser("validate-evidence-gate", help="validate the Evidence Gate record")
    gate.add_argument("--root", type=Path, required=True)
    gate.set_defaults(handler=lambda args: command_validate_evidence_gate(args.root))

    scope = commands.add_parser("validate-scope-matrix", help="validate the Scope Matrix")
    scope.add_argument("--root", type=Path, required=True)
    scope.set_defaults(handler=lambda args: command_validate_scope_matrix(args.root))

    specification = commands.add_parser(
        "validate-specification", help="validate the paper specification"
    )
    specification.add_argument("--root", type=Path, required=True)
    specification.set_defaults(handler=lambda args: command_validate_specification(args.root))

    specification_gate = commands.add_parser(
        "validate-specification-gate", help="validate the Specification Gate record"
    )
    specification_gate.add_argument("--root", type=Path, required=True)
    specification_gate.set_defaults(
        handler=lambda args: command_validate_specification_gate(args.root)
    )

    hash_command = commands.add_parser("canonical-hash", help="hash canonical JSON")
    hash_command.add_argument("document", type=Path)
    hash_command.set_defaults(
        handler=lambda args: {"path": str(args.document), "sha256": canonical_hash(args.document)}
    )

    verify_hash = commands.add_parser("verify-hash", help="verify a canonical JSON hash")
    verify_hash.add_argument("document", type=Path)
    verify_hash.add_argument("--expected", required=True)
    verify_hash.set_defaults(handler=lambda args: command_verify_hash(args.document, args.expected))

    transition = commands.add_parser("check-transition", help="check a lifecycle edge")
    transition.add_argument("state_file", type=Path)
    transition.add_argument("--to", dest="target", required=True)
    transition.add_argument("--return-target")
    transition.set_defaults(
        handler=lambda args: command_check_transition(
            args.state_file, args.target, args.return_target
        )
    )
    return parser


def command_verify_hash(document, expected):
    actual = canonical_hash(document)
    if actual != expected:
        raise ContractError(f"Hash mismatch for {document}: expected {expected}, got {actual}")
    return {"valid": True, "path": str(document), "sha256": actual}


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
