import unittest
from sdlc_lab.agents import code_quality_security_review, sdet_test_plan, qa_directives, release_evidence_summary
from sdlc_lab.workflow import run_workflow


class AgentTests(unittest.TestCase):
    def test_mock_reviewer_flags_auth_todo(self):
        out = code_quality_security_review({"diff_excerpt": "TODO: add authorization"})
        self.assertTrue(any(x["category"] == "authorization_gap" for x in out["findings"]))
        self.assertEqual(out["mode"], "MOCK_ONLY")

    def test_tests_are_proposals_not_execution(self):
        out = sdet_test_plan({}, {"acceptance_criteria": ["User can save draft"]})
        self.assertTrue(all(x["status"] == "proposed_not_executed" for x in out["test_cases"]))

    def test_qa_does_not_claim_coverage(self):
        plan = sdet_test_plan({}, {"acceptance_criteria": ["A works"]})
        qa = qa_directives({}, plan, {"findings": []})
        self.assertTrue(all("None" in x["automation_evidence"] for x in qa["manual_test_matrix"]))

    def test_missing_release_evidence_blocks(self):
        self.assertEqual(release_evidence_summary({})["status"], "BLOCKED")

    def test_rejection_stops_workflow(self):
        approvals = []
        def reject_first(stage, artifact):
            decision = {"stage": stage, "decision": "reject", "artifact_sha256": "test"}
            approvals.append(decision)
            return decision
        report = run_workflow({"pr_id": "P", "commit_sha": "abc"}, {"acceptance_criteria": []}, reject_first, {})
        self.assertEqual(report["final_status"], "STOPPED_AT_HITL_REJECTION")
        self.assertEqual(len(report["stages"]), 1)


if __name__ == "__main__":
    unittest.main()
