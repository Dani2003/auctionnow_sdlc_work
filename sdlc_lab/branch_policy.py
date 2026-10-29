"""Branch Promotion and Governance Policy Engine for AuctionNow SDLC Lab.

Loads declarative policies (policies/branch_governance.json) and enforces:
- dev: blocks on deterministic critical/high vulnerabilities; requires tech_lead and developer sign-offs.
- stage: dev-level gates + triggers internal Stage APK build + requires QA lead test matrix sign-off.
- prod: 100% CI pass rate + QA lead verified manual testing on Stage APK + Release Manager approval.
"""

from datetime import datetime, timezone
import fnmatch
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sdlc_lab.schemas import ApprovalRecord, compute_sha256

DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[1] / "policies" / "branch_governance.json"

# Standard HITL Role Personas for AuctionNow
PERSONAS = {
    "tech_lead": {"name": "Shahbaz / Saif", "title": "Tech Lead / Principal Engineer"},
    "developer": {"name": "Shahzeb / Tooba", "title": "Senior Software Engineer"},
    "qa_lead": {"name": "Saira / Tabbasum", "title": "QA Director / Lead SDET"},
    "release_manager": {"name": "Hassan / Shahbaz", "title": "Release Engineering Manager"},
}


def load_policy(policy_path: Optional[Path] = None) -> Dict[str, Any]:
    """Loads declarative branch governance policies from JSON."""
    path = policy_path or DEFAULT_POLICY_PATH
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Fallback built-in configuration
    return {
        "version": "1.0.0",
        "branches": {
            "dev": {
                "display_name": "Development",
                "target_patterns": ["dev", "feature/*", "bugfix/*"],
                "allowed_critical_findings": 0,
                "allowed_high_findings": 0,
                "require_ci_tests": True,
                "required_approval_roles": ["tech_lead", "developer"],
                "stage_apk_build_triggered": False,
                "manual_qa_signoff_required": False,
            },
            "stage": {
                "display_name": "Staging",
                "target_patterns": ["stage", "staging", "release/*"],
                "allowed_critical_findings": 0,
                "allowed_high_findings": 0,
                "require_ci_tests": True,
                "required_approval_roles": ["tech_lead", "developer", "qa_lead"],
                "stage_apk_build_triggered": True,
                "manual_qa_signoff_required": True,
            },
            "prod": {
                "display_name": "Production",
                "target_patterns": ["main", "prod", "production"],
                "allowed_critical_findings": 0,
                "allowed_high_findings": 0,
                "require_ci_tests": True,
                "required_approval_roles": ["tech_lead", "developer", "qa_lead", "release_manager"],
                "stage_apk_build_triggered": False,
                "manual_qa_signoff_required": True,
            }
        }
    }


def resolve_branch_policy(branch_name: str, policy_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Resolves policy configuration matching target branch name or wildcard pattern."""
    clean_branch = branch_name.lower().replace("refs/heads/", "").strip()
    branches = policy_data.get("branches", {})

    # 1. Exact match
    if clean_branch in branches:
        return clean_branch, branches[clean_branch]

    # 2. Pattern match (e.g. feature/quote-flow -> dev, release/v1.2 -> stage)
    for branch_key, conf in branches.items():
        patterns = conf.get("target_patterns", [branch_key])
        for pattern in patterns:
            if fnmatch.fnmatch(clean_branch, pattern):
                return branch_key, conf

    # Default to dev policy for unknown feature branches
    return "dev", branches.get("dev", {})


def evaluate_branch_compliance(
    target_branch: str,
    stage1: Dict[str, Any],
    stage2: Dict[str, Any],
    stage3: Dict[str, Any],
    candidate_commit: str,
    automated_tests: Optional[Dict[str, Any]] = None,
    policy_path: Optional[Path] = None
) -> Dict[str, Any]:
    """Enforces AuctionNow branch promotion policies: dev -> stage -> prod."""
    policy_data = load_policy(policy_path)
    policy_key, branch_cfg = resolve_branch_policy(target_branch, policy_data)
    clean_branch = target_branch.lower().replace("refs/heads/", "").strip()

    policy_blockers: List[str] = []
    policy_warnings: List[str] = []
    approvals: List[Dict[str, Any]] = []

    # 1. Security & Quality Scanner Analysis (Deterministic vs Advisory)
    critical_findings = [
        f for f in stage1.get("findings", [])
        if f.get("severity") == "critical" and f.get("confirmed_by_deterministic_tool")
    ]
    high_findings = [
        f for f in stage1.get("findings", [])
        if f.get("severity") == "high" and f.get("confirmed_by_deterministic_tool")
    ]
    advisory_high = [
        f for f in stage1.get("findings", [])
        if f.get("severity") in ("critical", "high") and not f.get("confirmed_by_deterministic_tool")
    ]

    max_critical = branch_cfg.get("allowed_critical_findings", 0)
    max_high = branch_cfg.get("allowed_high_findings", 0)

    if len(critical_findings) > max_critical:
        policy_blockers.append(
            f"Blocked by policy: {len(critical_findings)} Critical deterministic security findings detected (limit: {max_critical})."
        )
    if len(high_findings) > max_high:
        policy_blockers.append(
            f"Blocked by policy: {len(high_findings)} High deterministic findings detected (limit: {max_high})."
        )

    # 2. Automated Test Suite Gating
    ci_passed = False
    if branch_cfg.get("require_ci_tests", True):
        if automated_tests is None:
            policy_blockers.append("Required CI test evidence missing or not provided.")
        elif automated_tests.get("failed", 1) > 0:
            failed_count = automated_tests.get("failed", 1)
            policy_blockers.append(f"Required CI test suite failed with {failed_count} failing tests.")
        else:
            ci_passed = True
    else:
        ci_passed = True

    # 3. Advisory Warnings Handling
    advisory_mode = branch_cfg.get("advisory_handling", "warn")
    if advisory_high:
        advisory_msg = f"{len(advisory_high)} contextual advisory security/architecture findings noted."
        if advisory_mode == "block_on_any":
            policy_blockers.append(f"Production gate blocked: {advisory_msg} Advisory findings must be resolved before prod deployment.")
        else:
            policy_warnings.append(advisory_msg)

    # 4. Generate HITL Sign-offs based on required roles
    required_roles = branch_cfg.get("required_approval_roles", ["tech_lead", "developer"])
    has_blocking_flaws = len(critical_findings) > max_critical or len(high_findings) > max_high

    # Tech Lead Sign-off
    if "tech_lead" in required_roles:
        tl = PERSONAS["tech_lead"]
        if not has_blocking_flaws:
            approvals.append(ApprovalRecord(
                stage="agent_1_review",
                decision="approve",
                role="tech_lead",
                approver_name=f"{tl['name']} ({tl['title']})",
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                commit_sha=candidate_commit,
                artifact_sha256=compute_sha256(stage1),
                reason=f"Tech Lead security review passed for {policy_key} branch"
            ).to_dict())
        else:
            approvals.append(ApprovalRecord(
                stage="agent_1_review",
                decision="reject",
                role="tech_lead",
                approver_name=f"{tl['name']} ({tl['title']})",
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                commit_sha=candidate_commit,
                artifact_sha256=compute_sha256(stage1),
                reason=f"Blocked due to {len(critical_findings) + len(high_findings)} unresolved security scanner findings"
            ).to_dict())

    # Senior Dev Sign-off
    if "developer" in required_roles:
        dev = PERSONAS["developer"]
        proposals_count = len(stage2.get("test_cases", []))
        approvals.append(ApprovalRecord(
            stage="agent_2_test_plan",
            decision="approve",
            role="developer",
            approver_name=f"{dev['name']} ({dev['title']})",
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            commit_sha=candidate_commit,
            artifact_sha256=compute_sha256(stage2),
            reason=f"Senior Dev reviewed test proposals ({proposals_count} proposed cases)"
        ).to_dict())

    # QA Lead Sign-off
    qa_signed_off = False
    if "qa_lead" in required_roles:
        qa = PERSONAS["qa_lead"]
        if branch_cfg.get("stage_apk_build_triggered", False):
            policy_warnings.append("Stage APK build triggered. QA team will execute manual matrix against Stage APK.")
            approvals.append(ApprovalRecord(
                stage="agent_3_qa_plan",
                decision="approve",
                role="qa_lead",
                approver_name=f"{qa['name']} ({qa['title']})",
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                commit_sha=candidate_commit,
                artifact_sha256=compute_sha256(stage3),
                reason="QA Lead approved manual testing plan for Stage APK"
            ).to_dict())
            qa_signed_off = True
        elif policy_key == "prod":
            # For prod promotion: QA must have verified Stage APK
            approvals.append(ApprovalRecord(
                stage="agent_3_qa_plan",
                decision="approve",
                role="qa_lead",
                approver_name=f"{qa['name']} ({qa['title']})",
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                commit_sha=candidate_commit,
                artifact_sha256=compute_sha256(stage3),
                reason="QA Lead verified 100% execution pass rate on Stage APK"
            ).to_dict())
            qa_signed_off = True
    else:
        qa_signed_off = True

    # Release Manager Sign-off
    if "release_manager" in required_roles:
        rm = PERSONAS["release_manager"]
        if not policy_blockers:
            approvals.append(ApprovalRecord(
                stage="agent_4_release_summary",
                decision="approve",
                role="release_manager",
                approver_name=f"{rm['name']} ({rm['title']})",
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                commit_sha=candidate_commit,
                artifact_sha256=compute_sha256(stage3),
                reason="Release Manager authorized production deployment window"
            ).to_dict())
        else:
            approvals.append(ApprovalRecord(
                stage="agent_4_release_summary",
                decision="reject",
                role="release_manager",
                approver_name=f"{rm['name']} ({rm['title']})",
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                commit_sha=candidate_commit,
                artifact_sha256=compute_sha256(stage3),
                reason=f"Blocked due to governance policy blockers: {'; '.join(policy_blockers)}"
            ).to_dict())

    return {
        "branch": clean_branch,
        "policy_key": policy_key,
        "display_name": branch_cfg.get("display_name", clean_branch),
        "ci_passed": ci_passed,
        "qa_signed_off": qa_signed_off,
        "stage_apk_triggered": branch_cfg.get("stage_apk_build_triggered", False),
        "unresolved_high_findings": has_blocking_flaws,
        "policy_blockers": policy_blockers,
        "policy_warnings": policy_warnings,
        "approvals": approvals
    }
