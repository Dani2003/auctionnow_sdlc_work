## 📋 AuctionNow Pull Request & Governance Gate

**Target Branch:** `dev` | `stage` | `prod`  
**PR Title:**  
**Related Issue / Ticket:**  

---

### 1. Change Summary
<!-- Describe what feature, bugfix, or refactor this PR introduces. Explicitly note any changes affecting startup routines, database schema, or auth boundaries. -->
- 

---

### 2. Affected System Surfaces
- [ ] Backend API / Services (`backend/app/...`)
- [ ] Database Schema / Migrations (`backend/alembic/...`)
- [ ] Mobile React Native App (`mobile/src/...`)
- [ ] Authentication / Authorization Boundaries
- [ ] CI/CD Pipeline / GitHub Actions

---

### 3. Automated SDLC Governance Stages & Sign-offs

> [!CAUTION]
> **Anti-Hallucination Policy:** Blind LLM approvals ("I asked an LLM and it said LGTM") are strictly prohibited. All merges require deterministic tool verification and role sign-offs.

#### Stage 1: Security & Quality Gate (Tech Lead: Sarah Chen)
- [ ] Gitleaks Secret Scan: Zero unmasked secrets detected.
- [ ] Semgrep SAST: Zero Critical/High authorization (IDOR) or injection flaws.
- [ ] OSV-Scanner: Zero unvetted High/Critical dependency CVEs.
- [ ] Ruff / ESLint: Code quality and formatting checks passed.
- **Tech Lead Approval:** `[ ] Approved` | `Approver: ____________`

#### Stage 2: Test Proposal & Design Verification (Senior Dev: Alex Rivera)
- [ ] Positive & negative unit tests proposed.
- [ ] Boundary tests (e.g. quote expiration timestamps) defined.
- [ ] Authorization / cross-buyer tenancy tests covered.
- [ ] Mobile debounce / idempotency checks reviewed (`AcceptQuoteButton.tsx`).
- [ ] Clarification requests answered (no assumed business logic).
- **Senior Dev Approval:** `[ ] Approved` | `Approver: ____________`

#### Stage 3: QA Matrix & Stage APK Handoff (QA Lead: Priya Patel)
- [ ] Target branch `stage`: Triggers internal Stage APK build.
- [ ] Manual test scenarios executed against the real Stage APK build.
- [ ] Zero blocking regressions observed in quotation/auction flow.
- **QA Lead Sign-off:** `[ ] Approved` | `Approver: ____________`

#### Stage 4: Production Release Verification (Release Manager: David Kim)
- [ ] Target branch `prod`: 100% CI automated test pass rate verified on candidate commit SHA.
- [ ] All upstream role sign-offs present with cryptographic artifact SHA-256 digests.
- **Release Manager Approval:** `[ ] Approved` | `Approver: ____________`

---

### 4. Verification Evidence
- **Candidate Commit SHA:** ` `
- **CI Run ID:** ` `
- **Machine-Readable Audit Trail:** `artifacts/latest_run.json`
