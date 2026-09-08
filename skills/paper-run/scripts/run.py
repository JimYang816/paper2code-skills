#!/usr/bin/env python3
"""Prepare, approve, execute, and import portable Full Run bundles."""

import argparse
import datetime as _datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


SCHEMA_VERSION = "1.0"
CPU_STATE = "cpu_validated"
APPROVED_STATE = "full_run_approved"
COMPLETE_STATE = "full_run_complete"
STATE_RELATIVE = ".paper2code/state.yaml"
GATE_RELATIVE = ".paper2code/gates/full-run-gate.yaml"
CPU_REPORT_RELATIVE = "validation/reports/cpu-validation.yaml"
RUN_SCHEMA_RELATIVE = "skills/paper2code-core/references/schemas/v1/run.schema.json"
GATE_SCHEMA_RELATIVE = "skills/paper2code-core/references/schemas/v1/full-run-gate.schema.json"
REPORT_SCHEMA_RELATIVE = "skills/paper2code-core/references/schemas/v1/full-run-report.schema.json"
RECORD_PREFIXES = (
    ".paper2code/",
    "runs/",
    "validation/",
    "results/",
    "dossier/",
    "decisions/",
    "specification/",
    "contracts/",
    "paper/",
    "prototypes/",
)


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


def find_run_id(root, requested=None):
    if requested:
        return requested
    bundles = sorted((root / "runs").glob("*/bundle.yaml"))
    if len(bundles) != 1:
        if not bundles:
            raise ContractError("Missing runs/<run-id>/bundle.yaml")
        raise ContractError("Multiple Full Run bundles found; pass --run-id")
    return bundles[0].parent.name


def bundle(root, run_id):
    path = root / "runs" / run_id / "bundle.yaml"
    return path, load_json(path)


def code_snapshot(root):
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.PIPE,
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=root,
            text=True,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ContractError(f"Cannot resolve the repository code revision: {exc}") from exc
    dirty_paths = []
    for line in status.splitlines():
        relative = line[3:].strip()
        if " -> " in relative:
            relative = relative.split(" -> ", 1)[-1]
        if relative and not relative.replace("\\", "/").startswith(RECORD_PREFIXES):
            dirty_paths.append(relative)
    return {"revision": revision, "dirty": bool(dirty_paths), "dirty_paths": dirty_paths}


def verify_code_snapshot(root, bundle_value, gate=None):
    snapshot = code_snapshot(root)
    declared = bundle_value["code_revision"]
    if declared["revision"] != "HEAD" and declared["revision"] != snapshot["revision"]:
        raise ContractError("Full Run bundle code revision differs from the current checkout")
    if declared["dirty"] or snapshot["dirty"]:
        paths = ", ".join(snapshot["dirty_paths"]) or "declared dirty state"
        raise ContractError(f"Full Run requires a clean code checkout: {paths}")
    if gate and snapshot["revision"] != gate["code_revision"]:
        raise ContractError("stale Full Run approval: code revision changed")
    return snapshot


def verify_cpu_report(root):
    return run_core(root, "validate-cpu-report", "--root", str(root))


def validate_bundle(root, run_id):
    return run_core(root, "validate-run-bundle", "--root", str(root), "--run-id", run_id)


def verify_gate(root, run_id):
    result = run_core(root, "validate-full-run-gate", "--root", str(root))
    if result["run_id"] != run_id:
        raise ContractError("Full Run approval is for a different run")
    verify_cpu_report(root)
    gate = load_json(root / GATE_RELATIVE)
    return result, gate


def schema_hashes(root):
    return {
        "run": raw_hash(root / RUN_SCHEMA_RELATIVE),
        "gate": raw_hash(root / GATE_SCHEMA_RELATIVE),
        "report": raw_hash(root / REPORT_SCHEMA_RELATIVE),
    }


def check_capabilities(root, bundle_value, run_id):
    available = []
    missing = []
    for item in bundle_value["environment"]["capabilities"]:
        executable = item["executable"]
        resolved = sys.executable if executable == "{python}" else shutil.which(executable)
        entry = {"id": item["id"], "kind": item["kind"], "executable": executable}
        if resolved:
            entry["resolved"] = resolved
            available.append(entry)
        else:
            entry["reason"] = "executable is unavailable"
            missing.append(entry)

    for item in bundle_value["environment"]["dependencies"]:
        try:
            installed = importlib.metadata.version(item["name"])
        except importlib.metadata.PackageNotFoundError:
            installed = None
        entry = {"name": item["name"], "required": item["version"], "installed": installed}
        if installed == item["version"]:
            available.append(entry)
        else:
            entry["reason"] = "locked dependency is unavailable or has a different version"
            missing.append(entry)

    expected_python = bundle_value["environment"]["python_version"]
    actual_python = platform.python_version()
    if expected_python != actual_python:
        missing.append(
            {
                "id": "python-version",
                "required": expected_python,
                "installed": actual_python,
                "reason": "locked Python version differs",
            }
        )
    elif bundle_value["environment"]["platform"] != sys.platform:
        missing.append(
            {
                "id": "platform",
                "required": bundle_value["environment"]["platform"],
                "installed": sys.platform,
                "reason": "locked platform differs",
            }
        )

    report = {
        "schema_version": SCHEMA_VERSION,
        "stage": "full_run",
        "available": available,
        "missing": missing,
        "recovery_commands": [
            "Provide the declared executable or dependency in the approved environment, then rerun this capability check."
        ]
        if missing
        else [],
    }
    report_path = root / ".paper2code/capability-reports" / f"full-run-{run_id}.yaml"
    write_json(report_path, report)
    return report, report_path


def normalized_substitutions(run_id, seed):
    return {
        "{root}": ".",
        "{run_dir}": f"runs/{run_id}",
        "{seed}": str(seed),
        "{python}": "{python}",
        "{workers}": "1",
    }


def runtime_substitutions(root, run_id, seed):
    return {
        "{root}": str(root),
        "{run_dir}": str(root / "runs" / run_id),
        "{seed}": str(seed),
        "{python}": sys.executable,
        "{workers}": "1",
    }


def replace_tokens(value, substitutions):
    for token, replacement in substitutions.items():
        value = value.replace(token, replacement)
    return value


def relative_artifact(root, value):
    path = Path(value)
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ContractError(f"Full Run artifact escapes repository root: {value}") from exc


def write_report(root, run_id, gate, bundle_value, started_at, command_results, failure):
    report_path = root / "runs" / run_id / "report.yaml"
    artifacts = {}
    for result in command_results:
        for relative in [result["log"], *result["metrics"], *result["outputs"]]:
            artifact = root / relative
            if artifact.is_file():
                artifacts[relative] = raw_hash(artifact)
    report = {
        "schema_version": SCHEMA_VERSION,
        "stage": "full_run",
        "status": "failed" if failure else "passed",
        "execution_mode": "local",
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
        "bundle_sha256": canonical_hash(root / "runs" / run_id / "bundle.yaml"),
        "approval_sha256": canonical_hash(root / GATE_RELATIVE),
        "code_revision": gate["code_revision"],
        "commands": command_results,
        "artifacts": artifacts,
        "failure": failure,
    }
    write_json(report_path, report)
    return report, report_path


def route_failure(root, failure):
    target_state = "needs_decision" if failure["class"] == "evidence" else "diagnosing"
    run_core(
        root,
        "check-transition",
        str(root / STATE_RELATIVE),
        "--to",
        target_state,
        "--return-target",
        APPROVED_STATE,
    )
    write_json(
        root / STATE_RELATIVE,
        {"schema_version": SCHEMA_VERSION, "state": target_state, "return_target": APPROVED_STATE},
    )


def command_prepare(root, run_id):
    state = read_state(root)
    if state.get("state") != CPU_STATE:
        raise ContractError(f"Full Run preparation requires state {CPU_STATE}, got {state.get('state')}")
    verify_cpu_report(root)
    result = validate_bundle(root, run_id)
    _, bundle_value = bundle(root, run_id)
    snapshot = verify_code_snapshot(root, bundle_value)
    return {
        "stage": "paper-run",
        "valid": True,
        "state": CPU_STATE,
        "run_id": run_id,
        "bundle_sha256": result["bundle_sha256"],
        "code_revision": snapshot["revision"],
        "commands": result["commands"],
    }


def command_approve(root, run_id, approver):
    if not approver:
        raise ContractError("--approver is required for a researcher-approved Full Run Gate")
    state = read_state(root)
    if state.get("state") != CPU_STATE:
        raise ContractError(f"Full Run approval requires state {CPU_STATE}, got {state.get('state')}")
    verify_cpu_report(root)
    bundle_path, bundle_value = bundle(root, run_id)
    if bundle_value.get("status") not in ("prepared", "approved"):
        raise ContractError("Full Run bundle is not in an approvable state")
    bundle_value["status"] = "approved"
    write_json(bundle_path, bundle_value)
    result = validate_bundle(root, run_id)
    _, bundle_value = bundle(root, run_id)
    snapshot = verify_code_snapshot(root, bundle_value)
    run_core(root, "check-transition", str(root / STATE_RELATIVE), "--to", APPROVED_STATE)
    gate = {
        "schema_version": SCHEMA_VERSION,
        "gate": "full_run",
        "transition": f"{CPU_STATE} -> {APPROVED_STATE}",
        "approved_at": _datetime.datetime.now(_datetime.timezone.utc).isoformat(),
        "approved_by": approver,
        "run_id": run_id,
        "bundle_path": result["bundle_path"],
        "bundle_sha256": result["bundle_sha256"],
        "cpu_validation_report_path": CPU_REPORT_RELATIVE,
        "cpu_validation_report_sha256": canonical_hash(root / CPU_REPORT_RELATIVE),
        "code_revision": snapshot["revision"],
        "schemas": schema_hashes(root),
    }
    write_json(root / GATE_RELATIVE, gate)
    write_json(
        root / STATE_RELATIVE,
        {"schema_version": SCHEMA_VERSION, "state": APPROVED_STATE, "return_target": None},
    )
    return {
        "stage": "paper-run",
        "state": APPROVED_STATE,
        "gate": GATE_RELATIVE,
        "run_id": run_id,
        "approved_by": approver,
        "bundle_sha256": gate["bundle_sha256"],
        "code_revision": gate["code_revision"],
    }


def command_execute(root, run_id):
    state = read_state(root)
    if state.get("state") != APPROVED_STATE:
        raise ContractError(f"Full Run execution requires state {APPROVED_STATE}, got {state.get('state')}")
    _gate_result, gate = verify_gate(root, run_id)
    validate_result = validate_bundle(root, run_id)
    _bundle_path, bundle_value = bundle(root, run_id)
    verify_code_snapshot(root, bundle_value, gate)
    capability_report, capability_path = check_capabilities(root, bundle_value, run_id)
    if capability_report["missing"]:
        missing = ", ".join(
            item.get("executable", item.get("name", item.get("id", "unknown")))
            for item in capability_report["missing"]
        )
        raise ContractError(
            f"Missing Full Run capabilities: {missing}; report written to {capability_path}"
        )

    started_at = _datetime.datetime.now(_datetime.timezone.utc).isoformat()
    command_results = []
    first_failure = None
    environment = os.environ.copy()
    environment.update(
        {
            "PAPER2CODE_DEVICE": "cpu",
            "PAPER2CODE_WORKERS": "1",
            "PAPER2CODE_RUN_ID": run_id,
            "CUDA_VISIBLE_DEVICES": "",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
    )
    for command_spec in bundle_value["commands"]:
        for seed in bundle_value["seeds"]:
            runtime = runtime_substitutions(root, run_id, seed)
            portable = normalized_substitutions(run_id, seed)
            command = [replace_tokens(token, runtime) for token in command_spec["command"]]
            normalized_command = [replace_tokens(token, portable) for token in command_spec["command"]]
            log = relative_artifact(root, replace_tokens(command_spec["log"], runtime))
            metrics = [relative_artifact(root, replace_tokens(item, runtime)) for item in command_spec["metrics"]]
            outputs = [relative_artifact(root, replace_tokens(item, runtime)) for item in command_spec["outputs"]]
            run_environment = dict(environment)
            run_environment["PAPER2CODE_SEED"] = str(seed)
            try:
                completed = subprocess.run(
                    command,
                    cwd=root,
                    env=run_environment,
                    text=True,
                    capture_output=True,
                )
                exit_code = completed.returncode
                message = completed.stderr.strip() or ("command failed" if exit_code else "")
                output = completed.stdout
                if completed.stderr:
                    output += "\n[stderr]\n" + completed.stderr
            except (FileNotFoundError, PermissionError, OSError) as exc:
                exit_code = None
                message = str(exc)
                output = ""
            log_path = root / log
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(output, encoding="utf-8")
            missing = [path for path in [*metrics, *outputs] if not (root / path).is_file()]
            failure_class = None
            if exit_code not in (0, None):
                failure_class = command_spec["failure_class"]
                message = message or f"command exited with code {exit_code}"
            elif exit_code is None:
                failure_class = "environment"
            elif missing:
                failure_class = "evidence"
                message = "Missing declared artifacts: " + ", ".join(missing)
            result = {
                "id": command_spec["id"],
                "seed": seed,
                "status": "failed" if failure_class else "passed",
                "command": normalized_command,
                "log": log,
                "metrics": metrics,
                "outputs": outputs,
                "exit_code": exit_code,
                "message": message,
            }
            command_results.append(result)
            if first_failure is None and failure_class:
                first_failure = {
                    "class": failure_class,
                    "id": command_spec["id"],
                    "message": message or "Full Run command failed",
                    "state": "needs_decision" if failure_class == "evidence" else "diagnosing",
                    "return_target": APPROVED_STATE,
                }

    report, report_path = write_report(
        root, run_id, gate, bundle_value, started_at, command_results, first_failure
    )
    if first_failure:
        route_failure(root, first_failure)
        return {"stage": "paper-run", "status": "failed", "state": first_failure["state"], "report": str(report_path.relative_to(root)), "failure": first_failure}

    run_core(root, "check-transition", str(root / STATE_RELATIVE), "--to", COMPLETE_STATE)
    write_json(
        root / STATE_RELATIVE,
        {"schema_version": SCHEMA_VERSION, "state": COMPLETE_STATE, "return_target": None},
    )
    return {
        "stage": "paper-run",
        "status": report["status"],
        "state": COMPLETE_STATE,
        "run_id": run_id,
        "report": str(report_path.relative_to(root)),
        "artifacts": sorted(report["artifacts"]),
        "validated_bundle": validate_result["bundle_sha256"],
    }


def command_import(root, run_id):
    state = read_state(root)
    if state.get("state") != APPROVED_STATE:
        raise ContractError(f"Full Run import requires state {APPROVED_STATE}, got {state.get('state')}")
    verify_gate(root, run_id)
    result = run_core(root, "validate-full-run-report", "--root", str(root), "--run-id", run_id)
    run_core(root, "check-transition", str(root / STATE_RELATIVE), "--to", COMPLETE_STATE)
    write_json(
        root / STATE_RELATIVE,
        {"schema_version": SCHEMA_VERSION, "state": COMPLETE_STATE, "return_target": None},
    )
    return {"stage": "paper-run", "status": result["status"], "execution_mode": "imported", "state": COMPLETE_STATE, "run_id": run_id}


def command_verify(root, run_id):
    state = read_state(root)
    if state.get("state") != COMPLETE_STATE:
        raise ContractError(f"Full Run verification requires state {COMPLETE_STATE}, got {state.get('state')}")
    return run_core(root, "validate-full-run-report", "--root", str(root), "--run-id", run_id)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--run-id")
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare", help="validate a Full Run bundle")
    prepare.set_defaults(handler=lambda args: command_prepare(args.root.resolve(), find_run_id(args.root.resolve(), args.run_id)))

    approve = commands.add_parser("approve", help="record the Full Run approval gate")
    approve.add_argument("--approver", required=True)
    approve.set_defaults(handler=lambda args: command_approve(args.root.resolve(), find_run_id(args.root.resolve(), args.run_id), args.approver))

    execute = commands.add_parser("execute", help="execute a locally approved Full Run")
    execute.set_defaults(handler=lambda args: command_execute(args.root.resolve(), find_run_id(args.root.resolve(), args.run_id)))

    imported = commands.add_parser("import", help="validate an externally returned Full Run")
    imported.set_defaults(handler=lambda args: command_import(args.root.resolve(), find_run_id(args.root.resolve(), args.run_id)))

    verify = commands.add_parser("verify", help="verify a completed Full Run")
    verify.set_defaults(handler=lambda args: command_verify(args.root.resolve(), find_run_id(args.root.resolve(), args.run_id)))
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        result = args.handler(args)
    except (ContractError, OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 2 if result.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
