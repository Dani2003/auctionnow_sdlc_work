"""Unit tests for CI Orchestrator, Branch Governance Policies, and Local Scanner Runner.

Verifies:
1. Branch Promotion Policies (dev -> stage -> prod)
2. HITL Approval Records & Persona Auditing
3. CI Run Gating & Step Summary Markdown Generation
4. Local Scanner Runner Safety & Fallbacks
"""

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from sdlc_lab.branch_policy import (
    evaluate_branch_compliance,
    load_policy,
    resolve_branch_policy,
)
from sdlc_lab.ci_orchestrator import (
    generate_step_summary_md,
    load_scanner_reports_from_dir,
    run_ci,
)
from sdlc_lab.local_runner import (
    _run,
    run_all_scanners,
    run_gitleaks,
    run_osv,
    run_ruff,
    run_semgrep,
)
from sdlc_lab.schemas import validate_stage_artifact

ROOT = Path(__file__).resolve().parents[1]


class TestBranchGovernancePolicy(unittest.TestCase):
    """Tests for declarative branch promotion rules and role permissions."""

    def setUp(self):
        self.policy_data = load_policy()
        self.candidate_commit = "commit-abc1234567"
        self.clean_stage1 = {
            "stage": "agent_1_review",
            "findings": [],
            "confirmed_findings_count": 0,
            "unconfirmed_findings_count": 0,
            "commit_sha": self.candidate_commit
        }
        self.blocked_stage1 = {
            "stage": "agent_1_review",
            "findings": [
                {
                    "finding_id": "DET-001",
                    "severity": "critical",
                    "category": "secret_exposure",
                    "description": "AWS Secret exposed in file",
                    "file_path": "backend/auth.py",
                    "line_number": 12,
                    "confirmed_by_deterministic_tool": True,
                    "evidence_snippet": "AKIA..."
                }
            ],
            "confirmed_findings_count": 1,
            "unconfirmed_findings_count": 0,
            "commit_sha": self.candidate_commit
        }
        self.stage2 = {
            "stage": "agent_2_test_plan",
            "test_cases": [{"id": "TC-1", "title": "Quote boundary test"}],
            "commit_sha": self.candidate_commit
        }
        self.stage3 = {
            "stage": "agent_3_qa_plan",
            "risk_matrix": [{"risk": "auth bypass", "mitigation": "integration test"}],
            "commit_sha": self.candidate_commit
        }
        self.passing_ci_tests = {
            "total": 24,
            "passed": 24,
            "failed": 0,
            "skipped": 0,
            "commit_sha": self.candidate_commit
        }

    def test_resolve_branch_policy_exact_and_patterns(self):
        # Exact branch matches
        key, cfg = resolve_branch_policy("dev", self.policy_data)
        self.assertEqual(key, "dev")
        self.assertFalse(cfg["stage_apk_build_triggered"])

        key, cfg = resolve_branch_policy("stage", self.policy_data)
        self.assertEqual(key, "stage")
        self.assertTrue(cfg["stage_apk_build_triggered"])

        key, cfg = resolve_branch_policy("prod", self.policy_data)
        self.assertEqual(key, "prod")
        self.assertIn("release_manager", cfg["required_approval_roles"])

        # Wildcard pattern matches
        key, cfg = resolve_branch_policy("feature/quote-enhancement", self.policy_data)
        self.assertEqual(key, "dev")

        key, cfg = resolve_branch_policy("release/v2.1.0", self.policy_data)
        self.assertEqual(key, "stage")

    def test_dev_branch_blocks_on_critical_findings(self):
        result = evaluate_branch_compliance(
            target_branch="dev",
            stage1=self.blocked_stage1,
            stage2=self.stage2,
            stage3=self.stage3,
            candidate_commit=self.candidate_commit,
            automated_tests=self.passing_ci_tests
        )
        self.assertTrue(result["unresolved_high_findings"])
        self.assertTrue(any("Critical" in b for b in result["policy_blockers"]))

        # Tech Lead must reject
        tl_approvals = [a for a in result["approvals"] if a["role"] == "tech_lead"]
        self.assertEqual(len(tl_approvals), 1)
        self.assertEqual(tl_approvals[0]["decision"], "reject")
        self.assertIn("Sarah Chen", tl_approvals[0]["approver_name"])

    def test_dev_branch_approves_when_clean(self):
        result = evaluate_branch_compliance(
            target_branch="dev",
            stage1=self.clean_stage1,
            stage2=self.stage2,
            stage3=self.stage3,
            candidate_commit=self.candidate_commit,
            automated_tests=self.passing_ci_tests
        )
        self.assertFalse(result["unresolved_high_findings"])
        self.assertEqual(len(result["policy_blockers"]), 0)

        # Both Tech Lead and Senior Dev approve
        decisions = {a["role"]: a["decision"] for a in result["approvals"]}
        self.assertEqual(decisions.get("tech_lead"), "approve")
        self.assertEqual(decisions.get("developer"), "approve")

    def test_stage_branch_triggers_stage_apk_and_qa_lead(self):
        result = evaluate_branch_compliance(
            target_branch="stage",
            stage1=self.clean_stage1,
            stage2=self.stage2,
            stage3=self.stage3,
            candidate_commit=self.candidate_commit,
            automated_tests=self.passing_ci_tests
        )
        self.assertTrue(result["stage_apk_triggered"])
        self.assertTrue(result["qa_signed_off"])

        # QA Lead must be present in approvals
        qa_approvals = [a for a in result["approvals"] if a["role"] == "qa_lead"]
        self.assertEqual(len(qa_approvals), 1)
        self.assertEqual(qa_approvals[0]["decision"], "approve")
        self.assertIn("Priya Patel", qa_approvals[0]["approver_name"])

    def test_prod_branch_requires_release_manager_signoff(self):
        result = evaluate_branch_compliance(
            target_branch="prod",
            stage1=self.clean_stage1,
            stage2=self.stage2,
            stage3=self.stage3,
            candidate_commit=self.candidate_commit,
            automated_tests=self.passing_ci_tests
        )
        self.assertEqual(len(result["policy_blockers"]), 0)

        # Release Manager approval required for prod
        rm_approvals = [a for a in result["approvals"] if a["role"] == "release_manager"]
        self.assertEqual(len(rm_approvals), 1)
        self.assertEqual(rm_approvals[0]["decision"], "approve")
        self.assertIn("David Kim", rm_approvals[0]["approver_name"])

    def test_missing_or_failing_ci_tests_blocks_promotion(self):
        # Missing CI tests
        result_missing = evaluate_branch_compliance(
            target_branch="dev",
            stage1=self.clean_stage1,
            stage2=self.stage2,
            stage3=self.stage3,
            candidate_commit=self.candidate_commit,
            automated_tests=None
        )
        self.assertTrue(any("missing" in b.lower() for b in result_missing["policy_blockers"]))

        # Failing CI tests
        failing_tests = {"total": 24, "passed": 23, "failed": 1, "commit_sha": self.candidate_commit}
        result_failing = evaluate_branch_compliance(
            target_branch="dev",
            stage1=self.clean_stage1,
            stage2=self.stage2,
            stage3=self.stage3,
            candidate_commit=self.candidate_commit,
            automated_tests=failing_tests
        )
        self.assertTrue(any("failed with 1 failing" in b for b in result_failing["policy_blockers"]))


class TestCiOrchestratorExecution(unittest.TestCase):
    """Tests full CI Orchestrator CLI and execution lifecycle."""

    def test_ci_run_blocks_on_real_scanner_fixtures(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_json = Path(tmpdir) / "ci_run.json"
            out_summary = Path(tmpdir) / "summary.md"

            report = run_ci(
                target_branch="dev",
                commit_sha="mockcommit-104-a1b2c3",
                pr_id="PR-104",
                scanners_dir=ROOT / "fixtures",
                tests_file=ROOT / "fixtures" / "sample_ci_evidence.json",
                output_path=out_json,
                summary_path=out_summary
            )

            # Fixtures contain critical secret and semgrep issue -> Must BLOCK
            self.assertEqual(report["final_decision"], "BLOCKED")
            stage4 = next(s["artifact"] for s in report["stages"] if s["stage"] == "agent_4_release_summary")
            self.assertEqual(stage4["status"], "BLOCKED")
            self.assertTrue(out_json.exists())
            self.assertTrue(out_summary.exists())

            # Validate generated summary markdown
            summary_text = out_summary.read_text(encoding="utf-8")
            self.assertIn("BLOCKED", summary_text)
            self.assertIn("Sarah Chen", summary_text)
            self.assertIn("DET-GITLEAKS-001", summary_text)

    def test_step_summary_md_structure(self):
        report = {
            "pr": {"commit_sha": "a1b2c3d4e5f67890"}
        }
        stage1 = {
            "stage": "agent_1_review",
            "findings": [
                {
                    "finding_id": "TEST-01",
                    "tool": "semgrep",
                    "severity": "high",
                    "category": "authorization_gap",
                    "file_path": "backend/service.py",
                    "line_number": 10,
                    "description": "Auth gap",
                    "confirmed_by_deterministic_tool": True
                }
            ],
            "confirmed_findings_count": 1,
            "unconfirmed_findings_count": 0
        }
        stage2 = {"test_cases": [{"id": "T1"}], "clarification_requests": ["Q1"]}
        stage3 = {"manual_scenarios": [{"id": "S1"}]}
        stage4 = {
            "status": "PASS",
            "approvals": [
                {
                    "stage": "agent_1_review",
                    "decision": "approve",
                    "role": "tech_lead",
                    "approver_name": "Sarah Chen",
                    "artifact_sha256": "abcdef1234567890abcdef"
                }
            ]
        }
        md = generate_step_summary_md(report, stage1, stage2, stage3, stage4, target_branch="dev")
        self.assertIn("# ✅ AuctionNow SDLC Quality & Governance Report", md)
        self.assertIn("Sarah Chen", md)
        self.assertIn("TEST-01", md)


class TestLocalScannerRunner(unittest.TestCase):
    """Tests execution safety, timeouts, and fallback handling for local scanners."""

    def test_runner_missing_binary_fallback_safety(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir)
            # Call individual scanner functions; should return SKIPPED or COMPLETED without unhandled exception
            gl_res = run_gitleaks(ROOT, out_dir)
            self.assertIn(gl_res["status"], ("COMPLETED", "SKIPPED"))

            sg_res = run_semgrep(ROOT, out_dir)
            self.assertIn(sg_res["status"], ("COMPLETED", "SKIPPED"))

            osv_res = run_osv(ROOT, out_dir)
            self.assertIn(osv_res["status"], ("COMPLETED", "SKIPPED"))

            ruff_res = run_ruff(ROOT, out_dir)
            self.assertIn(ruff_res["status"], ("COMPLETED", "SKIPPED"))

    def test_run_all_scanners_creates_output_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "scanners_out"
            results = run_all_scanners(ROOT, out_dir)
            self.assertTrue(out_dir.exists())
            self.assertIsInstance(results, dict)
            self.assertIn("gitleaks", results)
            self.assertIn("semgrep", results)
            self.assertIn("osv", results)
            self.assertIn("linters", results)


if __name__ == "__main__":
    unittest.main()
