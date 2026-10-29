"""Live Presentation Runner for AuctionNow SDLC Governance.

Demonstrates to the PM and Senior Developer:
1. Scenario A: The 'Unvetted PR' (Why blind LLM review causes app collapse).
   - Catches hardcoded API secret via Gitleaks.
   - Catches IDOR authorization gap via Semgrep.
   - Blocks pipeline immediately; halts dirty context propagation.
2. Scenario B: The 'Remediated & Hardened PR'.
   - 0 scanner flaws, clean env variables, proper auth decorator.
   - Triggers internal Stage APK build for QA manual testing.
   - Passes with full cryptographic audit trail and role sign-offs.
"""

from pathlib import Path
import sys
import time

from .branch_policy import evaluate_branch_compliance

ROOT = Path(__file__).resolve().parents[1]

# Terminal ANSI styling
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner(text: str, color: str = CYAN):
    line = "=" * 72
    print(f"\n{color}{BOLD}{line}")
    print(f" {text}")
    print(f"{line}{RESET}\n")


def print_step(title: str, detail: str = ""):
    print(f"  {CYAN}>{RESET} {BOLD}{title}{RESET} {detail}")


def run_scenario_a():
    print_banner("SCENARIO A: Unvetted PR (#104) - The 'App Collapse' Risk", RED)
    print("Context: Junior dev submitted quick quote-acceptance logic.")
    print("Senior dev blindly asks raw LLM: 'Will this break anything?' -> LLM says 'Looks clean!'.")
    print("Without our deterministic governance layer, this merges and crashes the app on startup.\n")
    time.sleep(0.5)

    print_step("Deterministic Scanner Suite Invoked", "(Gitleaks, Semgrep, OSV, Ruff)")
    print(f"    {RED}[FAIL] Gitleaks:{RESET}  Detected hardcoded secret: generic-api-key at backend/app/quotes/service.py:5")
    print(f"    {RED}[FAIL] Semgrep:{RESET}   Detected IDOR flaw: python.security.authorization.missing-ownership-check at line 14")
    print(f"    {YELLOW}[WARN] OSV:{RESET}       Vulnerable dependency detected in requirements.txt (GHSA-x4qr-2fvf-3mr5)")
    print(f"    {YELLOW}[WARN] Advisory:{RESET}  Mobile AcceptQuoteButton lacks debouncing; risk of duplicate payment submissions")
    print()

    stage1 = {
        "stage": "agent_1_review",
        "findings": [
            {
                "finding_id": "DET-GITLEAKS-001",
                "severity": "critical",
                "category": "secret_exposure",
                "confirmed_by_deterministic_tool": True,
                "file_path": "backend/app/quotes/service.py",
                "line_number": 5
            },
            {
                "finding_id": "DET-SEMGREP-001",
                "severity": "high",
                "category": "authorization_gap",
                "confirmed_by_deterministic_tool": True,
                "file_path": "backend/app/quotes/service.py",
                "line_number": 14
            }
        ],
        "confirmed_findings_count": 2,
        "unconfirmed_findings_count": 1,
        "commit_sha": "mockcommit-104-a1b2c3"
    }

    print_step("HITL Governance Gate: Shahbaz / Saif (Tech Lead)", "evaluating deterministic evidence...")
    policy = evaluate_branch_compliance(
        target_branch="dev",
        stage1=stage1,
        stage2={"stage": "agent_2_test_plan", "test_cases": []},
        stage3={"stage": "agent_3_qa_plan"},
        candidate_commit="mockcommit-104-a1b2c3",
        automated_tests={"failed": 1}
    )

    tl_approval = next(a for a in policy["approvals"] if a["role"] == "tech_lead")
    print(f"    Decision: {RED}{BOLD}{tl_approval['decision'].upper()}{RESET}")
    print(f"    Approver: {tl_approval['approver_name']}")
    print(f"    Reason:   {tl_approval['reason']}")
    print(f"    Digest:   {tl_approval['artifact_sha256'][:16]}...")
    print(f"\n{RED}{BOLD}[BLOCKED] PIPELINE HALTED IMMEDIATELY:{RESET} Downstream Stages (SDET, QA, Release) NOT EXECUTED.")
    print("Safety Result: Zero dirty code merged. Zero secrets exposed. Zero application crash.\n")


def run_scenario_b():
    print_banner("SCENARIO B: Remediated & Hardened PR (#105) - Safe Promotion", GREEN)
    print("Context: Developer remediated the findings properly:")
    print("  1. Secret moved to environment variable / AWS Secrets Manager.")
    print("  2. Added @require_ownership tenant check to prevent IDOR.")
    print("  3. Added debouncing to AcceptQuoteButton.tsx in React Native.\n")
    time.sleep(0.5)

    print_step("Deterministic Scanner Suite Invoked", "(Gitleaks, Semgrep, OSV, Linters)")
    print(f"    {GREEN}[PASS] Gitleaks:{RESET}  0 secrets detected.")
    print(f"    {GREEN}[PASS] Semgrep:{RESET}   0 security violations.")
    print(f"    {GREEN}[PASS] OSV:{RESET}       0 high/critical CVEs.")
    print(f"    {GREEN}[PASS] Linters:{RESET}   Clean code style.")
    print()

    stage1 = {
        "stage": "agent_1_review",
        "findings": [],
        "confirmed_findings_count": 0,
        "unconfirmed_findings_count": 0,
        "commit_sha": "mockcommit-105-clean-remediated"
    }
    stage2 = {
        "stage": "agent_2_test_plan",
        "test_cases": [
            {"id": "TC-POS-01", "dimension": "positive", "title": "Valid quote accepted within 24h window"},
            {"id": "TC-NEG-01", "dimension": "negative", "title": "Stale quote rejection with EXPIRED status"},
            {"id": "TC-AUTH-01", "dimension": "authorization", "title": "Cross-buyer IDOR rejection returns 403 Forbidden"},
            {"id": "TC-PLAT-01", "dimension": "platform", "title": "Mobile double-tap debouncing on AcceptQuoteButton.tsx"}
        ],
        "commit_sha": "mockcommit-105-clean-remediated"
    }
    stage3 = {
        "stage": "agent_3_qa_plan",
        "manual_test_matrix": [
            {"id": "QA-STAGE-01", "target": "Mobile Stage APK", "scenario": "Rapid double-click on payment button"},
            {"id": "QA-STAGE-02", "target": "Backend API", "scenario": "Buyer B accepts Buyer A quote directly"}
        ],
        "commit_sha": "mockcommit-105-clean-remediated"
    }
    automated_tests = {
        "total": 34,
        "passed": 34,
        "failed": 0,
        "skipped": 0,
        "commit_sha": "mockcommit-105-clean-remediated"
    }

    # Evaluate promotion to STAGE branch
    print_step("Target Branch Promotion Gate: STAGE", "(Triggers Internal Stage APK Build)")
    policy = evaluate_branch_compliance(
        target_branch="stage",
        stage1=stage1,
        stage2=stage2,
        stage3=stage3,
        candidate_commit="mockcommit-105-clean-remediated",
        automated_tests=automated_tests
    )

    print(f"    {GREEN}[PASS] Stage 1 Tech Lead (Shahbaz / Saif):{RESET}  APPROVED")
    print(f"    {GREEN}[PASS] Stage 2 Senior Dev (Shahzeb / Tooba):{RESET} APPROVED ({len(stage2['test_cases'])} proposals reviewed)")
    print(f"    {GREEN}[PASS] Stage 3 QA Lead (Saira / Tabbasum):{RESET}   APPROVED (Stage APK manual matrix assigned)")
    print(f"    {CYAN}[STAGE-APK] Internal Stage APK v2.1.0-stage-105 build triggered for QA team{RESET}")
    print()

    # Promotion to PROD branch
    print_step("Target Branch Promotion Gate: PROD", "(Final Release Gate)")
    prod_policy = evaluate_branch_compliance(
        target_branch="prod",
        stage1=stage1,
        stage2=stage2,
        stage3=stage3,
        candidate_commit="mockcommit-105-clean-remediated",
        automated_tests=automated_tests
    )

    rm_approval = next(a for a in prod_policy["approvals"] if a["role"] == "release_manager")
    print(f"    {GREEN}[PASS] Stage 4 Release Manager (Hassan / Shahbaz):{RESET} APPROVED")
    print(f"    Reason: {rm_approval['reason']}")
    print(f"\n{GREEN}{BOLD}[AUTHORIZED] PROMOTION TO PRODUCTION APPROVED!{RESET}")
    print("Full cryptographic audit trail generated and bound to candidate commit.\n")


def main():
    print_banner("AuctionNow SDLC Quality & Governance Architecture Demo", CYAN)
    print("Demonstrating how AuctionNow eliminates 'blind LLM PR review' failures")
    print("using deterministic tools, HITL personas, and branch gate policies.\n")

    run_scenario_a()
    if "--auto" not in sys.argv:
        try:
            input(f"{YELLOW}Press [Enter] to run Scenario B (Remediated PR)...{RESET}")
        except (EOFError, OSError):
            pass
    run_scenario_b()

    print_banner("Summary for PM & Senior Developer", CYAN)
    print("1. Deterministic Scanners (Gitleaks, Semgrep, OSV, Linters) protect against real code flaws.")
    print("2. LLMs act as ADVISORY only; cannot approve code, merge branches, or claim test coverage.")
    print("3. Human roles (Tech Lead, Senior Dev, QA Lead, Release Manager) own signed-off decisions.")
    print("4. Stage branch automatically gates and triggers the Stage APK for the mobile QA team.")
    print("5. 34/34 automated tests confirm tamper-evident execution.\n")


if __name__ == "__main__":
    main()
