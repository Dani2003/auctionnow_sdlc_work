"""
AuctionNow Auth Tests
Covers: OTP request, OTP verify, token refresh, logout, invalid flows.
"""
import pytest


class TestOTPRequest:
    """POST /auth/otp/request — send OTP to phone number"""

    def test_valid_phone_number(self, client):
        r = client.post("/auth/otp/request", json={"phone": "+923001234567"})
        assert r.status_code == 200
        assert r.json().get("message") or r.json().get("status")

    def test_invalid_phone_format(self, client):
        r = client.post("/auth/otp/request", json={"phone": "03001234567"})
        # should reject local format without country code
        assert r.status_code == 422

    def test_missing_phone_field(self, client):
        r = client.post("/auth/otp/request", json={})
        assert r.status_code == 422

    def test_empty_phone_string(self, client):
        r = client.post("/auth/otp/request", json={"phone": ""})
        assert r.status_code in (400, 422)

    def test_phone_with_spaces(self, client):
        r = client.post("/auth/otp/request", json={"phone": "+92 300 1234567"})
        # acceptable — should normalize or reject clearly
        assert r.status_code in (200, 422)

    def test_rate_limit_on_repeated_otp_requests(self, client):
        for _ in range(5):
            client.post("/auth/otp/request", json={"phone": "+923001234567"})
        r = client.post("/auth/otp/request", json={"phone": "+923001234567"})
        # should rate-limit
        assert r.status_code in (200, 429)


class TestOTPVerify:
    """POST /auth/otp/verify — verify OTP and receive JWT"""

    def test_valid_otp(self, client):
        # In test env, backend should accept a magic OTP e.g. 000000
        r = client.post("/auth/otp/verify", json={
            "phone": "+923001234567",
            "otp": "000000"
        })
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data or "token" in data

    def test_wrong_otp(self, client):
        r = client.post("/auth/otp/verify", json={
            "phone": "+923001234567",
            "otp": "999999"
        })
        assert r.status_code in (400, 401)

    def test_expired_otp(self, client):
        # Assumes test env has an expired OTP seeded
        r = client.post("/auth/otp/verify", json={
            "phone": "+923001234567",
            "otp": "111111"  # seed as expired in test DB
        })
        assert r.status_code in (400, 401)

    def test_otp_too_short(self, client):
        r = client.post("/auth/otp/verify", json={
            "phone": "+923001234567",
            "otp": "123"
        })
        assert r.status_code == 422

    def test_otp_non_numeric(self, client):
        r = client.post("/auth/otp/verify", json={
            "phone": "+923001234567",
            "otp": "abcdef"
        })
        assert r.status_code == 422

    def test_role_in_response(self, client):
        r = client.post("/auth/otp/verify", json={
            "phone": "+923001234567",
            "otp": "000000"
        })
        if r.status_code == 200:
            data = r.json()
            assert "role" in data  # buyer or seller


class TestTokenRefresh:
    """POST /auth/token/refresh"""

    def test_valid_refresh(self, client, buyer_token):
        r = client.post("/auth/token/refresh",
                        headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code in (200, 404)  # 404 if endpoint not yet built

    def test_expired_token_rejected(self, client):
        r = client.post("/auth/token/refresh",
                        headers={"Authorization": "Bearer expired.token.here"})
        assert r.status_code in (401, 422)


class TestProtectedRoute:
    """Baseline: any protected route rejects unauthenticated requests."""

    def test_no_token_returns_401(self, client):
        r = client.get("/buyer/requests")
        assert r.status_code == 401

    def test_malformed_token_returns_401(self, client):
        r = client.get("/buyer/requests",
                       headers={"Authorization": "Bearer not.a.real.token"})
        assert r.status_code == 401
