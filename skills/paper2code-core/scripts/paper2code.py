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
VALIDATION_SCHEMA = SCHEMAS_DIR / "validation.schema.json"
VALIDATION_REPORT_SCHEMA = SCHEMAS_DIR / "validation-report.schema.json"
RUN_SCHEMA = SCHEMAS_DIR / "run.schema.json"
FULL_RUN_GATE_SCHEMA = SCHEMAS_DIR / "full-run-gate.schema.json"
FULL_RUN_REPORT_SCHEMA = SCHEMAS_DIR / "full-run-report.schema.json"
VALIDATION_KINDS = {"data", "model", "baseline", "metric", "reporting"}
VALIDATION_CHECKS = ("invariants", "units", "shapes", "gradients")
RUN_FAILURE_CLASSES = {"software", "scientific", "evidence", "environment"}
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


def _validate_relative_artifact(relative, label):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ContractError(f"{label} must be a relative path: {relative}")


def _validate_validation_contract(document, root):
    validate_schema_file(document, VALIDATION_SCHEMA, "validation/validation.yaml")
    if has_unresolved_value(document):
        raise ContractError("validation/validation.yaml contains unresolved placeholders")

    math_items = document["critical_math"]
    ensure_unique_ids(math_items, "validation/validation.yaml critical_math")
    for item in math_items:
        reference = item["reference"]
        _validate_relative_artifact(reference, "critical_math reference")
        if not reference.startswith("validation/references/"):
            raise ContractError(
                f"critical math reference must be under validation/references/: {reference}"
            )
        if not (root / reference).is_file():
            raise ContractError(f"Missing independent numerical reference: {reference}")
        checks = item["checks"]
        not_applicable = set(checks["not_applicable"])
        if len(not_applicable) != len(checks["not_applicable"]):
            raise ContractError(f"Duplicate not_applicable check in {item['id']}")
        all_ids = []
        for check in VALIDATION_CHECKS:
            values = checks[check]
            if check in not_applicable:
                if values:
                    raise ContractError(
                        f"{item['id']} marks {check} not applicable but declares checks"
                    )
            elif not values:
                raise ContractError(
                    f"{item['id']} needs an applicable {check} check or marks it not_applicable"
                )
            all_ids.extend(values)
        if len(all_ids) != len(set(all_ids)):
            raise ContractError(f"{item['id']} contains duplicate check identifiers")

    paths = document["paths"]
    ensure_unique_ids(paths, "validation/validation.yaml paths")
    kinds = {item["kind"] for item in paths}
    missing_kinds = sorted(VALIDATION_KINDS - kinds)
    if missing_kinds:
        raise ContractError(
            "validation/validation.yaml is missing required pipeline paths: "
            + ", ".join(missing_kinds)
        )
    for item in paths:
        for artifact in item["artifacts"]:
            _validate_relative_artifact(artifact, f"{item['id']} artifact")

    return {
        "valid": True,
        "critical_math": len(math_items),
        "paths": len(paths),
        "path_kinds": sorted(kinds),
        "artifacts": ["validation/validation.yaml"],
    }


def command_validate_cpu_contract(root):
    root = root.resolve()
    path = root / "validation/validation.yaml"
    if not path.is_file():
        raise ContractError("Missing validation/validation.yaml")
    return _validate_validation_contract(load_json(path), root)


def command_validate_cpu_report(root):
    root = root.resolve()
    contract_result = command_validate_cpu_contract(root)
    contract = load_json(root / "validation/validation.yaml")
    path = root / "validation/reports/cpu-validation.yaml"
    if not path.is_file():
        raise ContractError("Missing validation/reports/cpu-validation.yaml")
    report = load_json(path)
    validate_schema_file(report, VALIDATION_REPORT_SCHEMA, "validation/reports/cpu-validation.yaml")
    if report["contract_sha256"] != canonical_hash(root / "validation/validation.yaml"):
        raise ContractError("CPU Validation Report is stale: validation contract changed")
    if report["deterministic"] != contract["deterministic"]:
        raise ContractError("CPU Validation Report deterministic settings differ from contract")

    expected_math = {item["id"] for item in contract["critical_math"]}
    actual_math = {item["id"] for item in report["math"]}
    ensure_unique_ids(report["math"], "CPU Validation Report math results")
    if actual_math != expected_math:
        raise ContractError("CPU Validation Report does not cover every critical math reference")
    expected_paths = {item["id"] for item in contract["paths"]}
    actual_paths = {item["id"] for item in report["paths"]}
    ensure_unique_ids(report["paths"], "CPU Validation Report path results")
    if actual_paths != expected_paths:
        raise ContractError("CPU Validation Report does not cover every pipeline path")

    expected_math_items = {item["id"]: item for item in contract["critical_math"]}
    for result in report["math"]:
        expected = expected_math_items[result["id"]]
        for group in VALIDATION_CHECKS:
            required = set(expected["checks"][group])
            if not required:
                continue
            observed = result["checks"].get(group)
            if not isinstance(observed, list) or not required <= set(observed):
                missing = sorted(required - set(observed or []))
                raise ContractError(
                    f"CPU Validation Report is missing {group} checks for {result['id']}: "
                    + ", ".join(missing)
                )

    expected_path_items = {item["id"]: item for item in contract["paths"]}
    for result in report["paths"]:
        expected = expected_path_items[result["id"]]
        if result["kind"] != expected["kind"]:
            raise ContractError(f"CPU Validation Report has the wrong kind for {result['id']}")
        if set(result["artifacts"]) != set(expected["artifacts"]):
            raise ContractError(
                f"CPU Validation Report has the wrong artifacts for {result['id']}"
            )

    if report["status"] == "passed":
        if report["state"] != "cpu_validated" or report["return_target"] is not None:
            raise ContractError("Passed CPU Validation Report must target cpu_validated")
        if report["failure"] is not None:
            raise ContractError("Passed CPU Validation Report cannot contain a failure")
        if any(item["status"] != "passed" for item in [*report["math"], *report["paths"]]):
            raise ContractError("Passed CPU Validation Report contains a failed check")
    else:
        if report["failure"] is None:
            raise ContractError("Failed CPU Validation Report must classify a failure")
        if report["state"] == "cpu_validated":
            raise ContractError("Failed CPU Validation Report cannot target cpu_validated")

    for relative, expected_hash in report["artifacts"].items():
        _validate_relative_artifact(relative, "CPU Validation Report artifact")
        artifact = root / relative
        if not artifact.is_file():
            raise ContractError(f"CPU Validation Report references missing artifact: {relative}")
        actual_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if expected_hash != actual_hash:
            raise ContractError(f"CPU Validation Report has a stale artifact hash: {relative}")
    return {
        "valid": True,
        "status": report["status"],
        "state": report["state"],
        "failure": report["failure"],
        "contract": contract_result,
        "artifacts": ["validation/reports/cpu-validation.yaml", *sorted(report["artifacts"])],
    }


def raw_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_run_bundle(root, run_id=None):
    root = root.resolve()
    if run_id:
        candidates = [root / "runs" / run_id / "bundle.yaml"]
    else:
        runs = root / "runs"
        candidates = sorted(runs.glob("*/bundle.yaml")) if runs.is_dir() else []
    if len(candidates) != 1:
        if not candidates:
            raise ContractError("Missing runs/<run-id>/bundle.yaml")
        raise ContractError("Multiple Full Run bundles found; pass --run-id")
    path = candidates[0]
    bundle = load_json(path)
    return path, bundle


def _run_substitutions(root, run_id, seed, portable=False):
    run_dir = f"runs/{run_id}" if portable else str(root / "runs" / run_id)
    root_value = "." if portable else str(root)
    return {
        "{root}": root_value,
        "{run_dir}": run_dir,
        "{seed}": str(seed),
        "{python}": "{python}" if portable else sys.executable,
        "{workers}": "1",
    }


def _replace_run_tokens(value, substitutions):
    for token, replacement in substitutions.items():
        value = value.replace(token, replacement)
    return value


def _validate_run_relative(relative, label):
    _validate_relative_artifact(relative, label)
    if "{" in relative or "}" in relative:
        raise ContractError(f"{label} contains an unresolved substitution: {relative}")


def _run_artifact_paths(root, bundle, command, seed, portable=True):
    substitutions = _run_substitutions(root, bundle["run_id"], seed, portable=portable)
    values = {
        "log": _replace_run_tokens(command["log"], substitutions),
        "metrics": [_replace_run_tokens(item, substitutions) for item in command["metrics"]],
        "outputs": [_replace_run_tokens(item, substitutions) for item in command["outputs"]],
    }
    for kind, paths in values.items():
        if isinstance(paths, str):
            paths = [paths]
        for path in paths:
            _validate_run_relative(path, f"{command['id']} {kind} artifact")
    return values


def _validate_run_bundle(root, run_id=None):
    root = root.resolve()
    path, bundle = _find_run_bundle(root, run_id)
    validate_schema_file(bundle, RUN_SCHEMA, "runs/<run-id>/bundle.yaml")
    if path.parent.name != bundle["run_id"]:
        raise ContractError("Full Run directory name must match bundle run_id")
    if not bundle["resolved_config"]:
        raise ContractError("Full Run resolved_config must not be empty")

    dataset_ids = [item["id"] for item in bundle["datasets"]]
    ensure_unique_ids(bundle["datasets"], "Full Run datasets")
    if len(bundle["seeds"]) != len(set(bundle["seeds"])):
        raise ContractError("Full Run seeds must be unique")
    capabilities = [item["id"] for item in bundle["environment"]["capabilities"]]
    if len(capabilities) != len(set(capabilities)):
        raise ContractError("Full Run capabilities must be unique")
    ensure_unique_ids(bundle["commands"], "Full Run commands")

    for item in bundle["datasets"]:
        _validate_relative_artifact(item["path"], f"{item['id']} dataset")
        dataset_path = root / item["path"]
        if not dataset_path.is_file():
            raise ContractError(f"Missing Full Run dataset: {item['path']}")
        actual = raw_hash(dataset_path)
        if actual != item["sha256"]:
            raise ContractError(f"Full Run dataset hash mismatch: {item['path']}")

    expected = []
    for command in bundle["commands"]:
        if any("\u0000" in token for token in command["command"]):
            raise ContractError(f"Full Run command contains a NUL byte: {command['id']}")
        for seed in bundle["seeds"]:
            artifact_paths = _run_artifact_paths(root, bundle, command, seed, portable=True)
            expected.append(
                {
                    "id": command["id"],
                    "seed": seed,
                    "command": [
                        _replace_run_tokens(token, _run_substitutions(root, bundle["run_id"], seed, portable=True))
                        for token in command["command"]
                    ],
                    **artifact_paths,
                }
            )

    return {
        "valid": True,
        "run_id": bundle["run_id"],
        "bundle_path": path.relative_to(root).as_posix(),
        "bundle_sha256": canonical_hash(path),
        "dataset_ids": dataset_ids,
        "seeds": bundle["seeds"],
        "commands": len(expected),
        "expected": expected,
    }, bundle


def command_validate_run_bundle(root, run_id=None):
    result, _bundle = _validate_run_bundle(root, run_id)
    return result


def command_validate_full_run_gate(root):
    root = root.resolve()
    path = root / ".paper2code/gates/full-run-gate.yaml"
    if not path.is_file():
        raise ContractError("Missing .paper2code/gates/full-run-gate.yaml")
    gate = load_json(path)
    validate_schema_file(gate, FULL_RUN_GATE_SCHEMA, ".paper2code/gates/full-run-gate.yaml")
    bundle_result, _bundle = _validate_run_bundle(root, gate["run_id"])
    if gate["bundle_path"] != bundle_result["bundle_path"]:
        raise ContractError("Full Run Gate points to a different bundle path")
    if gate["bundle_sha256"] != bundle_result["bundle_sha256"]:
        raise ContractError("stale Full Run approval: bundle changed")
    report_path = root / gate["cpu_validation_report_path"]
    if not report_path.is_file():
        raise ContractError("Full Run Gate references a missing CPU Validation Report")
    if gate["cpu_validation_report_sha256"] != canonical_hash(report_path):
        raise ContractError("stale Full Run approval: CPU Validation Report changed")
    for name, relative in {
        "run": "skills/paper2code-core/references/schemas/v1/run.schema.json",
        "gate": "skills/paper2code-core/references/schemas/v1/full-run-gate.schema.json",
        "report": "skills/paper2code-core/references/schemas/v1/full-run-report.schema.json",
    }.items():
        schema_path = root / relative
        if not schema_path.is_file() or gate["schemas"][name] != raw_hash(schema_path):
            raise ContractError(f"Full Run Gate schema identity is stale: {name}")
    return {
        "valid": True,
        "gate": ".paper2code/gates/full-run-gate.yaml",
        "run_id": gate["run_id"],
        "bundle_sha256": gate["bundle_sha256"],
        "approval_sha256": canonical_hash(path),
        "code_revision": gate["code_revision"],
    }


def command_validate_full_run_report(root, run_id=None):
    root = root.resolve()
    gate_result = command_validate_full_run_gate(root)
    selected_id = run_id or gate_result["run_id"]
    bundle_result, bundle = _validate_run_bundle(root, selected_id)
    if selected_id != gate_result["run_id"]:
        raise ContractError("Full Run report run_id differs from the approved run")
    report_path = root / "runs" / selected_id / "report.yaml"
    if not report_path.is_file():
        raise ContractError("Missing runs/<run-id>/report.yaml")
    report = load_json(report_path)
    validate_schema_file(report, FULL_RUN_REPORT_SCHEMA, "runs/<run-id>/report.yaml")
    if report["run_id"] != selected_id:
        raise ContractError("Full Run report run_id differs from its bundle")
    if report["bundle_sha256"] != bundle_result["bundle_sha256"]:
        raise ContractError("Full Run report is stale: bundle changed")
    if report["approval_sha256"] != gate_result["approval_sha256"]:
        raise ContractError("Full Run report is stale: approval changed")
    if report["code_revision"] != gate_result["code_revision"]:
        raise ContractError("Full Run report code revision differs from approval")

    expected = bundle_result["expected"]
    expected_keys = {(item["id"], item["seed"]): item for item in expected}
    actual_keys = {(item["id"], item["seed"]) for item in report["commands"]}
    if actual_keys != set(expected_keys):
        raise ContractError("Full Run report does not cover every command and seed")
    for result in report["commands"]:
        wanted = expected_keys[(result["id"], result["seed"])]
        if result["command"] != wanted["command"]:
            raise ContractError(f"Full Run report command differs for {result['id']} seed {result['seed']}")
        if result["log"] != wanted["log"] or result["metrics"] != wanted["metrics"] or result["outputs"] != wanted["outputs"]:
            raise ContractError(f"Full Run report artifacts differ for {result['id']} seed {result['seed']}")

    expected_artifacts = {
        path
        for result in expected
        for path in [result["log"], *result["metrics"], *result["outputs"]]
    }
    if report["status"] == "passed":
        if report["failure"] is not None:
            raise ContractError("Passed Full Run report cannot contain a failure")
        if any(item["status"] != "passed" or item["exit_code"] != 0 for item in report["commands"]):
            raise ContractError("Passed Full Run report contains a failed command")
        if set(report["artifacts"]) != expected_artifacts:
            raise ContractError("Passed Full Run report does not hash every expected artifact")
    elif report["failure"] is None:
        raise ContractError("Failed Full Run report must classify a failure")

    for relative, expected_hash in report["artifacts"].items():
        _validate_relative_artifact(relative, "Full Run report artifact")
        artifact = root / relative
        if not artifact.is_file():
            raise ContractError(f"Full Run report references missing artifact: {relative}")
        actual_hash = raw_hash(artifact)
        if actual_hash != expected_hash:
            raise ContractError(f"Full Run report has a stale artifact hash: {relative}")

    return {
        "valid": True,
        "status": report["status"],
        "execution_mode": report["execution_mode"],
        "run_id": selected_id,
        "artifacts": sorted(report["artifacts"]),
        "bundle": bundle_result,
        "environment": bundle["environment"],
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
    if target == "cpu_validated":
        try:
            command_validate_cpu_report(state_file.resolve().parent.parent)
        except ContractError as exc:
            raise ContractError(f"CPU Validation Report required before cpu_validated: {exc}") from exc
    if target == "full_run_complete":
        try:
            report_result = command_validate_full_run_report(state_file.resolve().parent.parent)
            if report_result["status"] != "passed":
                raise ContractError("Full Run Report is not a passed report")
        except ContractError as exc:
            raise ContractError(f"Full Run Report required before full_run_complete: {exc}") from exc
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

    for name in ("validate-cpu-contract", "validate-validation"):
        cpu_contract = commands.add_parser(name, help="validate the CPU Validation contract")
        cpu_contract.add_argument("--root", type=Path, required=True)
        cpu_contract.set_defaults(handler=lambda args: command_validate_cpu_contract(args.root))

    for name in ("validate-cpu-report", "validate-validation-report"):
        cpu_report = commands.add_parser(name, help="validate the CPU Validation Report")
        cpu_report.add_argument("--root", type=Path, required=True)
        cpu_report.set_defaults(handler=lambda args: command_validate_cpu_report(args.root))

    run_bundle = commands.add_parser("validate-run-bundle", help="validate a portable Full Run bundle")
    run_bundle.add_argument("--root", type=Path, required=True)
    run_bundle.add_argument("--run-id")
    run_bundle.set_defaults(
        handler=lambda args: command_validate_run_bundle(args.root, args.run_id)
    )

    run_gate = commands.add_parser("validate-full-run-gate", help="validate a Full Run approval")
    run_gate.add_argument("--root", type=Path, required=True)
    run_gate.set_defaults(handler=lambda args: command_validate_full_run_gate(args.root))

    run_report = commands.add_parser("validate-full-run-report", help="validate a completed Full Run")
    run_report.add_argument("--root", type=Path, required=True)
    run_report.add_argument("--run-id")
    run_report.set_defaults(
        handler=lambda args: command_validate_full_run_report(args.root, args.run_id)
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
