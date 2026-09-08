"""Shared deterministic claim-evaluation calculations."""

import hashlib
import json
import math
from pathlib import Path


STRENGTH_RANK = {"low": 0, "moderate": 1, "high": 2}


class EvaluationFailure(ValueError):
    def __init__(self, failure_class, identifier, message):
        super().__init__(message)
        self.failure_class = failure_class
        self.identifier = identifier
        self.message = message


def load_document(path):
    return json.loads(path.read_text(encoding="utf-8"))


def raw_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def evidence_strength(
    provenance,
    seed_count,
    independent_seeds,
    digitization_uncertainty,
    standard_deviation,
    target,
    validation_coverage,
):
    if seed_count >= 3 and independent_seeds:
        strength = "high"
    elif seed_count >= 2:
        strength = "moderate"
    else:
        strength = "low"
    if provenance in {"reconstructed", "derived", "empirical", "excluded"}:
        strength = min(strength, "moderate", key=lambda value: STRENGTH_RANK[value])
    if digitization_uncertainty > 0:
        strength = min(strength, "moderate", key=lambda value: STRENGTH_RANK[value])
    if validation_coverage < 1:
        strength = min(strength, "moderate", key=lambda value: STRENGTH_RANK[value])
    if standard_deviation is not None:
        variability_scale = max(abs(target), 1.0)
        variability_ratio = standard_deviation / variability_scale
        if variability_ratio > 1:
            strength = "low"
        elif variability_ratio > 0.5:
            strength = min(strength, "moderate", key=lambda value: STRENGTH_RANK[value])
    return strength


def validation_results(root):
    report = load_document(root / "validation/reports/cpu-validation.yaml")
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
            value = json_pointer(load_document(path), metric["json_pointer"])
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
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
            "standard_deviation": None,
            "max_standard_deviation": metric.get("max_standard_deviation"),
            "message": "No successful metric values were available",
        }, paths
    try:
        observed = aggregate(values, metric["aggregation"])
    except ValueError as exc:
        raise EvaluationFailure("evidence", claim["id"], str(exc)) from exc
    standard_deviation = math.sqrt(sum((value - observed) ** 2 for value in values) / len(values))
    agreed = compare(observed, metric, claim["evidence"]["digitization_uncertainty"])
    return {
        "status": "passed" if agreed else "failed",
        "metric_id": metric["id"],
        "observed": observed,
        "target": metric["target"],
        "tolerance": metric["tolerance"],
        "standard_deviation": standard_deviation,
        "max_standard_deviation": metric.get("max_standard_deviation"),
        "message": "" if agreed else "Observed value is outside the preregistered tolerance",
    }, paths


def claim_verdict(claim, implementation, execution, result, evidence):
    if implementation["status"] != "passed" or execution["status"] != "passed" or not evidence["sufficient"]:
        verdict = "inconclusive"
    elif result["status"] == "passed":
        verdict = "replicated"
    elif (
        result["status"] == "failed"
        and evidence["seed_count"] >= 2
        and claim["execution"]["independent_seeds"]
        and evidence["strength"] != "low"
    ):
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


def failed_claim_assessment(claim, metric, implementation, execution, message, validation_coverage=0):
    selected_seeds = execution["seeds"]
    strength = evidence_strength(
        claim["evidence"]["provenance"],
        len(selected_seeds),
        claim["execution"]["independent_seeds"],
        claim["evidence"]["digitization_uncertainty"],
        None,
        metric["target"],
        validation_coverage,
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
            "standard_deviation": None,
            "max_standard_deviation": metric.get("max_standard_deviation"),
            "message": message,
        },
        {
            "strength": strength,
            "minimum_strength": claim["evidence"]["minimum_strength"],
            "sufficient": False,
            "seed_count": len(selected_seeds),
            "validation_coverage": validation_coverage,
            "message": message,
        },
    )


def validation_coverage(claim, validations):
    identifiers = claim["implementation"]["validation_ids"]
    if not identifiers:
        return 0
    passed = sum(1 for identifier in identifiers if validations.get(identifier, {}).get("status") == "passed")
    return passed / len(identifiers)


def check_digitization_evidence(root, claim):
    evidence = claim["evidence"]
    uncertainty = evidence["digitization_uncertainty"]
    requires_record = uncertainty > 0 or evidence["provenance"] == "paper"
    record = evidence.get("digitization_record")
    record_hash = evidence.get("digitization_record_sha256")
    if requires_record and (not record or not evidence.get("independent_cross_check", False)):
        raise EvaluationFailure(
            "evidence",
            claim["id"],
            "Paper or uncertain evidence requires a digitization record and an independent cross-check",
        )
    if record:
        path = Path(record)
        if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
            raise EvaluationFailure("evidence", claim["id"], f"Missing digitization record: {record}")
        if not record_hash or raw_hash(root / path) != record_hash:
            raise EvaluationFailure("evidence", claim["id"], f"Stale or unbound digitization record: {record}")


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


def evaluate_claims(root, contract, full_report, bundle, validations):
    metrics = {item["id"]: item for item in contract["metrics"]}
    claims = []
    failure = None
    for claim in contract["claims"]:
        metric = metrics[claim["result"]["metric_id"]]
        implementation = implementation_assessment(claim, validations)
        execution = execution_assessment(claim, bundle, full_report)
        coverage = validation_coverage(claim, validations)
        try:
            selected_seeds = execution["seeds"]
            check_digitization_evidence(root, claim)
            result, _paths = result_assessment(
                root, contract["full_run_id"], claim, metric, full_report, selected_seeds
            )
            strength = evidence_strength(
                claim["evidence"]["provenance"],
                len(selected_seeds),
                claim["execution"]["independent_seeds"],
                claim["evidence"]["digitization_uncertainty"],
                result["standard_deviation"],
                result["target"],
                coverage,
            )
            required = claim["evidence"]["minimum_strength"]
            missing_artifacts = []
            for artifact in claim["evidence"]["required_artifacts"]:
                relative = artifact["path"]
                path = Path(relative)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or not (root / path).is_file()
                    or raw_hash(root / path) != artifact["sha256"]
                ):
                    missing_artifacts.append(relative)
            sufficient = STRENGTH_RANK[strength] >= STRENGTH_RANK[required] and not missing_artifacts
            max_standard_deviation = result["max_standard_deviation"]
            if (
                max_standard_deviation is not None
                and result["standard_deviation"] is not None
                and result["standard_deviation"] > max_standard_deviation
            ):
                sufficient = False
                evidence_message = (
                    "Observed standard deviation exceeds the preregistered maximum "
                    f"{max_standard_deviation}"
                )
            else:
                evidence_message = ""
            if missing_artifacts:
                raise EvaluationFailure(
                    "evidence", claim["id"], "Missing or stale required evidence artifacts: " + ", ".join(missing_artifacts)
                )
            if not sufficient and not evidence_message:
                evidence_message = f"Observed Evidence Strength {strength} is below the preregistered minimum {required}"
            evidence = {
                "strength": strength,
                "minimum_strength": required,
                "sufficient": sufficient,
                "seed_count": len(selected_seeds),
                "validation_coverage": coverage,
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
                    "return_target": "full_run_complete",
                }
            claims.append(failed_claim_assessment(claim, metric, implementation, execution, exc.message, coverage))

    if failure is None:
        failed_dimensions = [
            claim
            for claim in claims
            if claim["implementation"]["status"] == "failed"
            or claim["execution"]["status"] == "failed"
        ]
        if failed_dimensions:
            failed_claim = failed_dimensions[0]
            dimension = (
                "implementation"
                if failed_claim["implementation"]["status"] == "failed"
                else "execution"
            )
            failure = {
                "class": "software",
                "id": failed_claim["id"],
                "message": f"Claim {failed_claim['id']} has a failed {dimension} assessment",
                "state": "diagnosing",
                "return_target": "full_run_complete",
            }

    if failure is None:
        mismatches = [claim for claim in claims if claim["scope"] == "must" and claim["verdict"] == "not replicated"]
        if mismatches:
            failure = {
                "class": "result",
                "id": mismatches[0]["id"],
                "message": f"Claim {mismatches[0]['id']} does not agree with the preregistered result target",
                "state": "revision_required",
                "return_target": "full_run_complete",
            }
    return claims, failure
