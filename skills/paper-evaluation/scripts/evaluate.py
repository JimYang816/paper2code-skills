#!/usr/bin/env python3
"""Evaluate a validated Full Run against a frozen claim contract."""

import argparse
import datetime as _datetime
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys


SCHEMA_VERSION = "1.0"
SOURCE_STATE = "full_run_complete"
TARGET_STATE = "evaluated"
CONTRACT_RELATIVE = "results/evaluation.yaml"
REPORT_RELATIVE = "results/evaluation-report.yaml"
FULL_RUN_REPORT_RELATIVE = "runs/{run_id}/report.yaml"
STATE_RELATIVE = ".paper2code/state.yaml"
STRENGTH_RANK = {"low": 0, "moderate": 1, "high": 2}


class ContractError(ValueError):
    pass


class EvaluationFailure(ContractError):
    def __init__(self, failure_class, identifier, message):
        super().__init__(message)
        self.failure_class = failure_class
        self.identifier = identifier
        self.message = message


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


def raw_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_core(root, *arguments):
    completed = subprocess.run(
        [sys.executable, str(root / "skills/paper2code-core/scripts/paper2code.py"), *arguments],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ContractError(completed.stderr.strip() or completed.stdout.strip())
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ContractError("Core validator returned invalid JSON") from exc


def read_state(root):
    state = load_json(root / STATE_RELATIVE)
    if state.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("Unsupported state schema version")
    return state


def metric_path(root, run_id, template, seed):
    value = template.replace("{root}", str(root))
    value = value.replace("{run_dir}", str(root / "runs" / run_id))
    value = value.replace("{seed}", str(seed))
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise EvaluationFailure("evidence", "metric", f"Metric path escapes repository root: {template}") from exc


def json_pointer(value, pointer):
    if pointer == "":
        return value
    if not pointer.startswith("/"):
        raise ValueError("JSON Pointer must be empty or start with '/'")
    current = value
    for raw_part in pointer[1:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise KeyError(part)
    return current


def aggregate(values, aggregation):
    if not values:
        raise ValueError("no metric values")
    if aggregation == "mean":
        return sum(values) / len(values)
    if aggregation == "median":
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[middle]
        return (ordered[middle - 1] + ordered[middle]) / 2
    if aggregation == "min":
        return min(values)
    if aggregation == "max":
        return max(values)
    if aggregation in ("first", "single"):
        if aggregation == "single" and len(values) != 1:
            raise ValueError("single aggregation requires exactly one value")
        return values[0]
    raise ValueError(f"Unsupported metric aggregation: {aggregation}")


def compare(observed, metric, uncertainty):
    target = metric["target"]
    tolerance = metric["tolerance"]
    comparison = metric["comparison"]
    if comparison in ("within", "equal"):
        return abs(observed - target) <= tolerance + uncertainty
    if comparison == "lte":
        return observed <= target + tolerance + uncertainty
    if comparison == "gte":
        return observed >= target - tolerance - uncertainty
    raise ValueError(f"Unsupported metric comparison: {comparison}")


def evidence_strength(provenance, seed_count, digitization_uncertainty):
    if seed_count >= 3:
        strength = "high"
    elif seed_count >= 2:
        strength = "moderate"
    else:
        strength = "low"
    if provenance in {"reconstructed", "derived", "empirical", "excluded"}:
        strength = min(strength, "moderate", key=lambda value: STRENGTH_RANK[value])
    if digitization_uncertainty > 0:
        strength = min(strength, "moderate", key=lambda value: STRENGTH_RANK[value])
    return strength


def validation_results(root):
    report = load_json(root / "validation/reports/cpu-validation.yaml")
    values = {}
    for group in ("math", "paths"):
        for item in report.get(group, []):
            values[item["id"]] = item
    return values


def implementation_assessment(claim, validations):
    identifiers = claim["implementation"]["validation_ids"]
    missing = [identifier for identifier in identifiers if identifier not in validations]
    failed = [identifier for identifier in identifiers if identifier in validations and validations[identifier].get("status") != "passed"]
    if missing:
        return {
            "status": "inconclusive",
            "validation_ids": identifiers,
            "message": "No CPU Validation result for: " + ", ".join(missing),
        }
    if failed:
        return {
            "status": "failed",
            "validation_ids": identifiers,
            "message": "CPU Validation failed for: " + ", ".join(failed),
        }
    return {"status": "passed", "validation_ids": identifiers, "message": ""}


def execution_assessment(claim, bundle, full_report):
    execution = claim["execution"]
    command_ids = execution["command_ids"]
    seeds = execution.get("seeds", bundle["seeds"])
    minimum = execution.get("minimum_successful_seeds", len(seeds))
    selected = [
        item for item in full_report["commands"]
        if item["id"] in command_ids and item["seed"] in seeds
    ]
    expected_count = len(command_ids) * len(seeds)
    passed = [item for item in selected if item["status"] == "passed" and item["exit_code"] == 0]
    if len(selected) != expected_count:
        return {
            "status": "inconclusive",
            "command_ids": command_ids,
            "seeds": sorted({item["seed"] for item in passed}),
            "message": "Full Run report is missing command or seed coverage",
        }
    if len({item["seed"] for item in passed}) < minimum or len(passed) != expected_count:
        return {
            "status": "failed",
            "command_ids": command_ids,
            "seeds": sorted({item["seed"] for item in passed}),
            "message": "Full Run execution is incomplete for the claim",
        }
    return {
        "status": "passed",
        "command_ids": command_ids,
        "seeds": sorted({item["seed"] for item in passed}),
        "message": "",
    }


def result_assessment(root, run_id, claim, metric, full_report, seeds):
    values = []
    paths = []
    command_ids = set(claim["execution"]["command_ids"])
    for seed in seeds:
        matching = [
            item for item in full_report["commands"]
            if item["id"] in command_ids and item["seed"] == seed and item["status"] == "passed"
        ]
        if not matching:
            continue
        relative = metric_path(root, run_id, metric["path"], seed)
        if relative not in matching[0]["metrics"]:
            raise EvaluationFailure(
                "evidence", claim["id"], f"Metric artifact is not declared by Full Run: {relative}"
            )
        path = root / relative
        if not path.is_file():
            raise EvaluationFailure("evidence", claim["id"], f"Missing metric artifact: {relative}")
        try:
            value = json_pointer(load_json(path), metric["json_pointer"])
        except (ContractError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise EvaluationFailure("evidence", claim["id"], f"Cannot read metric {relative}: {exc}") from exc
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise EvaluationFailure("scientific", claim["id"], f"Metric {metric['id']} is not a finite number")
        values.append(float(value))
        paths.append(relative)
    if not values:
        return {
            "status": "inconclusive",
            "metric_id": metric["id"],
            "observed": None,
            "target": metric["target"],
            "tolerance": metric["tolerance"],
            "message": "No successful metric values were available",
        }, paths
    try:
        observed = aggregate(values, metric["aggregation"])
    except ValueError as exc:
        raise EvaluationFailure("evidence", claim["id"], str(exc)) from exc
    agreed = compare(observed, metric, claim["evidence"]["digitization_uncertainty"])
    return {
        "status": "passed" if agreed else "failed",
        "metric_id": metric["id"],
        "observed": observed,
        "target": metric["target"],
        "tolerance": metric["tolerance"],
        "message": "" if agreed else "Observed value is outside the preregistered tolerance",
    }, paths


def claim_verdict(claim, implementation, execution, result, evidence):
    evidence_ok = evidence["sufficient"]
    if implementation["status"] != "passed" or execution["status"] != "passed" or not evidence_ok:
        verdict = "inconclusive"
    elif result["status"] == "passed":
        verdict = "replicated"
    elif result["status"] == "failed":
        verdict = "not replicated"
    else:
        verdict = "inconclusive"
    return {
        "id": claim["id"],
        "title": claim["title"],
        "scope": claim["scope"],
        "implementation": implementation,
        "execution": execution,
        "result_agreement": result,
        "evidence": evidence,
        "verdict": verdict,
    }


def failed_claim_assessment(claim, metric, implementation, execution, message):
    selected_seeds = execution["seeds"]
    strength = evidence_strength(
        claim["evidence"]["provenance"],
        len(selected_seeds),
        claim["evidence"]["digitization_uncertainty"],
    )
    return claim_verdict(
        claim,
        implementation,
        execution,
        {
            "status": "inconclusive",
            "metric_id": metric["id"],
            "observed": None,
            "target": metric["target"],
            "tolerance": metric["tolerance"],
            "message": message,
        },
        {
            "strength": strength,
            "minimum_strength": claim["evidence"]["minimum_strength"],
            "sufficient": False,
            "seed_count": len(selected_seeds),
            "message": message,
        },
    )


def overall_outcome(claims):
    must = [claim for claim in claims if claim["scope"] == "must"]
    if not must:
        return "inconclusive"
    if any(claim["verdict"] == "not replicated" for claim in must):
        return "not replicated"
    if all(claim["verdict"] == "replicated" for claim in must):
        return "replicated"
    if any(claim["verdict"] == "replicated" for claim in must):
        return "partially replicated"
    return "inconclusive"


def route_failure(root, failure):
    routes = {
        "software": "diagnosing",
        "scientific": "diagnosing",
        "environment": "diagnosing",
        "result": "revision_required",
        "evidence": "needs_decision",
    }
    target = routes[failure["class"]]
    run_core(
        root,
        "check-transition",
        str(root / STATE_RELATIVE),
        "--to",
        target,
        "--return-target",
        SOURCE_STATE,
    )
    write_json(
        root / STATE_RELATIVE,
        {"schema_version": SCHEMA_VERSION, "state": target, "return_target": SOURCE_STATE},
    )
    return target


def build_report(root, contract, full_report, claims, failure=None):
    report = {
        "schema_version": SCHEMA_VERSION,
        "stage": "evaluation",
        "status": "failed" if failure else "passed",
        "full_run_id": contract["full_run_id"],
        "evaluated_at": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
        "contract_sha256": canonical_hash(root / CONTRACT_RELATIVE),
        "full_run_report_sha256": canonical_hash(root / FULL_RUN_REPORT_RELATIVE.format(run_id=contract["full_run_id"])),
        "outcome": overall_outcome(claims) if claims else "inconclusive",
        "claims": claims,
        "failure": failure,
    }
    return report


def command_evaluate(root):
    root = root.resolve()
    state = read_state(root)
    if state.get("state") != SOURCE_STATE:
        raise ContractError(f"Evaluation requires state {SOURCE_STATE}, got {state.get('state')}")
    contract_result = run_core(root, "validate-evaluation", "--root", str(root))
    contract = load_json(root / CONTRACT_RELATIVE)
    if contract["full_run_id"] != contract_result["full_run_id"]:
        raise ContractError("Evaluation contract run_id differs from its validated Full Run")
    full_result = run_core(root, "validate-full-run-report", "--root", str(root), "--run-id", contract["full_run_id"])
    full_report = load_json(root / FULL_RUN_REPORT_RELATIVE.format(run_id=contract["full_run_id"]))
    bundle = load_json(root / f"runs/{contract['full_run_id']}/bundle.yaml")
    validations = validation_results(root)
    metrics = {item["id"]: item for item in contract["metrics"]}
    claims = []
    failure = None
    for claim in contract["claims"]:
        metric = metrics[claim["result"]["metric_id"]]
        implementation = implementation_assessment(claim, validations)
        execution = execution_assessment(claim, bundle, full_report)
        try:
            selected_seeds = execution["seeds"]
            result, _paths = result_assessment(
                root, contract["full_run_id"], claim, metric, full_report, selected_seeds
            )
            strength = evidence_strength(
                claim["evidence"]["provenance"],
                len(selected_seeds),
                claim["evidence"]["digitization_uncertainty"],
            )
            required = claim["evidence"]["minimum_strength"]
            missing_artifacts = []
            for relative in claim["evidence"]["required_artifacts"]:
                path = Path(relative)
                if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
                    missing_artifacts.append(relative)
            sufficient = STRENGTH_RANK[strength] >= STRENGTH_RANK[required] and not missing_artifacts
            evidence_message = ""
            if missing_artifacts:
                raise EvaluationFailure(
                    "evidence", claim["id"], "Missing required evidence artifacts: " + ", ".join(missing_artifacts)
                )
            if not sufficient:
                evidence_message = f"Observed Evidence Strength {strength} is below the preregistered minimum {required}"
            evidence = {
                "strength": strength,
                "minimum_strength": required,
                "sufficient": sufficient,
                "seed_count": len(selected_seeds),
                "message": evidence_message,
            }
            claims.append(claim_verdict(claim, implementation, execution, result, evidence))
        except EvaluationFailure as exc:
            if failure is None:
                failure = {
                    "class": exc.failure_class,
                    "id": exc.identifier,
                    "message": exc.message,
                    "state": {"evidence": "needs_decision", "result": "revision_required"}.get(exc.failure_class, "diagnosing"),
                    "return_target": SOURCE_STATE,
                }
            claims.append(failed_claim_assessment(claim, metric, implementation, execution, exc.message))

    if failure:
        report = build_report(root, contract, full_report, claims, failure)
        write_json(root / REPORT_RELATIVE, report)
        route_failure(root, failure)
        return {"stage": "paper-evaluation", "status": "failed", "state": failure["state"], "report": REPORT_RELATIVE, "failure": failure}

    report = build_report(root, contract, full_report, claims)
    write_json(root / REPORT_RELATIVE, report)
    run_core(root, "check-transition", str(root / STATE_RELATIVE), "--to", TARGET_STATE)
    write_json(
        root / STATE_RELATIVE,
        {"schema_version": SCHEMA_VERSION, "state": TARGET_STATE, "return_target": None},
    )
    return {
        "stage": "paper-evaluation",
        "status": "passed",
        "state": TARGET_STATE,
        "outcome": report["outcome"],
        "report": REPORT_RELATIVE,
        "full_run": full_result,
    }


def command_verify(root):
    root = root.resolve()
    state = read_state(root)
    if state.get("state") != TARGET_STATE:
        raise ContractError(f"Evaluation verification requires state {TARGET_STATE}, got {state.get('state')}")
    return run_core(root, "validate-evaluation-report", "--root", str(root))


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    evaluate = commands.add_parser("evaluate", help="evaluate the imported or local Full Run")
    evaluate.set_defaults(handler=lambda args: command_evaluate(args.root))
    verify = commands.add_parser("verify", help="verify the completed evaluation report")
    verify.set_defaults(handler=lambda args: command_verify(args.root))
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
    return 2 if isinstance(result, dict) and result.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
