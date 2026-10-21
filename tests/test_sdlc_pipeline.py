"""Comprehensive test suite for AuctionNow AI-Assisted SDLC Pipeline.

Tests:
1. Deterministic Scanner Ingestion (Gitleaks, Semgrep, OSV, Linters)
2. Agent 1: Confirmed vs Unconfirmed Finding Separation & Redaction
3. Agent 2: SDET Test Proposal Categorization & Clarification Requests
4. Agent 3: QA Risk-Based Matrix & Proof-of-Execution Verification
5. Agent 4: Release Gate Statuses (PASS, BLOCKED, NEEDS_HUMAN_REVIEW)
6. Workflow: Lazy Execution, Pipeline Halt on Rejection, Role Auditing
7. Schema Validation & Tamper Prevention
"""

import json
from pathlib import Path
import unittest

from sdlc_lab.agents import (
    code_quality_security_review,
    qa_directives,
    release_evidence_summary,
    sdet_test_plan,
)
from sdlc_lab.schemas import (
    ApprovalRecord,
    Finding,
    ValidationError,
    compute_sha256,
    validate_stage_artifact,
)
from sdlc_lab.scanners import (
    ScannerIngestor,
    mask_secret,
    normalize_all_scanner_reports,
)
from sdlc_lab.workflow import run_workflow

ROOT = Path(__file__).resolve().parents[1]


class TestScannerIngestion(unittest.TestCase):
    """Tests for deterministic tool ingestion and redaction."""

    def test_secret_masking(self):
        self.assertEqual(mask_secret(""), "[EMPTY]")
        self.assertEqual(mask_secret("short"), "[REDACTED]")
        masked = mask_secret("SUPER_SECRET_PRODUCTION_KEY_999")
        self.assertTrue(masked.startswith("SU...[REDACTED]..."))
        self.assertNotIn("SECRET_PRODUCTION", masked)

    def test_gitleaks_ingestion_and_redaction(self):
        report = [
            {
                "RuleID": "aws-access-token",
                "Description": "AWS Access Key",
                "File": "backend/app/auth.py",
                "StartLine": 42,
                "Secret": "AKIAIOSFODNN7EXAMPLE99"
            }
        ]
        findings = ScannerIngestor.parse_gitleaks(report)
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f.category, "secret_exposure")
        self.assertEqual(f.severity, "critical")
        self.assertTrue(f.confirmed_by_deterministic_tool)
        self.assertEqual(f.source_tool, "gitleaks")
        self.assertEqual(f.file_path, "backend/app/auth.py")
        self.assertEqual(f.line_number, 42)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE99", f.evidence)
        self.assertIn("[REDACTED]", f.evidence)

    def test_semgrep_ingestion_severity_mapping(self):
        report = {
            "results": [
                {
                    "check_id": "python.lang.security.insecure-auth.idor",
                    "path": "backend/app/quotes/service.py",
                    "start": {"line": 15},
                    "extra": {
                        "severity": "ERROR",
                        "message": "Missing tenant ownership check on resource"
                    }
                }
            ]
        }
        findings = ScannerIngestor.parse_semgrep(report)
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f.category, "authorization_gap")
        self.assertEqual(f.severity, "high")
        self.assertTrue(f.confirmed_by_deterministic_tool)
        self.assertEqual(f.line_number, 15)

    def test_osv_ingestion(self):
        report = {
            "results": [
                {
                    "source": {"path": "backend/requirements.txt"},
                    "packages": [
                        {
                            "package": {"name": "cryptography", "version": "3.3.0"},
                            "vulnerabilities": [
                                {
                                    "id": "GHSA-test-vuln-01",
                                    "summary": "Sample advisory",
                                    "database_specific": {"severity": "critical"}
                                }
                            ]
                        }
                    ]
                }
            ]
        }
        findings = ScannerIngestor.parse_osv(report)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, "vulnerable_dependency")
        self.assertEqual(findings[0].severity, "critical")
        self.assertTrue(findings[0].confirmed_by_deterministic_tool)

    def test_malformed_scanner_reports_handled_gracefully(self):
        self.assertEqual(normalize_all_scanner_reports(None), [])
        self.assertEqual(normalize_all_scanner_reports({}), [])
        self.assertEqual(normalize_all_scanner_reports({"gitleaks": []}), [])


class TestAgent1QualityAndSecurityReviewer(unittest.TestCase):
    """Tests for Agent 1 vendor-neutral review and finding separation."""

    def test_deterministic_vs_advisory_findings_distinction(self):
        pr = {
            "pr_id": "PR-101",
            "commit_sha": "sha-101",
            "changed_files": ["backend/app/quotes/service.py"],
            "diff_excerpt": "def accept(id):\n    # TODO: add authorization\n    eval(user_input)\n"
        }
        scanner_reports = {
            "semgrep": {
                "results": [
                    {
                        "check_id": "semgrep-auth-rule",
                        "path": "backend/app/quotes/service.py",
                        "start": {"line": 2},
                        "extra": {"severity": "ERROR", "message": "IDOR risk"}
                    }
                ]
            }
        }
        review = code_quality_security_review(pr, scanner_reports=scanner_reports)
        self.assertEqual(review["confirmed_findings_count"], 1)
        self.assertEqual(review["unconfirmed_findings_count"], 2)  # eval and TODO
        self.assertTrue(review["policy_blocked"])

        # Check confirmed finding
        confirmed = [f for f in review["findings"] if f["confirmed_by_deterministic_tool"]]
        self.assertEqual(len(confirmed), 1)
        self.assertEqual(confirmed[0]["source_tool"], "semgrep")

        # Check advisory finding
        advisory = [f for f in review["findings"] if not f["confirmed_by_deterministic_tool"]]
        self.assertEqual(len(advisory), 2)
        self.assertTrue(all(f["source_tool"] == "llm_advisory" for f in advisory))


class TestAgent2SDETTestPlanner(unittest.TestCase):
    """Tests for Agent 2 proposal generation and clarification protocols."""

    def test_test_proposals_categorization(self):
        pr = {
            "pr_id": "PR-202",
            "commit_sha": "sha-202",
            "changed_files": ["backend/app/quotes/service.py", "mobile/src/features/quotes/AcceptQuoteButton.tsx"]
        }
        reqs = {
            "acceptance_criteria": [
                "A buyer can accept a quote belonging to their own request",
                "A buyer cannot accept a quote belonging to another buyer's request",
                "A quote that is no longer available returns a clear error",
                "The UI prevents duplicate submissions while processing"
            ]
        }
        plan = sdet_test_plan(pr, reqs)
        cases = plan["test_cases"]

        categories = {c["category"] for c in cases}
        self.assertIn("positive", categories)
        self.assertIn("authorization", categories)
        self.assertIn("negative", categories)
        self.assertIn("platform", categories)
        self.assertIn("boundary", categories)
        self.assertIn("failure", categories)

        # Verify platform test targets mobile
        mobile_cases = [c for c in cases if c["target_surface"] == "mobile"]
        self.assertTrue(len(mobile_cases) >= 1)

        # Status must strictly be proposed_not_executed
        self.assertTrue(all(c["status"] == "proposed_not_executed" for c in cases))

    def test_clarification_requests_formulated(self):
        plan = sdet_test_plan({"pr_id": "PR-1"}, {"acceptance_criteria": ["Quote expires"]})
        self.assertTrue(len(plan["clarification_requests"]) >= 1)
        cr = plan["clarification_requests"][0]
        self.assertIn("topic", cr)
        self.assertIn("question", cr)
        self.assertIn("impact", cr)


class TestAgent3QADirector(unittest.TestCase):
    """Tests for Agent 3 risk-based manual matrix and automation evidence."""

    def test_proposals_never_count_as_automated_coverage(self):
        plan = sdet_test_plan({}, {"acceptance_criteria": ["Valid acceptance"]})
        qa = qa_directives({}, plan, {"findings": []}, automated_test_results=None)

        for row in qa["manual_test_matrix"]:
            self.assertFalse(row["automated_coverage_confirmed"])
            self.assertIn("None", row["automation_evidence"])

    def test_verified_passing_ci_test_marks_coverage(self):
        commit = "sha-verified-303"
        pr = {"pr_id": "PR-303", "commit_sha": commit}
        reqs = {"acceptance_criteria": ["A buyer can accept a quote belonging to their own request"]}
        plan = sdet_test_plan(pr, reqs, candidate_commit=commit)

        # Provide simulated passing CI test run matching the exact commit
        ci_results = {
            "tests": {
                "TC-POS-001": {
                    "test_name": "test_accept_quote_success",
                    "test_file": "backend/tests/test_quotes.py",
                    "status": "PASSED",
                    "commit_sha": commit
                }
            }
        }
        qa = qa_directives(pr, plan, {"findings": []}, automated_test_results=ci_results, candidate_commit=commit)
        covered_row = next(r for r in qa["manual_test_matrix"] if r["scenario_id"] == "TC-POS-001")
        self.assertTrue(covered_row["automated_coverage_confirmed"])
        self.assertIn("PASSED", covered_row["automation_evidence"])

    def test_stale_commit_in_ci_test_rejected_as_coverage(self):
        commit = "sha-new-404"
        pr = {"pr_id": "PR-404", "commit_sha": commit}
        reqs = {"acceptance_criteria": ["A buyer can accept a quote belonging to their own request"]}
        plan = sdet_test_plan(pr, reqs, candidate_commit=commit)

        # CI test run is from an OLD commit SHA
        ci_results = {
            "tests": {
                "TC-POS-001": {
                    "test_name": "test_accept_quote_success",
                    "test_file": "backend/tests/test_quotes.py",
                    "status": "PASSED",
                    "commit_sha": "sha-old-111"  # Mismatch!
                }
            }
        }
        qa = qa_directives(pr, plan, {"findings": []}, automated_test_results=ci_results, candidate_commit=commit)
        row = next(r for r in qa["manual_test_matrix"] if r["scenario_id"] == "TC-POS-001")
        self.assertFalse(row["automated_coverage_confirmed"])


class TestAgent4ReleaseSummarizer(unittest.TestCase):
    """Tests for Agent 4 release gate evaluation."""

    def test_pass_when_all_evidence_and_approvals_valid(self):
        commit = "sha-release-505"
        evidence = {
            "commit_sha": commit,
            "evidence_commit_sha": commit,
            "ci_passed": True,
            "qa_signed_off": True,
            "unresolved_high_findings": False,
            "advisory_warnings_count": 0
        }
        approvals = [
            {"stage": "agent_1_review", "decision": "approve", "role": "tech_lead", "commit_sha": commit},
            {"stage": "agent_2_test_plan", "decision": "approve", "role": "developer", "commit_sha": commit},
            {"stage": "agent_3_qa_plan", "decision": "approve", "role": "qa_lead", "commit_sha": commit},
        ]
        summary = release_evidence_summary(evidence, candidate_commit=commit, approvals=approvals)
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(len(summary["blockers"]), 0)

    def test_blocked_when_commit_sha_mismatch(self):
        evidence = {
            "commit_sha": "sha-target-1",
            "evidence_commit_sha": "sha-stale-2",
            "ci_passed": True,
            "qa_signed_off": True,
            "unresolved_high_findings": False
        }
        summary = release_evidence_summary(evidence, candidate_commit="sha-target-1")
        self.assertEqual(summary["status"], "BLOCKED")
        self.assertTrue(any("mismatch" in b.lower() for b in summary["blockers"]))

    def test_blocked_when_ci_or_qa_fails(self):
        commit = "sha-606"
        evidence = {
            "commit_sha": commit,
            "evidence_commit_sha": commit,
            "ci_passed": False,
            "qa_signed_off": False
        }
        summary = release_evidence_summary(evidence, candidate_commit=commit)
        self.assertEqual(summary["status"], "BLOCKED")
        self.assertTrue(any("ci" in b.lower() for b in summary["blockers"]))

    def test_needs_human_review_when_advisory_warnings_present(self):
        commit = "sha-707"
        evidence = {
            "commit_sha": commit,
            "evidence_commit_sha": commit,
            "ci_passed": True,
            "qa_signed_off": True,
            "unresolved_high_findings": False,
            "advisory_warnings_count": 2
        }
        approvals = [
            {"stage": "agent_1_review", "decision": "approve", "role": "tech_lead", "commit_sha": commit},
            {"stage": "agent_2_test_plan", "decision": "approve", "role": "developer", "commit_sha": commit},
            {"stage": "agent_3_qa_plan", "decision": "approve", "role": "qa_lead", "commit_sha": commit},
        ]
        summary = release_evidence_summary(evidence, candidate_commit=commit, approvals=approvals)
        self.assertEqual(summary["status"], "NEEDS_HUMAN_REVIEW")
        self.assertTrue(len(summary["warnings"]) > 0)


class TestWorkflowLazyExecutionAndAudit(unittest.TestCase):
    """Tests for lazy orchestrator, pipeline halting, and audit integrity."""

    def test_stage_1_rejection_halts_immediately_without_running_later_stages(self):
        visited_stages = []

        def reject_stage_1(stage, artifact, commit_sha):
            visited_stages.append(stage)
            return {
                "stage": stage,
                "decision": "reject" if stage == "agent_1_review" else "approve",
                "role": "tech_lead",
                "approver_name": "Tech Lead",
                "timestamp_utc": "2026-10-21T00:00:00Z",
                "commit_sha": commit_sha,
                "artifact_sha256": compute_sha256(artifact),
                "reason": "Security vulnerability detected"
            }

        report = run_workflow(
            pr={"pr_id": "PR-HALT-1", "commit_sha": "sha-halt"},
            requirements={"acceptance_criteria": []},
            approval_fn=reject_stage_1
        )
        self.assertEqual(report["final_status"], "STOPPED_AT_HITL_REJECTION")
        self.assertEqual(report["stopped_after_stage"], "agent_1_review")
        self.assertEqual(visited_stages, ["agent_1_review"])
        self.assertEqual(len(report["stages"]), 1)

    def test_stage_2_rejection_halts_before_stage_3_and_4(self):
        visited_stages = []

        def reject_stage_2(stage, artifact, commit_sha):
            visited_stages.append(stage)
            decision = "reject" if stage == "agent_2_test_plan" else "approve"
            return {
                "stage": stage,
                "decision": decision,
                "role": "developer",
                "approver_name": "Dev",
                "timestamp_utc": "2026-10-21T00:00:00Z",
                "commit_sha": commit_sha,
                "artifact_sha256": compute_sha256(artifact),
                "reason": "Test plan rejected"
            }

        report = run_workflow(
            pr={"pr_id": "PR-HALT-2", "commit_sha": "sha-halt-2"},
            requirements={"acceptance_criteria": []},
            approval_fn=reject_stage_2
        )
        self.assertEqual(report["final_status"], "STOPPED_AT_HITL_REJECTION")
        self.assertEqual(report["stopped_after_stage"], "agent_2_test_plan")
        self.assertEqual(visited_stages, ["agent_1_review", "agent_2_test_plan"])
        self.assertEqual(len(report["stages"]), 2)


class TestSchemaValidation(unittest.TestCase):
    """Tests for strict schema contracts and tamper prevention."""

    def test_invalid_finding_severity_raises(self):
        with self.assertRaises(ValidationError):
            f = Finding(
                finding_id="F-1",
                category="test",
                severity="SUPER_EXTREME",  # Invalid!
                confidence="high",
                summary="test",
                evidence="test",
                explanation="test",
                recommendation="test",
                confirmed_by_deterministic_tool=True,
                source_tool="test"
            )
            f.validate()

    def test_invalid_approval_record_raises(self):
        with self.assertRaises(ValidationError):
            rec = ApprovalRecord(
                stage="invalid_stage",
                decision="maybe",
                role="unknown",
                approver_name="anon",
                timestamp_utc="",
                commit_sha="",
                artifact_sha256="",
                reason=""
            )
            rec.validate()


if __name__ == "__main__":
    unittest.main()
