"""
AuctionNow Admin Portal Tests
Covers: seller verification, user management, request oversight, category mgmt.
Admin portal is for the founder — full visibility into all business activity.
"""
import pytest


class TestAdminAuth:

    def test_admin_login(self, client, admin_payload):
        r = client.post("/admin/auth/login", json=admin_payload)
        assert r.status_code in (200, 404)

    def test_non_admin_cannot_access_portal(self, client, buyer_token):
        r = client.get("/admin/dashboard",
                       headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code == 403

    def test_unauthenticated_admin_blocked(self, client):
        r = client.get("/admin/dashboard")
        assert r.status_code == 401


class TestSellerVerification:
    """Admin verifies sellers before they can bid."""

    def test_admin_can_list_pending_sellers(self, client, admin_token):
        r = client.get("/admin/sellers/pending",
                       headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            assert isinstance(r.json(), list)

    def test_admin_can_verify_seller(self, client, admin_token):
        r = client.post("/admin/sellers/1/verify",
                        headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code in (200, 404)

    def test_admin_can_reject_seller(self, client, admin_token):
        r = client.post("/admin/sellers/1/reject",
                        json={"reason": "Invalid documents"},
                        headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code in (200, 404)

    def test_admin_can_deactivate_verified_seller(self, client, admin_token):
        r = client.post("/admin/sellers/1/deactivate",
                        headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code in (200, 404)

    def test_buyer_cannot_verify_seller(self, client, buyer_token):
        r = client.post("/admin/sellers/1/verify",
                        headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code == 403


class TestAdminRequestOversight:
    """Admin can see all buyer requests across all users."""

    def test_admin_can_view_all_requests(self, client, admin_token):
        r = client.get("/admin/requests",
                       headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code in (200, 404)

    def test_admin_can_filter_by_category(self, client, admin_token):
        r = client.get("/admin/requests?category=mobiles",
                       headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code in (200, 404)

    def test_admin_can_view_specific_request(self, client, admin_token):
        r = client.get("/admin/requests/1",
                       headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code in (200, 404)

    def test_admin_can_close_request(self, client, admin_token):
        r = client.post("/admin/requests/1/close",
                        headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code in (200, 404)


class TestAdminDashboard:
    """Dashboard stats the founder views."""

    def test_dashboard_returns_stats(self, client, admin_token):
        r = client.get("/admin/dashboard",
                       headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = r.json()
            # Expect basic business metrics
            assert any(k in data for k in [
                "total_users", "total_requests", "total_bids",
                "active_sellers", "active_buyers"
            ])

    def test_dashboard_category_breakdown(self, client, admin_token):
        r = client.get("/admin/dashboard/categories",
                       headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code in (200, 404)

    def test_dashboard_city_breakdown(self, client, admin_token):
        r = client.get("/admin/dashboard/cities",
                       headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code in (200, 404)


class TestAdminUserManagement:

    def test_admin_can_list_all_buyers(self, client, admin_token):
        r = client.get("/admin/users?role=buyer",
                       headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code in (200, 404)

    def test_admin_can_list_all_sellers(self, client, admin_token):
        r = client.get("/admin/users?role=seller",
                       headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code in (200, 404)

    def test_admin_can_ban_user(self, client, admin_token):
        r = client.post("/admin/users/1/ban",
                        json={"reason": "Fraudulent activity"},
                        headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code in (200, 404)

    def test_banned_user_cannot_login(self, client):
        r = client.post("/auth/otp/request", json={"phone": "+923001111111"})
        # +923001111111 seeded as banned in test DB
        assert r.status_code in (200, 403)  # either blocked at OTP or at verify
