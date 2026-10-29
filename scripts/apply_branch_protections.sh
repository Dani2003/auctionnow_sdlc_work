#!/usr/bin/env bash
# Programmatic Branch Protection Provisioning for AuctionNow Repository
# Requires GITHUB_TOKEN with repo admin scope

set -euo pipefail

OWNER="AuctionNow"
REPO="auctionnow-backend"
API_BASE="https://api.github.com/repos/${OWNER}/${REPO}/branches"

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "Error: GITHUB_TOKEN environment variable is required."
  exit 1
fi

apply_protection() {
  local branch=$1
  local payload=$2
  echo "Applying branch protection to: ${branch}..."
  curl -s -X PUT "${API_BASE}/${branch}/protection" \
    -H "Authorization: Bearer ${GITHUB_TOKEN}" \
    -H "Accept: application/vnd.github.v3+json" \
    -H "Content-Type: application/json" \
    -d "${payload}" | jq -r '.url // .message'
}

# 1. Dev Branch Protection: Fast-feedback, requires Gate 1 & 2, 1 Tech Lead approval
DEV_PAYLOAD=$(cat <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Gate 1: Quality & Security",
      "Gate 2: Test Execution & Coverage"
    ]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 1
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
)
apply_protection "dev" "$DEV_PAYLOAD"

# 2. Stage Branch Protection: Requires Gates 1, 2, 3 (Neon Migration), 2 Approvals
STAGE_PAYLOAD=$(cat <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Gate 1: Quality & Security",
      "Gate 2: Test Execution & Coverage",
      "Gate 3: Migration Safety (Neon Preview)"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 2
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
)
apply_protection "stage" "$STAGE_PAYLOAD"

# 3. Prod Branch Protection: Merges restricted exclusively to Hassan
PROD_PAYLOAD=$(cat <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Gate 1: Quality & Security",
      "Gate 2: Test Execution & Coverage"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 2
  },
  "restrictions": {
    "users": ["hassan-auctionnow"],
    "teams": [],
    "apps": []
  },
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF
)
apply_protection "prod" "$PROD_PAYLOAD"

echo "Branch protection configuration successfully applied to dev, stage, and prod."

