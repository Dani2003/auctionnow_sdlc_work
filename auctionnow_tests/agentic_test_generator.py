"""
AuctionNow — Agentic Unit Test Generator
=========================================
Triggered on every new PR. Reads the diff, identifies new/changed FastAPI
routes, generates pytest edge-case tests automatically, and posts them as a
PR comment for the tech lead (Shahbaz / Shahzeb) to review before Hassan merges.

Architecture:
  GitHub Actions triggers on: [pull_request, types: [opened, synchronize]]
  → Agent reads the diff via GitHub API
  → Calls OpenAI (or any LLM) with structured prompt
  → Parses generated tests
  → Posts as PR comment + optionally commits to a `tests/` branch

Dependencies:
  pip install openai httpx PyGithub python-dotenv
"""

import os
import re
import json
import textwrap
from pathlib import Path
from typing import Optional

try:
    import httpx
    from github import Github
    from openai import OpenAI
except ImportError:
    print("Run: pip install openai httpx PyGithub")
    raise


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
REPO_NAME = os.environ.get("GITHUB_REPOSITORY", "your-org/auctionnow")
PR_NUMBER = int(os.environ.get("PR_NUMBER", "0"))

DOMAIN_CONTEXT = """
AuctionNow is a reverse marketplace in Lahore, Pakistan.
Buyers post requests. Verified sellers bid. Buyer accepts best bid.

Categories: cars, bikes, travel, umrah, electronics (8 subs: oven/heater/
water_geyser/fridge/dispenser/tv/ac/washing_machine), laptops, mobiles,
properties (2 subs: residential/commercial).

Auth: phone + OTP → JWT. Roles: buyer, seller (verified by admin), admin.
Backend: FastAPI. DB: Neon Postgres (stage), AWS RDS (prod).
"""

SYSTEM_PROMPT = f"""
You are a senior QA engineer writing pytest tests for a FastAPI application.
{DOMAIN_CONTEXT}

Given a code diff, generate pytest test functions that cover:
1. Happy path for each new endpoint
2. Missing/invalid required fields (422)
3. Wrong role / unauthorized access (401/403)
4. Boundary conditions (negative price, empty string, max length)
5. Business-rule edge cases (e.g. bid on closed request, duplicate bid)
6. Category/subcategory validation

Format: return ONLY valid Python code, no markdown fences, no explanation.
Use httpx.Client fixture named `client` and token fixtures: buyer_token,
seller_token, admin_token. Import pytest at the top.
"""


# ---------------------------------------------------------------------------
# Step 1: Get the PR diff
# ---------------------------------------------------------------------------

def get_pr_diff(repo_name: str, pr_number: int) -> str:
    """Fetch the unified diff for a PR via GitHub API."""
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)

    # Get changed files
    files = list(pr.get_files())

    # Filter to Python backend files only (skip migrations, frontend, etc.)
    backend_files = [
        f for f in files
        if f.filename.endswith(".py")
        and not f.filename.startswith("tests/")
        and not "migration" in f.filename.lower()
        and not "alembic" in f.filename.lower()
    ]

    if not backend_files:
        return ""

    diff_parts = []
    for f in backend_files:
        diff_parts.append(f"=== {f.filename} ===")
        if f.patch:
            diff_parts.append(f.patch)

    return "\n".join(diff_parts)


# ---------------------------------------------------------------------------
# Step 2: Extract new route signatures from the diff
# ---------------------------------------------------------------------------

def extract_new_routes(diff: str) -> list[dict]:
    """
    Parse the diff to find newly added FastAPI route decorators.
    Returns list of {method, path, function_name, params}.
    """
    routes = []
    lines = diff.split("\n")

    # Look for added lines (starting with +) that are route decorators
    route_pattern = re.compile(
        r'^\+\s*@(?:router|app)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']'
    )
    func_pattern = re.compile(r'^\+\s*(?:async\s+)?def\s+(\w+)\s*\(')

    i = 0
    while i < len(lines):
        m = route_pattern.match(lines[i])
        if m:
            method, path = m.group(1).upper(), m.group(2)
            # Look ahead for the function definition
            func_name = "unknown"
            for j in range(i + 1, min(i + 5, len(lines))):
                fm = func_pattern.match(lines[j])
                if fm:
                    func_name = fm.group(1)
                    break
            routes.append({
                "method": method,
                "path": path,
                "function": func_name,
            })
        i += 1

    return routes


# ---------------------------------------------------------------------------
# Step 3: Generate tests via LLM
# ---------------------------------------------------------------------------

def generate_tests(diff: str, routes: list[dict]) -> str:
    """Send diff + route context to LLM, receive pytest code."""
    client = OpenAI(api_key=OPENAI_API_KEY)

    route_summary = "\n".join(
        f"  - {r['method']} {r['path']} → {r['function']}()"
        for r in routes
    )

    user_prompt = f"""
New PR adds these endpoints:
{route_summary}

Full diff:
```
{diff[:6000]}
```

Generate pytest tests covering edge cases for ONLY the new endpoints above.
Use the conftest.py fixtures already in the repo (client, buyer_token, seller_token, admin_token).
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=2000,
    )

    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Step 4: Validate the generated code is syntactically valid Python
# ---------------------------------------------------------------------------

def validate_python(code: str) -> bool:
    try:
        compile(code, "<generated>", "exec")
        return True
    except SyntaxError as e:
        print(f"Generated code has syntax error: {e}")
        return False


# ---------------------------------------------------------------------------
# Step 5: Post as PR comment
# ---------------------------------------------------------------------------

def post_pr_comment(repo_name: str, pr_number: int, test_code: str, routes: list[dict]):
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(repo_name)
    pr = repo.get_pull(pr_number)

    route_list = "\n".join(
        f"- `{r['method']} {r['path']}`" for r in routes
    )

    comment = textwrap.dedent(f"""
    ## 🤖 Agentic Test Generator — Auto-generated Tests

    Detected **{len(routes)} new endpoint(s)** in this PR:
    {route_list}

    Generated pytest edge-case tests below. **Tech leads (Shahbaz / Shahzeb)**:
    please review before merge. Tests will be committed to `tests/` on approval.

    <details>
    <summary>📋 Generated Test Code</summary>

    ```python
    {test_code}
    ```

    </details>

    > To run these locally: copy into `tests/test_pr_{pr_number}_generated.py` and run `pytest`
    """).strip()

    pr.create_issue_comment(comment)
    print(f"Posted test comment on PR #{pr_number}")


# ---------------------------------------------------------------------------
# Step 6 (optional): Commit generated tests to a branch
# ---------------------------------------------------------------------------

def commit_tests_to_branch(test_code: str, pr_number: int):
    """
    Optionally commit the generated tests to the PR branch.
    Only do this if the tech lead has approved via a /approve-tests comment.
    """
    # TODO: implement after repo access granted
    pass


# ---------------------------------------------------------------------------
# Main entrypoint (called from GitHub Actions)
# ---------------------------------------------------------------------------

def main():
    if not PR_NUMBER:
        print("PR_NUMBER not set, skipping.")
        return

    print(f"Processing PR #{PR_NUMBER} in {REPO_NAME}...")

    # 1. Get diff
    diff = get_pr_diff(REPO_NAME, PR_NUMBER)
    if not diff:
        print("No backend Python changes found. Skipping test generation.")
        return

    # 2. Extract new routes
    routes = extract_new_routes(diff)
    if not routes:
        print("No new FastAPI routes detected. Skipping.")
        return

    print(f"Found {len(routes)} new routes: {[r['path'] for r in routes]}")

    # 3. Generate tests
    test_code = generate_tests(diff, routes)

    # 4. Validate
    if not validate_python(test_code):
        # Retry once with a stricter prompt
        test_code = generate_tests(diff, routes)
        if not validate_python(test_code):
            print("Generated code invalid after retry. Posting warning.")
            test_code = f"# Auto-generation failed — please write tests manually\n# Routes: {routes}"

    # 5. Post comment
    post_pr_comment(REPO_NAME, PR_NUMBER, test_code, routes)


if __name__ == "__main__":
    main()
