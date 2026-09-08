"""Exercise portable Full Run preparation, approval, execution, and import."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from _tmp import TempDirectory


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "skills/setup-paper2code/scripts/setup.py"
VALIDATION = ROOT / "skills/paper-validation/scripts/validate.py"
RUN = ROOT / "skills/paper-run/scripts/run.py"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def make_cpu_contract(target):
    command = ["{python}", "{root}/validation/fixture.py"]
    paths = []
    for kind in ("data", "model", "baseline", "metric", "reporting"):
        paths.append(
            {
                "id": f"PATH-{len(paths) + 1:04d}",
                "kind": kind,
                "title": f"Reduced CPU {kind} path",
                "command": [*command, "--path", kind],
                "failure_class": "software",
                "artifacts": [],
            }
        )
    contract = {
        "schema_version": "1.0",
        "stage": "cpu_validation",
        "deterministic": {"seed": 7, "device": "cpu", "workers": 1},
        "critical_math": [
            {
                "id": "MATH-0001",
                "title": "Known fixture transform",
                "reference": "validation/references/reference.py",
                "command": [*command, "--math"],
                "checks": {
                    "invariants": ["INV-0001"],
                    "units": ["UNIT-0001"],
                    "shapes": ["SHAPE-0001"],
                    "gradients": ["GRAD-0001"],
                    "not_applicable": [],
                },
            }
        ],
        "paths": paths,
    }
    write_json(target / "validation/validation.yaml", contract)
    (target / "validation/references/reference.py").parent.mkdir(parents=True, exist_ok=True)
    (target / "validation/references/reference.py").write_text(
        "# independent reference\n", encoding="utf-8"
    )
    (target / "validation/fixture.py").write_text(
        "import argparse, json\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--math', action='store_true')\n"
        "parser.add_argument('--path')\n"
        "args = parser.parse_args()\n"
        "if args.math:\n"
        "    print(json.dumps({'status': 'passed', 'checks': {\n"
        "        'invariants': ['INV-0001'], 'units': ['UNIT-0001'],\n"
        "        'shapes': ['SHAPE-0001'], 'gradients': ['GRAD-0001']}}))\n",
        encoding="utf-8",
    )


def make_bundle(target, capability="{python}", revision=None):
    dataset = target / "runs/fixture/datasets/input.json"
    dataset.parent.mkdir(parents=True, exist_ok=True)
    dataset.write_text('{"value": 3}\n', encoding="utf-8")
    dataset_hash = __import__("hashlib").sha256(dataset.read_bytes()).hexdigest()
    fixture = target / "runs/fixture/fixture.py"
    fixture.write_text(
        "import argparse, json, pathlib\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--seed', type=int, required=True)\n"
        "parser.add_argument('--output', required=True)\n"
        "parser.add_argument('--metric', required=True)\n"
        "args = parser.parse_args()\n"
        "pathlib.Path(args.output).parent.mkdir(parents=True, exist_ok=True)\n"
        "pathlib.Path(args.metric).parent.mkdir(parents=True, exist_ok=True)\n"
        "pathlib.Path(args.output).write_text(json.dumps({'seed': args.seed}))\n"
        "pathlib.Path(args.metric).write_text(json.dumps({'score': args.seed * 2}))\n"
        "print(json.dumps({'seed': args.seed, 'status': 'passed'}))\n",
        encoding="utf-8",
    )
    bundle = {
        "schema_version": "1.0",
        "stage": "full_run",
        "run_id": "fixture",
        "status": "prepared",
        "resolved_config": {
            "experiment": "portable-fixture",
            "execution": {"device": "cpu", "workers": 1},
        },
        "code_revision": {"revision": revision, "dirty": False},
        "environment": {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "platform": sys.platform,
            "dependencies": [],
            "capabilities": [
                {"id": "python", "kind": "executable", "executable": capability}
            ],
        },
        "datasets": [
            {
                "id": "DATA-0001",
                "path": "runs/fixture/datasets/input.json",
                "source": "local deterministic fixture",
                "license": "MIT",
                "sha256": dataset_hash,
                "manifest": {
                    "expected_files": [{"path": "runs/fixture/datasets/input.json", "sha256": dataset_hash}],
                    "preparation_recipe": "Write the deterministic JSON fixture.",
                },
            }
        ],
        "seeds": [3, 5, 7],
        "commands": [
            {
                "id": "CMD-0001",
                "title": "Execute the fixture",
                "command": [
                    "{python}",
                    "{run_dir}/fixture.py",
                    "--seed",
                    "{seed}",
                    "--output",
                    "{run_dir}/outputs/result-{seed}.json",
                    "--metric",
                    "{run_dir}/metrics/metric-{seed}.json",
                ],
                "log": "{run_dir}/logs/seed-{seed}.log",
                "metrics": ["{run_dir}/metrics/metric-{seed}.json"],
                "outputs": ["{run_dir}/outputs/result-{seed}.json"],
                "failure_class": "software",
            }
        ],
    }
    write_json(target / "runs/fixture/bundle.yaml", bundle)


def make_evaluation_contract(target):
    write_json(
        target / "results/evaluation.yaml",
        {
            "schema_version": "1.0",
            "stage": "evaluation",
            "status": "preregistered",
            "full_run_id": "fixture",
            "preregistered_at": "2026-01-01T00:00:00+00:00",
            "preregistered_by": "researcher@example.com",
            "claims": [
                {
                    "id": "CLM-0001",
                    "title": "Fixture score",
                    "scope": "must",
                    "implementation": {"validation_ids": ["PATH-0001"]},
                    "execution": {
                        "command_ids": ["CMD-0001"],
                        "independent_seeds": True,
                    },
                    "result": {"metric_id": "MET-0001"},
                    "evidence": {
                        "provenance": "source-faithful",
                        "minimum_strength": "low",
                        "required_artifacts": [],
                        "digitization_uncertainty": 0,
                    },
                }
            ],
            "metrics": [
                {
                    "id": "MET-0001",
                    "title": "Fixture score",
                    "path": "{run_dir}/metrics/metric-{seed}.json",
                    "json_pointer": "/score",
                    "aggregation": "mean",
                    "target": 10,
                    "tolerance": 0,
                    "comparison": "within",
                }
            ],
        },
    )


class FullRunTests(unittest.TestCase):
    def scaffold(self, capability="{python}"):
        temp = TempDirectory()
        self.addCleanup(temp.cleanup)
        target = Path(temp.name) / "paper"
        completed = subprocess.run(
            [
                sys.executable,
                str(SETUP),
                "--target",
                str(target),
                "--bundle-root",
                str(ROOT),
                "--apply",
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
        make_cpu_contract(target)
        write_json(
            target / ".paper2code/state.yaml",
            {"schema_version": "1.0", "state": "implementation_active", "return_target": None},
        )
        completed = subprocess.run(
            [sys.executable, str(VALIDATION), "--root", str(target), "run"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
        (target / "implementation.py").write_text("# committed implementation\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(target), "config", "user.email", "fixture@example.com"], check=True)
        subprocess.run(["git", "-C", str(target), "config", "user.name", "Fixture"], check=True)
        subprocess.run(["git", "-C", str(target), "add", "."], check=True)
        subprocess.run(["git", "-C", str(target), "commit", "-m", "fixture"], check=True, capture_output=True)
        revision = subprocess.check_output(["git", "-C", str(target), "rev-parse", "HEAD"], text=True).strip()
        make_bundle(target, capability, revision)
        make_evaluation_contract(target)
        return target

    def run_tool(self, target, *args, expected=0):
        completed = subprocess.run(
            [sys.executable, str(RUN), "--root", str(target), *map(str, args)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(expected, completed.returncode, completed.stderr or completed.stdout)
        return json.loads(completed.stdout) if completed.stdout.strip() else {}

    def test_prepare_and_approve_bind_bundle_and_cpu_report(self):
        target = self.scaffold()

        prepared = self.run_tool(target, "prepare")
        self.assertTrue(prepared["valid"])
        self.assertEqual("cpu_validated", json.loads((target / ".paper2code/state.yaml").read_text())["state"])

        approved = self.run_tool(target, "approve", "--approver", "researcher@example.com")
        self.assertEqual("full_run_approved", approved["state"])
        gate = json.loads((target / ".paper2code/gates/full-run-gate.yaml").read_text())
        self.assertEqual("researcher@example.com", gate["approved_by"])
        self.assertIn("bundle_sha256", gate)
        self.assertIn("cpu_validation_report_sha256", gate)

    def test_execute_writes_logs_metrics_outputs_and_completes(self):
        target = self.scaffold()
        self.run_tool(target, "approve", "--approver", "researcher@example.com")

        result = self.run_tool(target, "execute")

        self.assertEqual("full_run_complete", result["state"])
        report = json.loads((target / "runs/fixture/report.yaml").read_text())
        self.assertEqual("passed", report["status"])
        self.assertEqual(3, len(report["commands"]))
        expected_artifacts = sorted(
            [
                *[f"runs/fixture/logs/seed-{seed}.log" for seed in (3, 5, 7)],
                *[f"runs/fixture/metrics/metric-{seed}.json" for seed in (3, 5, 7)],
                *[f"runs/fixture/outputs/result-{seed}.json" for seed in (3, 5, 7)],
            ]
        )
        self.assertEqual(expected_artifacts, sorted(report["artifacts"]))
        self.run_tool(target, "verify")

    def test_stale_approval_refuses_execution(self):
        target = self.scaffold()
        self.run_tool(target, "approve", "--approver", "researcher@example.com")
        bundle_path = target / "runs/fixture/bundle.yaml"
        bundle = json.loads(bundle_path.read_text())
        bundle["resolved_config"]["execution"]["workers"] = 2
        write_json(bundle_path, bundle)

        result = self.run_tool(target, "execute", expected=2)
        self.assertIn("stale Full Run approval", result["error"])

    def test_missing_capability_writes_report_without_running(self):
        target = self.scaffold(capability="missing-full-run-executable")
        self.run_tool(target, "approve", "--approver", "researcher@example.com")

        result = self.run_tool(target, "execute", expected=2)

        self.assertIn("missing-full-run-executable", result["error"])
        self.assertFalse((target / "runs/fixture/report.yaml").exists())
        self.assertTrue((target / ".paper2code/capability-reports/full-run-fixture.yaml").is_file())

    def test_imported_report_uses_the_same_validation_contract(self):
        target = self.scaffold()
        self.run_tool(target, "approve", "--approver", "researcher@example.com")
        self.run_tool(target, "execute")

        report_path = target / "runs/fixture/report.yaml"
        report = json.loads(report_path.read_text())
        report["execution_mode"] = "imported"
        write_json(report_path, report)
        write_json(
            target / ".paper2code/state.yaml",
            {"schema_version": "1.0", "state": "full_run_approved", "return_target": None},
        )

        imported = self.run_tool(target, "import")

        self.assertEqual("imported", imported["execution_mode"])
        self.assertEqual("full_run_complete", imported["state"])

    def test_missing_dataset_refuses_execution_before_commands(self):
        target = self.scaffold()
        self.run_tool(target, "approve", "--approver", "researcher@example.com")
        (target / "runs/fixture/datasets/input.json").unlink()

        result = self.run_tool(target, "execute", expected=2)

        self.assertIn("Missing Full Run dataset", result["error"])
        self.assertFalse((target / "runs/fixture/report.yaml").exists())

    def test_missing_seed_is_rejected_during_preparation(self):
        target = self.scaffold()
        bundle_path = target / "runs/fixture/bundle.yaml"
        bundle = json.loads(bundle_path.read_text())
        bundle["seeds"] = []
        write_json(bundle_path, bundle)

        result = self.run_tool(target, "prepare", expected=2)

        self.assertIn("needs at least 1 items", result["error"])

    def test_dirty_code_refuses_execution(self):
        target = self.scaffold()
        self.run_tool(target, "approve", "--approver", "researcher@example.com")
        (target / "implementation.py").write_text("# changed after approval\n", encoding="utf-8")

        result = self.run_tool(target, "execute", expected=2)

        self.assertIn("clean code checkout", result["error"])

    def test_incomplete_log_refuses_verification(self):
        target = self.scaffold()
        self.run_tool(target, "approve", "--approver", "researcher@example.com")
        self.run_tool(target, "execute")
        (target / "runs/fixture/logs/seed-3.log").unlink()

        result = self.run_tool(target, "verify", expected=2)

        self.assertIn("references missing artifact", result["error"])


if __name__ == "__main__":
    unittest.main()
