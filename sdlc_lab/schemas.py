"""Strict data schemas and validation contracts for AuctionNow SDLC Lab.

Every stage artifact and HITL approval record must satisfy these contracts.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional


class ValidationError(Exception):
    """Raised when an artifact or approval violates its schema contract."""
    pass


def compute_sha256(value: Any) -> str:
    """Compute deterministic SHA-256 digest of any JSON-serializable object."""
    encoded = json.dumps(value, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# -------------------------------------------------------------------------
# Agent 1 Models: Code Quality & Security Review
# -------------------------------------------------------------------------

@dataclass
class Finding:
    finding_id: str
    category: str
    severity: str  # critical, high, medium, low, info
    confidence: str  # high, medium, low
    summary: str
    evidence: str
    explanation: str
    recommendation: str
    confirmed_by_deterministic_tool: bool
    source_tool: str  # e.g., 'gitleaks', 'semgrep', 'osv-scanner', 'ruff', 'llm_advisory'
    file_path: Optional[str] = None
    line_number: Optional[int] = None

    def validate(self) -> None:
        if not self.finding_id or not isinstance(self.finding_id, str):
            raise ValidationError("Finding must have a non-empty string 'finding_id'")
        valid_severities = {"critical", "high", "medium", "low", "info"}
        if self.severity.lower() not in valid_severities:
            raise ValidationError(f"Invalid severity '{self.severity}'. Must be one of {valid_severities}")
        valid_confidences = {"high", "medium", "low"}
        if self.confidence.lower() not in valid_confidences:
            raise ValidationError(f"Invalid confidence '{self.confidence}'. Must be one of {valid_confidences}")
        if not isinstance(self.confirmed_by_deterministic_tool, bool):
            raise ValidationError("confirmed_by_deterministic_tool must be a boolean")
        if self.line_number is not None and (not isinstance(self.line_number, int) or self.line_number < 1):
            raise ValidationError("line_number must be a positive integer if provided")


@dataclass
class Stage1ReviewArtifact:
    agent: str
    stage: str
    pr_id: str
    commit_sha: str
    timestamp_utc: str
    summary: str
    findings: List[Finding]
    tools_executed: List[str]
    confirmed_findings_count: int
    unconfirmed_findings_count: int
    policy_blocked: bool
    mode: str = "MOCK_ONLY"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["findings"] = [asdict(f) if isinstance(f, Finding) else f for f in self.findings]
        return d

    def validate(self) -> None:
        if self.agent != "engineering_quality_security_reviewer":
            raise ValidationError(f"Invalid agent name '{self.agent}' for Stage 1")
        if self.stage != "agent_1_review":
            raise ValidationError(f"Invalid stage '{self.stage}' for Stage 1")
        if not self.pr_id or not self.commit_sha:
            raise ValidationError("Stage 1 artifact must bind to non-empty pr_id and commit_sha")
        for f in self.findings:
            if isinstance(f, Finding):
                f.validate()
            elif isinstance(f, dict):
                Finding(**f).validate()


# -------------------------------------------------------------------------
# Agent 2 Models: SDET Test Proposals
# -------------------------------------------------------------------------

@dataclass
class TestCaseProposal:
    id: str
    category: str  # positive, negative, boundary, authorization, failure, regression, platform
    title: str
    target_surface: str  # backend, mobile, api, ui
    preconditions: List[str]
    steps: List[str]
    expected_result: str
    priority: str  # P1, P2, P3
    rationale: str
    requirement_ids: List[str]
    status: str = "proposed_not_executed"

    def validate(self) -> None:
        valid_categories = {"positive", "negative", "boundary", "authorization", "failure", "regression", "platform"}
        if self.category.lower() not in valid_categories:
            raise ValidationError(f"Invalid test category '{self.category}'. Must be one of {valid_categories}")
        valid_priorities = {"P1", "P2", "P3"}
        if self.priority.upper() not in valid_priorities:
            raise ValidationError(f"Invalid priority '{self.priority}'. Must be one of {valid_priorities}")
        if self.status != "proposed_not_executed":
            raise ValidationError(f"Agent 2 proposals must have status 'proposed_not_executed', got '{self.status}'")
        if not self.steps or not self.expected_result:
            raise ValidationError(f"Test proposal {self.id} must include non-empty steps and expected_result")


@dataclass
class ClarificationRequest:
    id: str
    topic: str
    question: str
    impact: str
    suggested_default: Optional[str] = None


@dataclass
class Stage2TestPlanArtifact:
    agent: str
    stage: str
    pr_id: str
    commit_sha: str
    timestamp_utc: str
    summary: str
    test_cases: List[TestCaseProposal]
    clarification_requests: List[ClarificationRequest]
    warning: str = "Proposed tests only; not executed and no code was changed."
    mode: str = "MOCK_ONLY"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["test_cases"] = [asdict(t) if isinstance(t, TestCaseProposal) else t for t in self.test_cases]
        d["clarification_requests"] = [asdict(c) if isinstance(c, ClarificationRequest) else c for c in self.clarification_requests]
        return d

    def validate(self) -> None:
        if self.agent != "sdet_test_planner":
            raise ValidationError(f"Invalid agent name '{self.agent}' for Stage 2")
        if self.stage != "agent_2_test_plan":
            raise ValidationError(f"Invalid stage '{self.stage}' for Stage 2")
        if not self.pr_id or not self.commit_sha:
            raise ValidationError("Stage 2 artifact must bind to non-empty pr_id and commit_sha")
        for tc in self.test_cases:
            if isinstance(tc, TestCaseProposal):
                tc.validate()
            elif isinstance(tc, dict):
                TestCaseProposal(**tc).validate()


# -------------------------------------------------------------------------
# Agent 3 Models: QA Director Manual Test Matrix
# -------------------------------------------------------------------------

@dataclass
class ManualTestMatrixRow:
    scenario_id: str
    priority: str  # P1, P2, P3
    scenario: str
    target_surface: str
    preconditions: List[str]
    manual_steps: List[str]
    expected_result: str
    owner: str  # qa_lead, qa_engineer_mobile, qa_engineer_backend
    automation_evidence: str
    automated_coverage_confirmed: bool
    qa_action: str

    def validate(self) -> None:
        if not self.scenario_id or not self.scenario:
            raise ValidationError("Matrix row must have scenario_id and scenario description")
        if self.automated_coverage_confirmed and "None" in self.automation_evidence:
            raise ValidationError("Contradiction: automated_coverage_confirmed is True but evidence is None")


@dataclass
class Stage3QAPlanArtifact:
    agent: str
    stage: str
    pr_id: str
    commit_sha: str
    timestamp_utc: str
    summary: str
    manual_test_matrix: List[ManualTestMatrixRow]
    review_findings_count: int
    uncovered_scenarios_count: int
    warning: str = "No scenario is covered without named passing test evidence."
    mode: str = "MOCK_ONLY"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["manual_test_matrix"] = [asdict(r) if isinstance(r, ManualTestMatrixRow) else r for r in self.manual_test_matrix]
        return d

    def validate(self) -> None:
        if self.agent != "qa_director":
            raise ValidationError(f"Invalid agent name '{self.agent}' for Stage 3")
        if self.stage != "agent_3_qa_plan":
            raise ValidationError(f"Invalid stage '{self.stage}' for Stage 3")
        if not self.pr_id or not self.commit_sha:
            raise ValidationError("Stage 3 artifact must bind to non-empty pr_id and commit_sha")
        for r in self.manual_test_matrix:
            if isinstance(r, ManualTestMatrixRow):
                r.validate()
            elif isinstance(r, dict):
                ManualTestMatrixRow(**r).validate()


# -------------------------------------------------------------------------
# Agent 4 Models: Release & CI Evidence Gate
# -------------------------------------------------------------------------

@dataclass
class Stage4ReleaseSummaryArtifact:
    agent: str
    stage: str
    pr_id: str
    commit_sha: str
    timestamp_utc: str
    status: str  # PASS, BLOCKED, NEEDS_HUMAN_REVIEW
    summary: str
    blockers: List[str]
    warnings: List[str]
    evidence_summary: Dict[str, Any]
    decision_note: str = "Summarizes machine-readable evidence only; never merges or deploys."
    mode: str = "MOCK_ONLY"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        if self.agent != "release_ci_evidence_summarizer":
            raise ValidationError(f"Invalid agent name '{self.agent}' for Stage 4")
        if self.stage != "agent_4_release_summary":
            raise ValidationError(f"Invalid stage '{self.stage}' for Stage 4")
        valid_statuses = {"PASS", "BLOCKED", "NEEDS_HUMAN_REVIEW"}
        if self.status not in valid_statuses:
            raise ValidationError(f"Invalid status '{self.status}'. Must be one of {valid_statuses}")
        if self.status == "PASS" and self.blockers:
            raise ValidationError(f"Inconsistent release state: status is PASS but blockers exist: {self.blockers}")
        if not self.pr_id or not self.commit_sha:
            raise ValidationError("Stage 4 artifact must bind to non-empty pr_id and commit_sha")


# -------------------------------------------------------------------------
# HITL Approval Record
# -------------------------------------------------------------------------

@dataclass
class ApprovalRecord:
    stage: str
    decision: str  # approve, reject
    role: str  # tech_lead, developer, qa_lead, release_manager
    approver_name: str
    timestamp_utc: str
    commit_sha: str
    artifact_sha256: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def validate(self) -> None:
        valid_stages = {"agent_1_review", "agent_2_test_plan", "agent_3_qa_plan", "agent_4_release_summary"}
        if self.stage not in valid_stages:
            raise ValidationError(f"Invalid approval stage '{self.stage}'")
        if self.decision not in {"approve", "reject"}:
            raise ValidationError(f"Decision must be 'approve' or 'reject', got '{self.decision}'")
        valid_roles = {"tech_lead", "developer", "qa_lead", "release_manager", "local_demo_operator"}
        if self.role not in valid_roles:
            raise ValidationError(f"Role must be one of {valid_roles}, got '{self.role}'")
        if not self.commit_sha or not self.artifact_sha256:
            raise ValidationError("ApprovalRecord must specify commit_sha and artifact_sha256")


# -------------------------------------------------------------------------
# Dispatch Validator
# -------------------------------------------------------------------------

def validate_stage_artifact(stage_name: str, artifact: Dict[str, Any]) -> None:
    """Validate any stage artifact against its required schema contract."""
    if not isinstance(artifact, dict):
        raise ValidationError(f"Artifact for {stage_name} must be a dictionary")

    if stage_name == "agent_1_review":
        findings_raw = artifact.get("findings", [])
        findings = [Finding(**f) if isinstance(f, dict) else f for f in findings_raw]
        obj = Stage1ReviewArtifact(
            agent=artifact.get("agent", ""),
            stage=artifact.get("stage", ""),
            pr_id=artifact.get("pr_id", ""),
            commit_sha=artifact.get("commit_sha", ""),
            timestamp_utc=artifact.get("timestamp_utc", ""),
            summary=artifact.get("summary", ""),
            findings=findings,
            tools_executed=artifact.get("tools_executed", []),
            confirmed_findings_count=artifact.get("confirmed_findings_count", 0),
            unconfirmed_findings_count=artifact.get("unconfirmed_findings_count", 0),
            policy_blocked=artifact.get("policy_blocked", False),
        )
        obj.validate()

    elif stage_name == "agent_2_test_plan":
        tc_raw = artifact.get("test_cases", [])
        test_cases = [TestCaseProposal(**t) if isinstance(t, dict) else t for t in tc_raw]
        cr_raw = artifact.get("clarification_requests", [])
        clarifications = [ClarificationRequest(**c) if isinstance(c, dict) else c for c in cr_raw]
        obj = Stage2TestPlanArtifact(
            agent=artifact.get("agent", ""),
            stage=artifact.get("stage", ""),
            pr_id=artifact.get("pr_id", ""),
            commit_sha=artifact.get("commit_sha", ""),
            timestamp_utc=artifact.get("timestamp_utc", ""),
            summary=artifact.get("summary", ""),
            test_cases=test_cases,
            clarification_requests=clarifications,
            warning=artifact.get("warning", ""),
        )
        obj.validate()

    elif stage_name == "agent_3_qa_plan":
        matrix_raw = artifact.get("manual_test_matrix", [])
        matrix = [ManualTestMatrixRow(**m) if isinstance(m, dict) else m for m in matrix_raw]
        obj = Stage3QAPlanArtifact(
            agent=artifact.get("agent", ""),
            stage=artifact.get("stage", ""),
            pr_id=artifact.get("pr_id", ""),
            commit_sha=artifact.get("commit_sha", ""),
            timestamp_utc=artifact.get("timestamp_utc", ""),
            summary=artifact.get("summary", ""),
            manual_test_matrix=matrix,
            review_findings_count=artifact.get("review_findings_count", 0),
            uncovered_scenarios_count=artifact.get("uncovered_scenarios_count", 0),
            warning=artifact.get("warning", ""),
        )
        obj.validate()

    elif stage_name == "agent_4_release_summary":
        obj = Stage4ReleaseSummaryArtifact(
            agent=artifact.get("agent", ""),
            stage=artifact.get("stage", ""),
            pr_id=artifact.get("pr_id", ""),
            commit_sha=artifact.get("commit_sha", ""),
            timestamp_utc=artifact.get("timestamp_utc", ""),
            status=artifact.get("status", ""),
            summary=artifact.get("summary", ""),
            blockers=artifact.get("blockers", []),
            warnings=artifact.get("warnings", []),
            evidence_summary=artifact.get("evidence_summary", {}),
            decision_note=artifact.get("decision_note", ""),
        )
        obj.validate()
    else:
        raise ValidationError(f"Unknown stage name: {stage_name}")
