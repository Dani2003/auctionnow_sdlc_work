"""Deterministic Orchestrator with Lazy Execution and Role-Based HITL Governance.

Orchestrates the 4-stage SDLC workflow:
1. Engineering Quality & Security Reviewer (Tech Lead approval)
2. SDET Test Planner (Senior Dev approval)
3. QA Director (QA Lead approval)
4. Release & CI Evidence Summarizer (Release Manager approval)

Guarantees:
- Lazy execution: downstream stages are never run if an upstream stage is rejected.
- Auditability: each approval is bound to role, commit SHA, and artifact digest.
- No autonomous merge or deploy actions.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .agents import (
    code_quality_security_review,
    qa_directives,
    release_evidence_summary,
    sdet_test_plan,
)
from .schemas import (
    ApprovalRecord,
    compute_sha256,
    validate_stage_artifact,
)

ROOT = Path(__file__).resolve().parents[1]

STAGE_ROLES = {
    "agent_1_review": {"role": "tech_lead", "default_name": "Shahbaz / Saif (Tech Lead)"},
    "agent_2_test_plan": {"role": "developer", "default_name": "Shahzeb / Tooba (Senior Dev)"},
    "agent_3_qa_plan": {"role": "qa_lead", "default_name": "Saira / Tabbasum (QA Lead)"},
    "agent_4_release_summary": {"role": "release_manager", "default_name": "Hassan / Shahbaz (Release Manager)"},
}


def interactive_approval(stage: str, artifact: Dict[str, Any], candidate_commit: str) -> Dict[str, Any]:
    """Interactive CLI HITL checkpoint with role simulation."""
    meta = STAGE_ROLES.get(stage, {"role": "local_demo_operator", "default_name": "Operator"})
    role = meta["role"]
    approver = meta["default_name"]
    art_hash = compute_sha256(artifact)

    print(f"\n========================================================")
    print(f" HITL CHECKPOINT: {stage.upper()}")
    print(f" Assigned Role:  {approver} [{role}]")
    print(f" Candidate SHA:  {candidate_commit}")
    print(f" Artifact Hash:  {art_hash}")
    print(f" Summary:        {artifact.get('summary')}")
    print(f"========================================================")

    answer = input(f"Approve as {role}? [y/N]: ").strip().lower()
    decision = "approve" if answer in ("y", "yes") else "reject"
    reason = (
        f"Verified and approved by {approver} for candidate commit {candidate_commit}"
        if decision == "approve"
        else f"Rejected by {approver} during HITL inspection"
    )

    rec = ApprovalRecord(
        stage=stage,
        decision=decision,
        role=role,
        approver_name=approver,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        commit_sha=candidate_commit,
        artifact_sha256=art_hash,
        reason=reason
    )
    rec.validate()
    return rec.to_dict()


def simulated_approval(stage: str, artifact: Dict[str, Any], candidate_commit: str) -> Dict[str, Any]:
    """Automated programmatic approval for testing and non-interactive demo runs."""
    meta = STAGE_ROLES.get(stage, {"role": "local_demo_operator", "default_name": "Automated Tester"})
    role = meta["role"]
    approver = meta["default_name"]
    art_hash = compute_sha256(artifact)

    rec = ApprovalRecord(
        stage=stage,
        decision="approve",
        role=role,
        approver_name=approver,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        commit_sha=candidate_commit,
        artifact_sha256=art_hash,
        reason=f"Automated verification approved for {role} on commit {candidate_commit}"
    )
    rec.validate()
    return rec.to_dict()


def invoke_approval(approval_fn: Callable, stage: str, artifact: Dict[str, Any], commit_sha: str) -> Dict[str, Any]:
    """Invokes approval callback supporting both (stage, artifact, commit_sha) and legacy (stage, artifact)."""
    import inspect
    sig = inspect.signature(approval_fn)
    if len(sig.parameters) >= 3:
        return approval_fn(stage, artifact, commit_sha)
    return approval_fn(stage, artifact)


def run_workflow(
    pr: Dict[str, Any],
    requirements: Dict[str, Any],
    approval_fn: Callable = interactive_approval,
    scanner_reports: Optional[Dict[str, Any]] = None,
    automated_test_results: Optional[Dict[str, Any]] = None,
    evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Executes the 4 SDLC stages lazily with strict HITL approval gates."""
    pr_id = pr.get("pr_id", "SYNTHETIC-PR-000")
    commit_sha = pr.get("commit_sha", "unknown-commit-sha")

    report: Dict[str, Any] = {
        "workflow_version": "1.0.0",
        "run_mode": "AUCTIONNOW_SDLC_LAB",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "pr": {
            "pr_id": pr_id,
            "commit_sha": commit_sha,
            "title": pr.get("title", "Untitled PR"),
            "changed_files": pr.get("changed_files", []),
        },
        "stages": [],
        "approvals": [],
        "final_status": "IN_PROGRESS",
    }

    # -------------------------------------------------------------
    # Stage 1: Quality & Security Reviewer
    # -------------------------------------------------------------
    stage1_artifact = code_quality_security_review(
        pr=pr, scanner_reports=scanner_reports, candidate_commit=commit_sha
    )
    validate_stage_artifact("agent_1_review", stage1_artifact)
    report["stages"].append({"stage": "agent_1_review", "artifact": stage1_artifact})

    app1 = invoke_approval(approval_fn, "agent_1_review", stage1_artifact, commit_sha)
    report["approvals"].append(app1)
    if app1.get("decision") != "approve":
        report["final_status"] = "STOPPED_AT_HITL_REJECTION"
        report["stopped_after_stage"] = "agent_1_review"
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        return report

    # -------------------------------------------------------------
    # Stage 2: SDET Test Planner (Lazy Execution: only runs after Stage 1 approval)
    # -------------------------------------------------------------
    stage2_artifact = sdet_test_plan(
        pr=pr, requirements=requirements, review=stage1_artifact, candidate_commit=commit_sha
    )
    validate_stage_artifact("agent_2_test_plan", stage2_artifact)
    report["stages"].append({"stage": "agent_2_test_plan", "artifact": stage2_artifact})

    app2 = invoke_approval(approval_fn, "agent_2_test_plan", stage2_artifact, commit_sha)
    report["approvals"].append(app2)
    if app2.get("decision") != "approve":
        report["final_status"] = "STOPPED_AT_HITL_REJECTION"
        report["stopped_after_stage"] = "agent_2_test_plan"
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        return report

    # -------------------------------------------------------------
    # Stage 3: QA Director (Lazy Execution: only runs after Stage 2 approval)
    # -------------------------------------------------------------
    stage3_artifact = qa_directives(
        pr=pr,
        test_plan=stage2_artifact,
        review=stage1_artifact,
        automated_test_results=automated_test_results,
        candidate_commit=commit_sha,
    )
    validate_stage_artifact("agent_3_qa_plan", stage3_artifact)
    report["stages"].append({"stage": "agent_3_qa_plan", "artifact": stage3_artifact})

    app3 = invoke_approval(approval_fn, "agent_3_qa_plan", stage3_artifact, commit_sha)
    report["approvals"].append(app3)
    if app3.get("decision") != "approve":
        report["final_status"] = "STOPPED_AT_HITL_REJECTION"
        report["stopped_after_stage"] = "agent_3_qa_plan"
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        return report

    # -------------------------------------------------------------
    # Stage 4: Release & CI Evidence Gate (Lazy Execution)
    # -------------------------------------------------------------
    ev = evidence or {
        "pr_id": pr_id,
        "commit_sha": commit_sha,
        "evidence_commit_sha": commit_sha,
        "ci_passed": False,
        "qa_signed_off": False,
        "unresolved_high_findings": stage1_artifact.get("policy_blocked", False),
    }

    stage4_artifact = release_evidence_summary(
        evidence=ev,
        candidate_commit=commit_sha,
        pr_id=pr_id,
        approvals=report["approvals"],
    )
    validate_stage_artifact("agent_4_release_summary", stage4_artifact)
    report["stages"].append({"stage": "agent_4_release_summary", "artifact": stage4_artifact})

    app4 = invoke_approval(approval_fn, "agent_4_release_summary", stage4_artifact, commit_sha)
    report["approvals"].append(app4)
    if app4.get("decision") != "approve":
        report["final_status"] = "STOPPED_AT_HITL_REJECTION"
        report["stopped_after_stage"] = "agent_4_release_summary"
        report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        return report

    report["final_status"] = stage4_artifact["status"]
    report["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    return report


def run_demo(interactive: bool = True):
    """Loads fixtures, runs the end-to-end workflow, and writes latest_run.json."""
    pr_path = ROOT / "fixtures/sample_pr.json"
    reqs_path = ROOT / "fixtures/sample_requirements.json"
    scanner_path = ROOT / "fixtures/sample_scanner_reports.json"
    ci_path = ROOT / "fixtures/sample_ci_evidence.json"

    pr = json.loads(pr_path.read_text(encoding="utf-8"))
    reqs = json.loads(reqs_path.read_text(encoding="utf-8"))
    scanners = json.loads(scanner_path.read_text(encoding="utf-8")) if scanner_path.exists() else None
    ci_evidence = json.loads(ci_path.read_text(encoding="utf-8")) if ci_path.exists() else None

    approval_fn = interactive_approval if interactive else simulated_approval

    print("=================================================================")
    print(" AuctionNow SDLC Lab - Realistic AI-Assisted Governance Demo")
    print(f" Target PR: {pr['pr_id']} | Commit: {pr['commit_sha'][:10]}")
    print("=================================================================")

    report = run_workflow(
        pr=pr,
        requirements=reqs,
        approval_fn=approval_fn,
        scanner_reports=scanners,
        automated_test_results=ci_evidence.get("automated_test_results") if ci_evidence else None,
        evidence=ci_evidence.get("release_evidence") if ci_evidence else None,
    )

    out = ROOT / "artifacts/latest_run.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n-----------------------------------------------------------------")
    print(f" Workflow Finished. Final Gate Status: {report['final_status']}")
    print(f" Full Machine-Readable Audit Report Saved: {out}")
    print("-----------------------------------------------------------------")
    return report
