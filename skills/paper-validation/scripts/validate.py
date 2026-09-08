#!/usr/bin/env python3
"""Run the independent numerical reference and deterministic CPU Validation Gate."""

import argparse
import datetime as _datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


SCHEMA_VERSION = "1.0"
SOURCE_STATE = "implementation_active"
TARGET_STATE = "cpu_validated"
REPORT_RELATIVE = "validation/reports/cpu-validation.yaml"
ROUTES = {
    "software": ("diagnosing", "implementation_active"),
    "scientific": ("diagnosing", "implementation_active"),
    "environment": ("diagnosing", "implementation_active"),
    "evidence": ("needs_decision", "implementation_active"),
}
CHECK_GROUPS = ("invariants", "units", "shapes", "gradients")


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
    command = [
        sys.executable,
        str(root / "skills/paper2code-core/scripts/paper2code.py"),
        *arguments,
    ]
    completed = subprocess.run(command, cwd=root, text=True, capture_output=True)
    if completed.returncode != 0:
        raise ContractError(completed.stderr.strip() or completed.stdout.strip())
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ContractError("Core validator returned invalid JSON") from exc


def read_state(root):
    path = root / ".paper2code/state.yaml"
    state = load_json(path)
    if state.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("Unsupported state schema version")
    return state


def expand_command(command, root, deterministic):
    substitutions = {
        "{python}": sys.executable,
        "{root}": str(root),
        "{seed}": str(deterministic["seed"]),
        "{workers}": str(deterministic["workers"]),
        "{device}": deterministic["device"],
    }
    return [
        _replace_token(token, substitutions)
        for token in command
    ]


def _replace_token(value, substitutions):
    for token, replacement in substitutions.items():
        value = value.replace(token, replacement)
    return value


def command_environment(deterministic):
    environment = os.environ.copy()
    environment.update(
        {
            "PAPER2CODE_DEVICE": deterministic["device"],
            "PAPER2CODE_SEED": str(deterministic["seed"]),
            "PAPER2CODE_WORKERS": str(deterministic["workers"]),
            "PYTHONHASHSEED": str(deterministic["seed"]),
            "CUDA_VISIBLE_DEVICES": "",
            "OMP_NUM_THREADS": str(deterministic["workers"]),
            "MKL_NUM_THREADS": str(deterministic["workers"]),
        }
    )
    return environment


def execute(command, root, deterministic):
    expanded = expand_command(command, root, deterministic)
    try:
        completed = subprocess.run(
            expanded,
            cwd=root,
            env=command_environment(deterministic),
            text=True,
            capture_output=True,
        )
    except (FileNotFoundError, PermissionError, OSError) as exc:
        return expanded, None, "environment", str(exc), ""
    return expanded, completed.returncode, None, completed.stderr.strip(), completed.stdout.strip()


def missing_artifacts(root, artifacts):
    return [relative for relative in artifacts if not (root / relative).is_file()]


def parse_reference_output(stdout, item):
    try:
        output = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ContractError(f"{item['id']} did not print JSON: {exc}") from exc
    if not isinstance(output, dict) or output.get("status") != "passed":
        raise ContractError(f"{item['id']} reference did not report status=passed")
    checks = output.get("checks")
    if not isinstance(checks, dict):
        raise ContractError(f"{item['id']} reference omitted checks")
    expected = item["checks"]
    for group in CHECK_GROUPS:
        required = set(expected[group])
        if not required:
            continue
        actual = checks.get(group)
        if not isinstance(actual, list) or not required <= set(actual):
            missing = sorted(required - set(actual or []))
            raise ContractError(f"{item['id']} missing {group} checks: {', '.join(missing)}")
    return checks, output.get("artifacts", [])


def result_template(identifier, command, artifacts):
    return {
        "id": identifier,
        "status": "failed",
        "command": command,
        "checks": {},
        "exit_code": None,
        "artifacts": list(artifacts),
        "message": "",
    }


def run_math(root, item, deterministic):
    command, exit_code, immediate_class, message, stdout = execute(
        item["command"], root, deterministic
    )
    result = result_template(item["id"], command, [])
    result["exit_code"] = exit_code
    if immediate_class:
        result["message"] = message
        return result, immediate_class
    if exit_code != 0:
        result["message"] = message or f"reference exited with code {exit_code}"
        return result, "scientific"
    try:
        checks, artifacts = parse_reference_output(stdout, item)
    except ContractError as exc:
        result["message"] = str(exc)
        return result, "scientific"
    missing = missing_artifacts(root, artifacts)
    if missing:
        result["artifacts"] = artifacts
        result["message"] = "Missing reference artifacts: " + ", ".join(missing)
        return result, "evidence"
    result.update({"status": "passed", "checks": checks, "artifacts": artifacts, "message": ""})
    return result, None


def run_path(root, item, deterministic):
    command, exit_code, immediate_class, message, _stdout = execute(
        item["command"], root, deterministic
    )
    result = result_template(item["id"], command, item["artifacts"])
    result.pop("checks")
    result["kind"] = item["kind"]
    result["exit_code"] = exit_code
    if immediate_class:
        result["message"] = message
        return result, immediate_class
    if exit_code != 0:
        result["message"] = message or f"path exited with code {exit_code}"
        return result, item["failure_class"]
    missing = missing_artifacts(root, item["artifacts"])
    if missing:
        result["message"] = "Missing path artifacts: " + ", ".join(missing)
        return result, "evidence"
    result.update({"status": "passed", "message": ""})
    return result, None


def state_transition(root, target, return_target=None):
    command = [
        sys.executable,
        str(root / "skills/paper2code-core/scripts/paper2code.py"),
        "check-transition",
        str(root / ".paper2code/state.yaml"),
        "--to",
        target,
    ]
    if return_target:
        command.extend(["--return-target", return_target])
    completed = subprocess.run(command, cwd=root, text=True, capture_output=True)
    if completed.returncode != 0:
        raise ContractError(completed.stderr.strip() or completed.stdout.strip())


def route_failure(root, failure_class):
    state, return_target = ROUTES[failure_class]
    state_transition(root, state, return_target)
    write_json(
        root / ".paper2code/state.yaml",
        {"schema_version": SCHEMA_VERSION, "state": state, "return_target": return_target},
    )
    return state, return_target


def validate_specification_if_present(root):
    specification = root / "specification/specification.yaml"
    if not specification.is_file():
        return None
    gate = root / ".paper2code/gates/specification-gate.yaml"
    script = root / "skills/paper-spec/scripts/spec.py"
    if not gate.is_file() or not script.is_file():
        raise ContractError("evidence: specification exists without a verifiable Specification Gate")
    completed = subprocess.run(
        [sys.executable, str(script), "--root", str(root), "verify-gate"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ContractError("evidence: stale or invalid Specification Gate")
    return json.loads(completed.stdout)


def command_validate(root):
    root = root.resolve()
    state = read_state(root)
    contract = run_core(root, "validate-cpu-contract", "--root", str(root))
    validate_specification_if_present(root)
    return {"stage": "paper-validation", "valid": True, "state": state["state"], "contract": contract}


def command_run(root):
    root = root.resolve()
    state = read_state(root)
    if state.get("state") != SOURCE_STATE:
        raise ContractError(
            f"CPU Validation requires state {SOURCE_STATE}, got {state.get('state')}"
        )
    validate_specification_if_present(root)
    run_core(root, "validate-cpu-contract", "--root", str(root))
    contract = load_json(root / "validation/validation.yaml")
    deterministic = contract["deterministic"]
    started_at = _datetime.datetime.now(_datetime.timezone.utc).isoformat()
    math_results = []
    path_results = []
    first_failure = None

    for item in contract["critical_math"]:
        result, failure_class = run_math(root, item, deterministic)
        math_results.append(result)
        if first_failure is None and failure_class:
            first_failure = (failure_class, item["id"], result["message"])

    for item in contract["paths"]:
        result, failure_class = run_path(root, item, deterministic)
        path_results.append(result)
        if first_failure is None and failure_class:
            first_failure = (failure_class, item["id"], result["message"])

    if first_failure is None:
        target_state, return_target = TARGET_STATE, None
        failure = None
        status = "passed"
    else:
        failure_class, identifier, message = first_failure
        target_state, return_target = ROUTES[failure_class]
        failure = {
            "class": failure_class,
            "id": identifier,
            "message": message or "Validation command failed",
            "state": target_state,
            "return_target": return_target,
        }
        status = "failed"

    artifacts = sorted(
        {
            artifact
            for result in [*math_results, *path_results]
            for artifact in result["artifacts"]
            if (root / artifact).is_file()
        }
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "stage": "cpu_validation",
        "status": status,
        "started_at": started_at,
        "completed_at": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
        "state": target_state,
        "return_target": return_target,
        "deterministic": deterministic,
        "contract_sha256": canonical_hash(root / "validation/validation.yaml"),
        "math": math_results,
        "paths": path_results,
        "failure": failure,
        "artifacts": {relative: hashlib.sha256((root / relative).read_bytes()).hexdigest() for relative in artifacts},
    }
    write_json(root / REPORT_RELATIVE, report)

    if first_failure is None:
        state_transition(root, TARGET_STATE)
        write_json(
            root / ".paper2code/state.yaml",
            {"schema_version": SCHEMA_VERSION, "state": TARGET_STATE, "return_target": None},
        )
    else:
        route_failure(root, first_failure[0])
    return report


def command_verify(root):
    root = root.resolve()
    state = read_state(root)
    if state.get("state") != TARGET_STATE:
        raise ContractError(f"CPU Validation Gate requires state {TARGET_STATE}, got {state.get('state')}")
    report = run_core(root, "validate-cpu-report", "--root", str(root))
    return {"stage": "paper-validation", "valid": True, "state": state["state"], "report": report}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="validate the CPU Validation contract")
    validate.set_defaults(handler=lambda args: command_validate(args.root))

    run = commands.add_parser("run", help="run the CPU Validation Gate")
    run.set_defaults(handler=lambda args: command_run(args.root))

    verify = commands.add_parser("verify", help="verify the completed CPU Validation Gate")
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
