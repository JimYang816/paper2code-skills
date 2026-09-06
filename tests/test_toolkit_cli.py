import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "skills" / "paper2code-core" / "scripts" / "paper2code.py"


class ToolkitCliTests(unittest.TestCase):
    def run_cli(self, *args: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [sys.executable, str(CLI), *map(str, args)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(expected, completed.returncode, completed.stderr or completed.stdout)
        return completed

    def write_yaml(self, path: Path, value: object) -> Path:
        path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
        return path

    def test_contract_validation_accepts_valid_state_and_rejects_invalid_state(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            valid = self.write_yaml(
                folder / "state.yaml",
                {"schema_version": "1.0", "state": "setup_pending", "return_target": None},
            )
            invalid = self.write_yaml(
                folder / "bad.yaml", {"schema_version": "1.0", "state": "made_up"}
            )
            self.run_cli("validate", valid, "--schema", "state")
            result = self.run_cli("validate", invalid, "--schema", "state", expected=2)
            self.assertIn("made_up", result.stderr)

    def test_canonical_hash_is_stable_across_yaml_key_order(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            first = self.write_yaml(folder / "a.yaml", {"b": 2, "a": {"y": 1, "x": 0}})
            second = self.write_yaml(folder / "b.yaml", {"a": {"x": 0, "y": 1}, "b": 2})
            first_hash = json.loads(self.run_cli("canonical-hash", first).stdout)["sha256"]
            second_hash = json.loads(self.run_cli("canonical-hash", second).stdout)["sha256"]
            self.assertEqual(first_hash, second_hash)

    def test_transition_check_handles_normal_and_typed_exception_states(self):
        with tempfile.TemporaryDirectory() as raw:
            state = self.write_yaml(
                Path(raw) / "state.yaml",
                {"schema_version": "1.0", "state": "evidence_extracted", "return_target": None},
            )
            self.run_cli("check-transition", state, "--to", "evidence_approved")
            self.run_cli("check-transition", state, "--to", "evaluated", expected=2)
            self.run_cli(
                "check-transition",
                state,
                "--to",
                "needs_decision",
                "--return-target",
                "evidence_extracted",
            )

    def test_router_reports_every_normal_and_exception_state(self):
        states = [
            "setup_pending", "ready_for_extraction", "evidence_extracted", "evidence_approved",
            "specification_ready", "specification_approved", "implementation_active",
            "cpu_validated", "full_run_approved", "full_run_complete", "evaluated",
            "needs_decision", "diagnosing", "revision_required",
        ]
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "state.yaml"
            for state in states:
                return_target = "implementation_active" if state in {"needs_decision", "diagnosing", "revision_required"} else None
                self.write_yaml(path, {"schema_version": "1.0", "state": state, "return_target": return_target})
                result = json.loads(self.run_cli("route", path).stdout)
                self.assertEqual(state, result["state"])
                self.assertIn("next_skill", result)

    def test_gate_verification_detects_stale_approved_artifact(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            artifact = self.write_yaml(folder / "scope.yaml", {"claims": ["M0"]})
            digest = json.loads(self.run_cli("canonical-hash", artifact).stdout)["sha256"]
            gate = self.write_yaml(
                folder / "gate.yaml",
                {
                    "schema_version": "1.0",
                    "approval_scope": "paper-dossier",
                    "artifact_hashes": {"scope.yaml": digest},
                    "schema_versions": {"scope": "1.0"},
                    "approved_by": "researcher",
                    "approved_at": "2026-09-06T00:00:00Z",
                    "authorizes": {"from": "evidence_extracted", "to": "evidence_approved"},
                },
            )
            self.run_cli("verify-gate", gate, "--root", folder)
            self.write_yaml(artifact, {"claims": ["M0", "M1"]})
            result = self.run_cli("verify-gate", gate, "--root", folder, expected=2)
            self.assertIn("stale", result.stderr.lower())

    def test_manifest_verification_checks_expected_file_hashes(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            payload = folder / "fixture.bin"
            payload.write_bytes(b"fixture")
            digest = hashlib.sha256(payload.read_bytes()).hexdigest()
            manifest = self.write_yaml(
                folder / "dataset.yaml",
                {
                    "schema_version": "1.0",
                    "dataset_id": "fixture-v1",
                    "source": {"name": "fixture", "url": "https://example.invalid/data"},
                    "license": {"name": "test-only", "redistribution": "fixture-only"},
                    "availability": "fixture",
                    "preparation_recipe": ["Use the committed deterministic fixture."],
                    "expected_files": [{"path": "fixture.bin", "sha256": digest}],
                },
            )
            self.run_cli("verify-manifest", manifest, "--root", folder)
            payload.write_bytes(b"changed")
            self.run_cli("verify-manifest", manifest, "--root", folder, expected=2)

    def test_run_bundle_enforces_seed_policy_and_complete_paths(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            for name in ("resolved.yaml", "environment.txt", "run.log", "metrics.json", "output.bin"):
                (folder / name).write_text("ok", encoding="utf-8")
            base = {
                "schema_version": "1.0",
                "run_id": "udnet-full",
                "learned_method": True,
                "budget_approved_single_run": False,
                "resolved_configuration": "resolved.yaml",
                "environment": "environment.txt",
                "code_revision": "a" * 40,
                "code_dirty": False,
                "dataset_manifests": [],
                "commands": ["python train.py"],
                "logs": ["run.log"],
                "metrics": ["metrics.json"],
                "outputs": ["output.bin"],
                "status": "complete",
            }
            bundle = self.write_yaml(folder / "run.yaml", {**base, "seeds": [1]})
            result = self.run_cli("verify-run-bundle", bundle, "--root", folder, expected=2)
            self.assertIn("three", result.stderr.lower())
            self.write_yaml(bundle, {**base, "seeds": [1, 2, 3]})
            self.run_cli("verify-run-bundle", bundle, "--root", folder)

    def test_claim_aggregation_keeps_inadequate_evidence_inconclusive(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            verdicts = self.write_yaml(
                folder / "claims.yaml",
                {
                    "schema_version": "1.0",
                    "claims": [
                        {
                            "claim_id": "M0",
                            "scope": "must",
                            "implementation": "supported",
                            "execution": "complete",
                            "result_agreement": "contradicted",
                            "evidence_strength": "inadequate",
                        }
                    ],
                },
            )
            outcome = json.loads(self.run_cli("evaluate", verdicts).stdout)
            self.assertEqual("inconclusive", outcome["outcome"])
            data = yaml.safe_load(verdicts.read_text(encoding="utf-8"))
            data["claims"][0]["evidence_strength"] = "adequate"
            self.write_yaml(verdicts, data)
            outcome = json.loads(self.run_cli("evaluate", verdicts).stdout)
            self.assertEqual("not_replicated", outcome["outcome"])

    def test_claim_aggregation_covers_replicated_and_partial_outcomes(self):
        supported = {
            "claim_id": "M0", "scope": "must", "implementation": "supported",
            "execution": "complete", "result_agreement": "supported", "evidence_strength": "strong",
        }
        incomplete = {
            "claim_id": "M1", "scope": "must", "implementation": "supported",
            "execution": "partial", "result_agreement": "not_evaluable", "evidence_strength": "limited",
        }
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "claims.yaml"
            self.write_yaml(path, {"schema_version": "1.0", "claims": [supported]})
            self.assertEqual("replicated", json.loads(self.run_cli("evaluate", path).stdout)["outcome"])
            self.write_yaml(path, {"schema_version": "1.0", "claims": [supported, incomplete]})
            self.assertEqual("partially_replicated", json.loads(self.run_cli("evaluate", path).stdout)["outcome"])

    def test_skill_closure_reports_missing_dependencies(self):
        with tempfile.TemporaryDirectory() as raw:
            folder = Path(raw)
            (folder / "skills" / "root").mkdir(parents=True)
            (folder / "skills" / "root" / "SKILL.md").write_text("root", encoding="utf-8")
            lock = self.write_yaml(
                folder / "skills-lock.yaml",
                {
                    "schema_version": "1.0",
                    "skills": {
                        "root": {
                            "origin": "local",
                            "content_hash": "0" * 64,
                            "modification": "new",
                            "dependencies": ["missing"],
                        }
                    },
                },
            )
            result = self.run_cli(
                "verify-closure",
                lock,
                "--skills-dir",
                folder / "skills",
                "--root-skill",
                "root",
                expected=2,
            )
            self.assertIn("missing", result.stderr.lower())

    def test_specification_readiness_requires_terminal_must_ambiguities(self):
        with tempfile.TemporaryDirectory() as raw:
            path = self.write_yaml(
                Path(raw) / "ambiguities.yaml",
                {
                    "schema_version": "1.0",
                    "ambiguities": [
                        {
                            "ambiguity_id": "A-CHANNEL",
                            "scope": "must",
                            "question": "Which channel configuration is intended?",
                            "evidence_ids": ["E-DATA-1"],
                            "resolution": "open",
                            "decision_record": None,
                        }
                    ],
                },
            )
            result = self.run_cli("check-specification-readiness", path, expected=2)
            self.assertIn("A-CHANNEL", result.stderr)
            record = yaml.safe_load(path.read_text(encoding="utf-8"))
            record["ambiguities"][0]["resolution"] = "reconstructed"
            record["ambiguities"][0]["decision_record"] = "decisions/channel.yaml"
            self.write_yaml(path, record)
            self.run_cli("check-specification-readiness", path)


if __name__ == "__main__":
    unittest.main()
