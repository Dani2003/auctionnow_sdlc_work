# AuctionNow — Test Suite & SDLC System

Built without repo access. Drop this into the private repo root once access is granted.

## Structure

```
tests/
├── conftest.py                  ← shared fixtures (client, tokens, test data)
├── auth/
│   └── test_auth.py             ← OTP, JWT, token refresh, protected routes
├── buyer/
│   └── test_buyer_requests.py   ← post request, view bids, accept bid, categories
├── seller/
│   └── test_seller_bids.py      ← view requests, place/update/withdraw bids
├── admin/
│   └── test_admin_portal.py     ← seller verification, dashboard, user mgmt
├── categories/
│   └── test_categories.py       ← all 8 categories + subcategories
└── agentic_test_generator.py    ← AI agent that writes tests for new PRs

.github/workflows/
├── agentic_tests.yml            ← triggers on PR open/sync, posts generated tests
└── sdlc_gates.yml               ← 4-gate CI/CD pipeline
```

## Running Tests

```bash
# Local (no repo access needed for structure/linting)
pip install pytest httpx python-dotenv

# Against stage
export AUCTIONNOW_ENV=stage
export AUCTIONNOW_BASE_URL=https://your-fastapi-cloud-url
export STAGE_USERNAME=...
export STAGE_PASSWORD=...
pytest tests/ -v

# Against local FastAPI
uvicorn app.main:app --reload
pytest tests/ -v
```

## Agentic Test Generator Flow

```
PR opened by Saif or Tooba
        ↓
GitHub Actions triggers agentic_test_generator.py
        ↓
Agent reads diff → finds new FastAPI routes
        ↓
Calls GPT-4o with AuctionNow domain context
        ↓
Validates generated Python syntax
        ↓
Posts as PR comment for Shahbaz / Shahzeb review
        ↓
Tech lead approves → Hassan merges
```

## Secrets to Add in GitHub

| Secret | Description |
|--------|-------------|
| `OPENAI_API_KEY` | For agentic test generation |
| `NEON_STAGE_DB_URL` | Stage Neon Postgres connection string |
| `AWS_ACCESS_KEY_ID` | Prod deploy |
| `AWS_SECRET_ACCESS_KEY` | Prod deploy |
| `ECR_REGISTRY` | AWS ECR URL for Docker images |
| `TEST_BUYER_TOKEN` | Seeded test JWT for buyer role |
| `TEST_SELLER_TOKEN` | Seeded test JWT for seller role |
| `TEST_ADMIN_TOKEN` | Seeded test JWT for admin role |

## Categories Reference

| Category | Subcategories |
|----------|---------------|
| cars | — |
| bikes | — |
| travel | — |
| umrah | — |
| electronics | oven, heater, water_geyser, fridge, dispenser, tv, ac, washing_machine |
| laptops | — |
| mobiles | — |
| properties | residential, commercial |

## What needs repo access to complete

1. Wire `conftest.py` client fixture to actual `app.main:app`
2. Confirm actual route paths (e.g. `/buyer/requests` vs `/api/v1/buyer/requests`)
3. Seed test DB with fixed test users + requests + bids
4. Add `agentic_test_generator.py` to `.github/scripts/`
5. Push workflow YAMLs to `.github/workflows/`
6. Add all secrets to GitHub repo settings
