"""AuctionNow Agentic Unit Test Generator.

Executed on PRs targeting dev/stage. Analyzes AST diffs, isolates changed FastAPI
routes, queries an LLM with domain-specific rules, verifies syntax via ast.parse,
and publishes the generated edge-case tests as an auditable PR comment.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional

try:
    import httpx
except ImportError:
    print("CRITICAL: httpx is required. Run: pip install httpx", file=sys.stderr)
    sys.exit(1)

# Domain Model Definition - Hardcoded architectural truth for AuctionNow Lahore
AUCTIONNOW_DOMAIN_RULES = """
AUCTIONNOW PLATFORM SPECIFICATIONS:
1. Location: Lahore, Pakistan (Reverse marketplace model).
2. Flow: Buyer posts request -> Verified Sellers place bids -> Buyer accepts best bid -> Request closed.
3. Top-Level Categories (Exactly 8):
   - cars, bikes, travel, umrah, electronics, laptops, mobiles, properties
4. Subcategories:
   - electronics (Exactly 8): oven, heater, water_geyser, fridge, dispenser, tv, ac, washing_machine
   - properties (Exactly 2): residential, commercial
   - cars, bikes, travel, umrah, laptops, mobiles: No subcategories permitted (must be null/omitted).
5. User Roles:
   - 'buyer': Can post requests, view bids on owned requests, accept bids, cancel owned requests.
   - 'seller': Can view open requests, place bids, withdraw bids. Must have `is_verified == True` to bid.
   - 'admin': Can verify/reject sellers, ban users, inspect analytics dashboard.
6. Core Business Logic Invariants:
   - Sellers CANNOT bid on their own requests (even if registered as both roles).
   - Bids cannot be placed on 'closed', 'accepted', or 'cancelled' requests (HTTP 400/409).
   - Unverified sellers placing a bid MUST receive HTTP 403 Forbidden.
   - Buyers accepting a bid on a request they do not own MUST receive HTTP 403 Forbidden (IDOR prevention).
   - Negative prices or zero amounts in bids must return HTTP 422 Unprocessable Entity.
7. Authentication:
   - Header: 'Authorization: Bearer <jwt_token>'
   - Unauthenticated requests must return HTTP 401 Unauthorized.
"""


def get_pr_diff(github_token: str, repo: str, pr_number: int) -> str:
    """Fetches the unified git diff from GitHub REST API."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3.diff",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to fetch PR diff: HTTP {resp.status_code} - {resp.text}")
        return resp.text


def extract_route_metadata(diff_text: str) -> List[Dict[str, str]]:
    """Identifies changed or newly introduced FastAPI route decorators."""
    pattern = re.compile(
        r"^\+\s*@(app|router)\.(get|post|put|delete|patch)\(\s*[\"']([^\"']+)[\"']",
        re.MULTILINE,
    )
    routes = []
    for match in pattern.finditer(diff_text):
        routes.append({
            "http_method": match.group(2).upper(),
            "path": match.group(3),
        })
    return routes


def build_agent_prompt(routes: List[Dict[str, str]], diff_text: str) -> str:
    """Builds a bounded prompt incorporating system domain rules."""
    routes_formatted = json.dumps(routes, indent=2)
    return f"""You are a Principal SDET writing robust pytest test cases for AuctionNow's FastAPI backend.
{AUCTIONNOW_DOMAIN_RULES}

DETECTED NEW/CHANGED ROUTES IN THIS PR:
{routes_formatted}

PR DIFF CONTEXT:
```diff
{diff_text[:4000]}
```

TASK REQUIREMENTS:
Write executable, standalone pytest test cases targeting the detected routes.
Cover:
1. Happy path scenario using correct roles and valid payload.
2. Missing/malformed required field validation (HTTP 422).
3. Unauthorized access (no token) -> HTTP 401.
4. Role boundary violation (e.g. buyer attempting seller-only action) -> HTTP 403.
5. Inactive/unverified seller attempt -> HTTP 403.
6. Business rule edge cases (IDOR checks, closed requests, invalid subcategories).
7. Category/subcategory validation (e.g. invalid subcategory under electronics, or subcategory passed to 'cars').

SYNTAX & FIXTURE CONSTRAINTS:
- Use `client: httpx.Client` fixture.
- Use token fixtures: `buyer_token`, `seller_token`, `unverified_seller_token`, `admin_token`.
- Use headers parameter: `headers={{"Authorization": f"Bearer {{token}}"}`.
- Return ONLY valid Python code inside triple backticks with 'python'. No prose explanations.
"""


def query_llm_for_tests(api_key: str, prompt: str) -> str:
    """Invokes the LLM to generate test proposals."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": "You are a specialized SDET compiler agent. Output executable Python code only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            raise RuntimeError(f"LLM API execution failure: HTTP {resp.status_code} - {resp.text}")
        content = resp.json()["choices"][0]["message"]["content"]

    match = re.search(r"```python\s*(.*?)\s*```", content, re.DOTALL)
    return match.group(1).strip() if match else content.strip()


def validate_python_syntax(code_str: str) -> bool:
    """Validates that generated string parses into a valid Python AST."""
    try:
        ast.parse(code_str)
        return True
    except SyntaxError as e:
        print(f"ERROR: Generated code failed AST syntax validation: {e}", file=sys.stderr)
        return False


def post_pr_comment(github_token: str, repo: str, pr_number: int, comment_body: str) -> None:
    """Posts a comment on the active PR using GitHub REST API."""
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github.v3+json",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, headers=headers, json={"body": comment_body})
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Failed to post PR comment: HTTP {resp.status_code} - {resp.text}")


def main():
    github_token = os.environ.get("GITHUB_TOKEN")
    openai_key = os.environ.get("OPENAI_API_KEY")
    repo = os.environ.get("GITHUB_REPOSITORY")
    pr_number_str = os.environ.get("PR_NUMBER")

    if not all([github_token, openai_key, repo, pr_number_str]):
        print("Missing required environment variables. Skipping execution.", file=sys.stderr)
        sys.exit(0)

    pr_number = int(pr_number_str)
    diff = get_pr_diff(github_token, repo, pr_number)
    if not diff:
        print("No diff found or PR contains no changes.")
        sys.exit(0)

    routes = extract_route_metadata(diff)
    if not routes:
        print("No new or modified FastAPI route endpoints detected in PR diff.")
        sys.exit(0)

    print(f"Identified {len(routes)} changed FastAPI route(s). Generating tests...")
    prompt = build_agent_prompt(routes, diff)
    generated_code = query_llm_for_tests(openai_key, prompt)

    if not validate_python_syntax(generated_code):
        print("CRITICAL: LLM generated invalid Python syntax. Halting comment dispatch.", file=sys.stderr)
        sys.exit(1)

    comment = f"""### 🤖 AuctionNow SDLC Agent: Proposed Unit & Edge-Case Tests

**Attention Reviewers:** @Shahbaz / @Shahzeb (Tech Leads)  
**PR Author:** Saif / Tooba  
**Candidate Commit:** `{os.environ.get('HEAD_SHA', 'latest')}`

The agent detected changes to **{len(routes)} endpoint(s)** and generated the following edge-case tests covering:
- ✅ Positive happy path with role verification
- 🛑 HTTP 401 Unauthorized & 403 Forbidden role boundaries
- 🔍 Category & subcategory integrity (electronics / properties validation)
- ⚠️ Business rule invariants (IDOR checks, closed request states)

```python
{generated_code}
```

*Note: This code has passed local AST syntax validation (`ast.parse`). Review and verify before Hassan authorizes merge.*
"""
    post_pr_comment(github_token, repo, pr_number, comment)
    print("Successfully published generated tests to PR comment thread.")


if __name__ == "__main__":
    main()
