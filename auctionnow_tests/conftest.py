"""
AuctionNow Test Suite — conftest.py
Shared fixtures for all test modules.
FastAPI backend on FastAPI Cloud (stage), AWS (prod).
"""
import pytest
import os
from fastapi.testclient import TestClient
# from app.main import app  # uncomment once repo access granted

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
BASE_URL = os.getenv("AUCTIONNOW_BASE_URL", "http://localhost:8000")
STAGE_USER = os.getenv("STAGE_USERNAME", "")
STAGE_PASS = os.getenv("STAGE_PASSWORD", "")

# ---------------------------------------------------------------------------
# Shared test data — aligned to AuctionNow domain
# ---------------------------------------------------------------------------

CATEGORIES = [
    "cars", "bikes", "travel", "umrah",
    "electronics", "laptops", "mobiles", "properties"
]

ELECTRONICS_SUBCATEGORIES = [
    "oven", "heater", "water_geyser", "fridge",
    "dispenser", "tv", "ac", "washing_machine"
]

PROPERTIES_SUBCATEGORIES = ["residential", "commercial"]

BIKES_SUBCATEGORIES = ["electric_bike", "motorbike"]

BRANDS = {
    "cars": ["toyota", "honda", "suzuki", "hyundai", "kia", "mg", "changan", "audi", "bmw", "mercedes"],
    "bikes": ["honda", "yamaha", "suzuki", "road_prince", "united", "super_power", "yadea", "metro"],
    "electronics": ["samsung", "haier", "dawlance", "gree", "pel", "orient", "lg", "tcl", "kenwood", "panasonic"]
}

# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def buyer_payload():
    return {
        "name": "Test Buyer",
        "phone": "+923001234567",
        "role": "buyer",
        "city": "Lahore",
    }

@pytest.fixture
def seller_payload():
    return {
        "name": "Test Seller",
        "phone": "+923009876543",
        "role": "seller",
        "city": "Lahore",
        "verified": True,
    }

@pytest.fixture
def admin_payload():
    return {
        "username": os.getenv("ADMIN_USERNAME", "admin"),
        "password": os.getenv("ADMIN_PASSWORD", ""),
    }

# ---------------------------------------------------------------------------
# Auth tokens (populated after login)
# ---------------------------------------------------------------------------

@pytest.fixture
def buyer_token(buyer_payload):
    """Returns a valid buyer JWT after OTP login."""
    # TODO: wire to real /auth/otp/verify once repo access
    return os.getenv("TEST_BUYER_TOKEN", "stub_buyer_token")

@pytest.fixture
def seller_token(seller_payload):
    return os.getenv("TEST_SELLER_TOKEN", "stub_seller_token")

@pytest.fixture
def admin_token(admin_payload):
    return os.getenv("TEST_ADMIN_TOKEN", "stub_admin_token")

# ---------------------------------------------------------------------------
# HTTP client fixture (uses TestClient locally, httpx for stage)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_in_memory_state():
    """Reset mock app in-memory state before each test run for test isolation."""
    try:
        from app.main import reset_db
        reset_db()
    except Exception:
        pass
    yield

@pytest.fixture
def client():
    """
    Local: TestClient against the FastAPI app.
    Stage: real HTTP client pointed at FastAPI Cloud URL.
    Switch via AUCTIONNOW_ENV=stage environment variable.
    """
    if os.getenv("AUCTIONNOW_ENV") == "stage":
        import httpx
        return httpx.Client(
            base_url=BASE_URL,
            auth=(STAGE_USER, STAGE_PASS),
            timeout=30.0,
        )
    try:
        from app.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)
    except Exception:
        import httpx
        return httpx.Client(base_url=BASE_URL, timeout=10.0)
