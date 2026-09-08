#!/usr/bin/env python3
"""Evaluate a validated Full Run against a frozen claim contract."""

import argparse
import datetime as _datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys


CORE_SCRIPTS = Path(__file__).resolve().parents[2] / "paper2code-core" / "scripts"
if str(CORE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(CORE_SCRIPTS))
from evaluation_engine import evaluate_claims
from evaluation_engine import overall_outcome
from evaluation_engine import validation_results


SCHEMA_VERSION = "1.0"
SOURCE_STATE = "full_run_complete"
TARGET_STATE = "evaluated"
CONTRACT_RELATIVE = "results/evaluation.yaml"
REPORT_RELATIVE = "results/evaluation-report.yaml"
FULL_RUN_REPORT_RELATIVE = "runs/{run_id}/report.yaml"
STATE_RELATIVE = ".paper2code/state.yaml"


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
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ContractError("Core validator returned invalid JSON") from exc


def read_state(root):
    state = load_json(root / STATE_RELATIVE)
    if state.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("Unsupported state schema version")
    return state


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


def build_report(root, contract, claims, failure=None):
    return {
        "schema_version": SCHEMA_VERSION,
        "stage": "evaluation",
        "status": "failed" if failure else "passed",
        "full_run_id": contract["full_run_id"],
        "evaluated_at": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
        "contract_sha256": canonical_hash(root / CONTRACT_RELATIVE),
        "full_run_report_sha256": canonical_hash(
            root / FULL_RUN_REPORT_RELATIVE.format(run_id=contract["full_run_id"])
        ),
        "outcome": overall_outcome(claims) if claims else "inconclusive",
        "claims": claims,
        "failure": failure,
    }


def command_evaluate(root):
    root = root.resolve()
    state = read_state(root)
    if state.get("state") != SOURCE_STATE:
        raise ContractError(f"Evaluation requires state {SOURCE_STATE}, got {state.get('state')}")
    contract_result = run_core(root, "validate-evaluation", "--root", str(root))
    contract = load_json(root / CONTRACT_RELATIVE)
    if contract["full_run_id"] != contract_result["full_run_id"]:
        raise ContractError("Evaluation contract run_id differs from its validated Full Run")
    full_result = run_core(
        root,
        "validate-full-run-report",
        "--root",
        str(root),
        "--run-id",
        contract["full_run_id"],
    )
    full_report = load_json(root / FULL_RUN_REPORT_RELATIVE.format(run_id=contract["full_run_id"]))
    if not full_result.get("evaluation_contract_sha256"):
        raise ContractError("Evaluation contract must be preregistered before Full Run approval")
    if full_result["status"] != "passed":
        recorded_failure = full_report.get("failure")
        if not recorded_failure:
            raise ContractError("Failed Full Run report must classify a failure")
        failure = {
            **recorded_failure,
            "state": {"result": "revision_required", "evidence": "needs_decision"}.get(
                recorded_failure["class"], "diagnosing"
            ),
            "return_target": SOURCE_STATE,
        }
        route_failure(root, failure)
        return {
            "stage": "paper-evaluation",
            "status": "failed",
            "state": failure["state"],
            "outcome": "inconclusive",
            "source_report": FULL_RUN_REPORT_RELATIVE.format(run_id=contract["full_run_id"]),
            "failure": failure,
        }

    bundle = load_json(root / f"runs/{contract['full_run_id']}/bundle.yaml")
    claims, failure = evaluate_claims(root, contract, full_report, bundle, validation_results(root))
    if failure:
        report = build_report(root, contract, claims, failure)
        write_json(root / REPORT_RELATIVE, report)
        route_failure(root, failure)
        return {
            "stage": "paper-evaluation",
            "status": "failed",
            "state": failure["state"],
            "outcome": report["outcome"],
            "report": REPORT_RELATIVE,
            "failure": failure,
        }

    report = build_report(root, contract, claims)
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
    if state.get("state") not in {TARGET_STATE, "diagnosing", "needs_decision", "revision_required"}:
        raise ContractError(f"Evaluation verification requires a completed evaluation, got {state.get('state')}")
    validation_result = run_core(root, "validate-evaluation-report", "--root", str(root))
    contract = load_json(root / CONTRACT_RELATIVE)
    full_report = load_json(root / FULL_RUN_REPORT_RELATIVE.format(run_id=contract["full_run_id"]))
    bundle = load_json(root / f"runs/{contract['full_run_id']}/bundle.yaml")
    claims, failure = evaluate_claims(root, contract, full_report, bundle, validation_results(root))
    expected = build_report(root, contract, claims, failure)
    actual = load_json(root / REPORT_RELATIVE)
    expected.pop("evaluated_at")
    actual.pop("evaluated_at", None)
    if actual != expected:
        raise ContractError("Evaluation report verdicts do not match the Full Run evidence")
    return validation_result


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
