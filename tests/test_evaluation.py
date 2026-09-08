"""Exercise claim-level Full Run evaluation and typed diagnosis routing."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from _tmp import TempDirectory
from test_full_run import make_bundle, make_cpu_contract


ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "skills/setup-paper2code/scripts/setup.py"
VALIDATION = ROOT / "skills/paper-validation/scripts/validate.py"
RUN = ROOT / "skills/paper-run/scripts/run.py"
EVALUATE = ROOT / "skills/paper-evaluation/scripts/evaluate.py"
DIAGNOSE = ROOT / "skills/paper-diagnosis/scripts/diagnose.py"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


class EvaluationTests(unittest.TestCase):
    def scaffold(self, seeds=(3, 5, 7), contract=None, preregister=True):
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
        (target / "implementation.py").write_text("# fixture\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(target), "config", "user.email", "fixture@example.com"], check=True)
        subprocess.run(["git", "-C", str(target), "config", "user.name", "Fixture"], check=True)
        subprocess.run(["git", "-C", str(target), "add", "."], check=True)
        subprocess.run(["git", "-C", str(target), "commit", "-m", "fixture"], check=True, capture_output=True)
        revision = subprocess.check_output(["git", "-C", str(target), "rev-parse", "HEAD"], text=True).strip()
        make_bundle(target, revision=revision)
        bundle_path = target / "runs/fixture/bundle.yaml"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        bundle["seeds"] = list(seeds)
        write_json(bundle_path, bundle)
        if preregister:
            if contract is None:
                contract = ([self.claim()], None)
            self.write_contract(target, contract[0], contract[1])
        if not preregister:
            return target
        self.run_tool(target, "approve", "--approver", "researcher@example.com")
        self.run_tool(target, "execute")
        return target

    def run_tool(self, target, command, *args, expected=0):
        if command in {"approve", "execute"}:
            tool = RUN
        elif command in {"evaluate", "verify"}:
            tool = EVALUATE
        else:
            tool = DIAGNOSE
        completed = subprocess.run(
            [sys.executable, str(tool), "--root", str(target), command, *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(expected, completed.returncode, completed.stderr or completed.stdout)
        return json.loads(completed.stdout) if completed.stdout.strip() else {"error": completed.stderr}

    def write_contract(self, target, claims, metrics=None):
        write_json(
            target / "results/evaluation.yaml",
            {
                "schema_version": "1.0",
                "stage": "evaluation",
                "status": "preregistered",
                "full_run_id": "fixture",
                "preregistered_at": "2026-01-01T00:00:00+00:00",
                "preregistered_by": "researcher@example.com",
                "claims": claims,
                "metrics": metrics
                or [
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

    @staticmethod
    def claim(identifier="CLM-0001", target_id="MET-0001", validation_ids=None, minimum="low", independent=True):
        return {
            "id": identifier,
            "title": identifier,
            "scope": "must",
            "implementation": {"validation_ids": validation_ids or ["PATH-0001"]},
            "execution": {"command_ids": ["CMD-0001"], "independent_seeds": independent},
            "result": {"metric_id": target_id},
            "evidence": {
                "provenance": "source-faithful",
                "minimum_strength": minimum,
                "required_artifacts": [],
                "digitization_uncertainty": 0,
            },
        }

    def test_replicated_claims_advance_to_evaluated(self):
        target = self.scaffold(contract=([self.claim()], None))

        result = self.run_tool(target, "evaluate")

        self.assertEqual("replicated", result["outcome"])
        self.assertEqual("evaluated", result["state"])
        report = json.loads((target / "results/evaluation-report.yaml").read_text())
        self.assertEqual("passed", report["claims"][0]["implementation"]["status"])
        self.assertEqual("passed", report["claims"][0]["execution"]["status"])
        self.assertEqual("passed", report["claims"][0]["result_agreement"]["status"])
        self.assertEqual("high", report["claims"][0]["evidence"]["strength"])
        self.run_tool(target, "verify")

    def test_partial_outcome_keeps_each_claim_assessment(self):
        claims = [
            self.claim("CLM-0001"),
            self.claim("CLM-0002", validation_ids=["PATH-9999"]),
        ]
        target = self.scaffold(contract=(claims, None))

        result = self.run_tool(target, "evaluate")

        self.assertEqual("partially replicated", result["outcome"])
        report = json.loads((target / "results/evaluation-report.yaml").read_text())
        self.assertEqual(
            ["replicated", "inconclusive"],
            [claim["verdict"] for claim in report["claims"]],
        )

    def test_decisive_result_mismatch_is_not_replicated(self):
        metric = {
            "id": "MET-0001",
            "title": "Fixture score",
            "path": "{run_dir}/metrics/metric-{seed}.json",
            "json_pointer": "/score",
            "aggregation": "mean",
            "target": 100,
            "tolerance": 0,
            "comparison": "within",
        }
        target = self.scaffold(contract=([self.claim()], [metric]))

        result = self.run_tool(target, "evaluate", expected=2)

        self.assertEqual("not replicated", result["outcome"])
        self.assertEqual("revision_required", result["state"])
        self.assertEqual("result", result["failure"]["class"])
        report = json.loads((target / "results/evaluation-report.yaml").read_text())
        self.assertEqual("failed", report["claims"][0]["result_agreement"]["status"])
        self.assertEqual("not replicated", report["claims"][0]["verdict"])

    def test_single_seed_is_reportable_but_not_high_strength(self):
        contract = ([self.claim(minimum="high")], [
            {
                "id": "MET-0001",
                "title": "Fixture score",
                "path": "{run_dir}/metrics/metric-{seed}.json",
                "json_pointer": "/score",
                "aggregation": "single",
                "target": 6,
                "tolerance": 0,
                "comparison": "within",
            }
        ])
        target = self.scaffold(seeds=(3,), contract=contract)

        result = self.run_tool(target, "evaluate")

        self.assertEqual("inconclusive", result["outcome"])
        report = json.loads((target / "results/evaluation-report.yaml").read_text())
        self.assertEqual("low", report["claims"][0]["evidence"]["strength"])
        self.assertFalse(report["claims"][0]["evidence"]["sufficient"])

    def test_non_independent_mismatch_is_inconclusive(self):
        metric = {
            "id": "MET-0001",
            "title": "Fixture score",
            "path": "{run_dir}/metrics/metric-{seed}.json",
            "json_pointer": "/score",
            "aggregation": "mean",
            "target": 100,
            "tolerance": 0,
            "comparison": "within",
        }
        target = self.scaffold(contract=([self.claim(independent=False)], [metric]))

        result = self.run_tool(target, "evaluate")

        self.assertEqual("inconclusive", result["outcome"])
        report = json.loads((target / "results/evaluation-report.yaml").read_text())
        self.assertEqual("moderate", report["claims"][0]["evidence"]["strength"])
        self.assertEqual("inconclusive", report["claims"][0]["verdict"])

    def test_changed_preregistration_invalidates_evaluation(self):
        target = self.scaffold(contract=([self.claim()], None))
        self.run_tool(target, "evaluate")
        contract_path = target / "results/evaluation.yaml"
        contract = json.loads(contract_path.read_text())
        contract["metrics"][0]["tolerance"] = 1
        write_json(contract_path, contract)

        result = self.run_tool(target, "verify", expected=2)

        self.assertIn("evaluation contract changed", result["error"] if result else "")

    def test_tampered_verdict_is_rejected_by_verification(self):
        target = self.scaffold(contract=([self.claim()], None))
        self.run_tool(target, "evaluate")
        report_path = target / "results/evaluation-report.yaml"
        report = json.loads(report_path.read_text())
        report["claims"][0]["verdict"] = "not replicated"
        report["outcome"] = "not replicated"
        write_json(report_path, report)

        result = self.run_tool(target, "verify", expected=2)

        self.assertIn("verdicts do not match", result["error"] if result else "")

    def test_evaluation_report_numeric_bounds_are_enforced(self):
        target = self.scaffold(contract=([self.claim()], None))
        self.run_tool(target, "evaluate")
        report_path = target / "results/evaluation-report.yaml"
        report = json.loads(report_path.read_text())
        report["claims"][0]["evidence"]["validation_coverage"] = 2
        write_json(report_path, report)

        result = self.run_tool(target, "verify", expected=2)

        self.assertIn("at most 1", result["error"] if result else "")

    def test_evaluation_requires_preregistration_before_full_run(self):
        target = self.scaffold(preregister=False)

        result = self.run_tool(target, "approve", "--approver", "researcher@example.com", expected=2)

        self.assertIn("requires results/evaluation.yaml", result["error"] if result else "")

    def test_evidence_failure_routes_to_needs_decision(self):
        metric = {
            "id": "MET-0001",
            "title": "Missing score",
            "path": "{run_dir}/metrics/missing-{seed}.json",
            "json_pointer": "/score",
            "aggregation": "mean",
            "target": 10,
            "tolerance": 0,
            "comparison": "within",
        }
        target = self.scaffold(contract=([self.claim()], [metric]))

        result = self.run_tool(target, "evaluate", expected=2)

        self.assertEqual("needs_decision", result["state"])
        state = json.loads((target / ".paper2code/state.yaml").read_text())
        self.assertEqual("full_run_complete", state["return_target"])

    def test_diagnosis_routes_each_failure_class(self):
        expected = {
            "software": "diagnosing",
            "scientific": "diagnosing",
            "result": "revision_required",
            "environment": "diagnosing",
            "evidence": "needs_decision",
        }
        for failure_class, state_name in expected.items():
            with self.subTest(failure_class=failure_class):
                target = self.scaffold()
                result = self.run_tool(
                    target,
                    "diagnose",
                    "--failure-class",
                    failure_class,
                    "--id",
                    "FIX-0001",
                    "--message",
                    "fixture failure",
                )
                self.assertEqual(state_name, result["route"]["state"])
                state = json.loads((target / ".paper2code/state.yaml").read_text())
                self.assertEqual(state_name, state["state"])
                self.assertEqual("full_run_complete", state["return_target"])


if __name__ == "__main__":
    unittest.main()
