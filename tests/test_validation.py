"""Exercise the independent numerical reference and CPU Validation Gate."""

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

from _tmp import TempDirectory


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "skills/setup-paper2code/scripts/setup.py"
CORE = ROOT / "skills/paper2code-core/scripts/paper2code.py"
VALIDATION = ROOT / "skills/paper-validation/scripts/validate.py"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def make_contract(target, *, math_mode="pass", path_mode="pass", artifact=False):
    command = ["{python}", "{root}/validation/fixture.py"]
    math_command = [*command, "--math", f"--mode={math_mode}"]
    paths = []
    for kind in ("data", "model", "baseline", "metric", "reporting"):
        path = {
            "id": f"PATH-{len(paths) + 1:04d}",
            "kind": kind,
            "title": f"Reduced CPU {kind} path",
            "command": [*command, "--path", kind, f"--mode={path_mode}"],
            "failure_class": "software",
            "artifacts": [],
        }
        if artifact and kind == "data":
            path["artifacts"] = ["validation/reports/data.json"]
        paths.append(path)
    contract = {
        "schema_version": "1.0",
        "stage": "cpu_validation",
        "deterministic": {"seed": 7, "device": "cpu", "workers": 1},
        "critical_math": [
            {
                "id": "MATH-0001",
                "title": "Known two-tap transform",
                "reference": "validation/references/two_tap.py",
                "command": math_command,
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
    return contract


class ValidationTests(unittest.TestCase):
    def scaffold(self):
        temp = TempDirectory()
        self.addCleanup(temp.cleanup)
        folder = Path(temp.name)
        target = folder / "paper"
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
        write_json(
            target / ".paper2code/state.yaml",
            {"schema_version": "1.0", "state": "implementation_active", "return_target": None},
        )
        (target / "validation/references/two_tap.py").parent.mkdir(parents=True, exist_ok=True)
        (target / "validation/references/two_tap.py").write_text("# independent reference\n", encoding="utf-8")
        (target / "validation/fixture.py").write_text(
            "import argparse, json, pathlib\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--math', action='store_true')\n"
            "parser.add_argument('--path')\n"
            "parser.add_argument('--mode', default='pass')\n"
            "args = parser.parse_args()\n"
            "if args.mode == 'fail': raise SystemExit(3)\n"
            "if args.math:\n"
            "    print(json.dumps({'status': 'passed', 'checks': {\n"
            "        'invariants': ['INV-0001'], 'units': ['UNIT-0001'],\n"
            "        'shapes': ['SHAPE-0001'], 'gradients': ['GRAD-0001']}}))\n"
            "elif args.path == 'data' and pathlib.Path('validation/write-data').exists():\n"
            "    pathlib.Path('validation/reports/data.json').write_text('{}')\n",
            encoding="utf-8",
        )
        return target

    def execute(self, tool, target, *args, expected=0):
        completed = subprocess.run(
            [sys.executable, str(tool), "--root", str(target), *map(str, args)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(expected, completed.returncode, completed.stderr or completed.stdout)
        if completed.stdout.strip():
            return json.loads(completed.stdout)
        return {"error": completed.stderr}

    def run_core(self, target, *args, expected=0):
        completed = subprocess.run(
            [sys.executable, str(CORE), *map(str, args)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(expected, completed.returncode, completed.stderr or completed.stdout)
        return completed

    def test_valid_fixture_runs_every_path_and_advances_cpu_gate(self):
        target = self.scaffold()
        make_contract(target)

        result = self.execute(VALIDATION, target, "run")

        self.assertEqual("cpu_validated", result["state"])
        report = json.loads(
            (target / "validation/reports/cpu-validation.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual("passed", report["status"])
        self.assertEqual(5, len(report["paths"]))
        self.assertEqual("passed", report["math"][0]["status"])
        verified = self.execute(VALIDATION, target, "verify")
        self.assertTrue(verified["valid"])

    def test_numerical_reference_accepts_equivalence_and_rejects_gain_fault(self):
        for fault in (False, True):
            with self.subTest(fault=fault):
                target = self.scaffold()
                contract = make_contract(target)
                for name in ("channel.py", "reference.py", "check_channel.py"):
                    shutil.copyfile(ROOT / "tests/fixtures/scientific" / name,
                                    target / "validation" / ("references" if name == "reference.py" else "") / name)
                math = contract["critical_math"][0]
                math["reference"] = "validation/references/reference.py"
                math["command"] = ["{python}", "{root}/validation/check_channel.py"]
                if fault:
                    math["command"].append("--fault")
                write_json(target / "validation/validation.yaml", contract)
                result = self.execute(VALIDATION, target, "run", expected=2 if fault else 0)
                self.assertEqual("diagnosing" if fault else "cpu_validated", result["state"])
                if fault:
                    self.assertEqual("scientific", result["failure"]["class"])
                else:
                    self.assertTrue(self.execute(VALIDATION, target, "verify")["valid"])

    def test_cpu_transition_rejects_report_without_reference_checks(self):
        target = self.scaffold()
        make_contract(target)
        self.execute(VALIDATION, target, "run")
        report_path = target / "validation/reports/cpu-validation.yaml"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["math"][0]["checks"]["gradients"] = []
        write_json(report_path, report)
        write_json(
            target / ".paper2code/state.yaml",
            {"schema_version": "1.0", "state": "implementation_active", "return_target": None},
        )

        result = self.run_core(
            target,
            "check-transition",
            target / ".paper2code/state.yaml",
            "--to",
            "cpu_validated",
            expected=2,
        )

        self.assertIn("missing gradients checks", result.stderr)

    def test_implementation_completion_alone_cannot_advance_cpu_gate(self):
        target = self.scaffold()

        result = self.run_core(
            target,
            "check-transition",
            target / ".paper2code/state.yaml",
            "--to",
            "cpu_validated",
            expected=2,
        )

        self.assertIn("CPU Validation Report", result.stderr)
        state = json.loads((target / ".paper2code/state.yaml").read_text(encoding="utf-8"))
        self.assertEqual("implementation_active", state["state"])

    def test_missing_required_path_kind_is_rejected(self):
        target = self.scaffold()
        contract = make_contract(target)
        contract["paths"][-1]["kind"] = "data"
        write_json(target / "validation/validation.yaml", contract)

        result = self.execute(VALIDATION, target, "validate", expected=2)

        self.assertIn("reporting", result["error"] if result else "")

    def test_scientific_failure_routes_to_diagnosing(self):
        target = self.scaffold()
        make_contract(target, math_mode="fail")

        result = self.execute(VALIDATION, target, "run", expected=2)

        self.assertEqual("failed", result["status"])
        self.assertEqual("scientific", result["failure"]["class"])
        state = json.loads((target / ".paper2code/state.yaml").read_text(encoding="utf-8"))
        self.assertEqual("diagnosing", state["state"])
        self.assertEqual("implementation_active", state["return_target"])

    def test_environment_failure_has_distinct_route(self):
        target = self.scaffold()
        contract = make_contract(target)
        contract["paths"][0]["command"] = ["{root}/missing-executable"]
        contract["paths"][0]["failure_class"] = "environment"
        write_json(target / "validation/validation.yaml", contract)

        result = self.execute(VALIDATION, target, "run", expected=2)

        self.assertEqual("environment", result["failure"]["class"])
        self.assertEqual("diagnosing", result["state"])

    def test_software_failure_has_distinct_route(self):
        target = self.scaffold()
        contract = make_contract(target)
        contract["paths"][0]["command"][-1] = "--mode=fail"
        contract["paths"][0]["failure_class"] = "software"
        write_json(target / "validation/validation.yaml", contract)

        result = self.execute(VALIDATION, target, "run", expected=2)

        self.assertEqual("software", result["failure"]["class"])
        self.assertEqual("diagnosing", result["state"])

    def test_missing_output_is_an_evidence_failure(self):
        target = self.scaffold()
        make_contract(target, artifact=True)

        result = self.execute(VALIDATION, target, "run", expected=2)

        self.assertEqual("evidence", result.get("failure", {}).get("class"), result)
        self.assertEqual("needs_decision", result["state"])
        self.assertEqual("implementation_active", result["return_target"])


if __name__ == "__main__":
    unittest.main()
