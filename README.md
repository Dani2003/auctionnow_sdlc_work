# AuctionNow SDLC Lab — AI-Assisted Governance Prototype

A local, vendor-neutral prototype for an AI-assisted software delivery workflow with strict Human-in-the-Loop (HITL) role-based governance. Built for Python 3.10+ with zero external dependencies.

---

## 1. Quick Start

### Setup Environment
```bash
py -3.11 -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
```

### Run Tests
```bash
python -m unittest discover -s tests -v
```

### Run Interactive HITL Demo
Step through interactive role-based approvals in your terminal:
```bash
python -m sdlc_lab
```

### Run Automated / Non-Interactive Demo
Run end-to-end pipeline in automated simulation mode:
```bash
python -m sdlc_lab --auto
```
The full schema-validated machine-readable audit report is saved to `artifacts/latest_run.json`.

---

## 2. Four Bounded Stages & HITL Personas

The prototype implements a sequential, lazy-execution pipeline where each stage is evaluated by a dedicated persona before downstream execution can proceed:

| Stage | Agent Name | Assigned HITL Persona | Key Responsibilities |
| :--- | :--- | :--- | :--- |
| **Stage 1** | **Engineering Quality & Security Reviewer** | **Sarah Chen (Tech Lead)** | Ingests deterministic scanner outputs (Gitleaks, Semgrep, OSV, Linters) alongside contextual advisory findings. Differentiates tool-confirmed vulnerabilities from LLM recommendations. Masks secrets. |
| **Stage 2** | **SDET Test Planner** | **Alex Rivera (Senior Dev)** | Generates structured test proposals categorized across positive, negative, boundary, authorization (IDOR), failure, and platform (mobile UI debounce) dimensions. Formulates clarification requests for missing business rules. All proposals have status `proposed_not_executed`. |
| **Stage 3** | **QA Director** | **Priya Patel (QA Lead)** | Creates a risk-based manual test matrix. Cross-references actual passing automated test execution reports. Prohibits marking scenarios covered without verified passing test reports matching the candidate commit. |
| **Stage 4** | **Release & CI Evidence Summarizer** | **David Kim (Release Manager)** | Evaluates all evidence (CI builds, automated tests, scanner reports, QA sign-off, and the complete HITL approval chain). Emits `PASS`, `BLOCKED`, or `NEEDS_HUMAN_REVIEW`. Never merges or deploys code. |

---

## 3. Architecture & Safety Guarantees

1. **Vendor-Neutral Architecture:**
   - **CodeRabbit is NOT an assumed or default dependency.**
   - Ingestion layer supports standardized open formats (Gitleaks, OSV-Scanner, Semgrep, Ruff/ESLint).
   - Keeps deterministic findings strictly separate from contextual AI suggestions (`confirmed_by_deterministic_tool: true` vs. `false`).
2. **Lazy Execution & Halt-on-Reject:**
   - Downstream stages are never executed if an upstream stage is rejected by its human reviewer.
3. **Commit & Digest Binding:**
   - Every artifact and approval record is bound to `pr_id`, `commit_sha`, UTC timestamp, and a cryptographic `artifact_sha256` digest.
   - Any commit change invalidates downstream evidence and requires re-approval.
4. **Strict Schema Contracts:**
   - Every stage artifact and approval record is validated against strict schemas in `sdlc_lab/schemas.py`.
   - Tampered payloads, invalid severities, or unverified statuses trigger explicit `ValidationError`.
5. **Safety Boundaries:**
   - Synthetic fixtures only (`fixtures/`). No live network calls, GitHub API mutations, git commits, PR merges, or deployments.
   - No proprietary source code or real secrets are transmitted or stored.

---

## 4. CI/CD Orchestrator & Local Scanner Commands

### Run CI/CD Governance Pipeline
```bash
python -m sdlc_lab.ci_orchestrator --target-branch dev --commit-sha mockcommit-104-a1b2c3 --pr-id SYNTHETIC-PR-104 --scanners-dir fixtures --tests-file fixtures/sample_ci_evidence.json --output artifacts/ci_run.json
```
This produces `artifacts/ci_run.json` and generates the GitHub Actions Step Summary in `artifacts/step_summary.md`.

### Run Deterministic Scanners Locally
```bash
python -m sdlc_lab.local_runner --repo-root . --output-dir artifacts/scanners
```
Executes Gitleaks, Semgrep, OSV-Scanner, Ruff, and ESLint with safe subprocess execution, timeout guards, and explicit skip reporting.

---

## 5. Repository Structure

```text
├── .github/
│   └── workflows/
│       └── sdlc_pipeline.yml         # Deterministic GitHub Actions CI/CD governance pipeline
├── artifacts/
│   ├── .gitkeep
│   ├── latest_run.json               # Machine-readable audit report of last run
│   └── step_summary.md               # GitHub Actions Markdown Step Summary
├── docs/
│   ├── current_design_review.md      # Architectural assessment, gaps, risks, scanner evaluation
│   ├── architecture.md               # Target architecture specifications & branch policy matrix
│   └── roadmap.md                    # Rollout roadmap & verified milestone checklist
├── fixtures/
│   ├── sample_pr.json                # Synthetic PR diff and metadata
│   ├── sample_requirements.json      # Feature acceptance criteria
│   ├── sample_scanner_reports.json   # Machine-readable Gitleaks, Semgrep, OSV, Ruff reports
│   └── sample_ci_evidence.json       # Machine-readable CI test runs and release evidence
├── policies/
│   └── branch_governance.json        # Declarative branch promotion policies (dev -> stage -> prod)
├── sdlc_lab/
│   ├── __init__.py
│   ├── __main__.py                   # CLI entrypoint (interactive and --auto modes)
│   ├── agents.py                     # 4 agent implementations with schema validation
│   ├── branch_policy.py              # Branch promotion policy engine and persona verification
│   ├── ci_orchestrator.py            # CI/CD orchestrator & GitHub Step Summary generator
│   ├── local_runner.py               # Deterministic scanner subprocess execution runner
│   ├── scanners.py                   # Deterministic scanner ingestion adapters & secret masking
│   ├── schemas.py                    # Schema dataclasses, validators, SHA-256 calculators
│   └── workflow.py                   # Lazy-execution orchestrator and HITL approval engine
└── tests/
    ├── test_agents.py                # Baseline compatibility tests
    ├── test_ci_orchestrator.py       # CI Orchestrator, Branch Governance, and Scanner Runner tests
    └── test_sdlc_pipeline.py         # Pipeline tests (34 unit tests across all phases)
```
