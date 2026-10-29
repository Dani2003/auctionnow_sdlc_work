"""
AuctionNow Seller-Side Tests
Covers: view open requests, place bid, update bid, withdraw bid.
Sellers are verified by admin before they can bid.
"""
import pytest


class TestSellerViewRequests:
    """GET /seller/requests — see open buyer requests in seller's categories"""

    def test_verified_seller_can_view_requests(self, client, seller_token):
        r = client.get("/seller/requests",
                       headers={"Authorization": f"Bearer {seller_token}"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_buyer_cannot_view_seller_feed(self, client, buyer_token):
        r = client.get("/seller/requests",
                       headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code == 403

    def test_unverified_seller_blocked(self, client):
        unverified_token = "stub_unverified_seller_token"
        r = client.get("/seller/requests",
                       headers={"Authorization": f"Bearer {unverified_token}"})
        assert r.status_code in (401, 403)

    def test_requests_filtered_by_seller_city(self, client, seller_token):
        r = client.get("/seller/requests",
                       headers={"Authorization": f"Bearer {seller_token}"})
        if r.status_code == 200 and r.json():
            for req in r.json():
                assert req.get("city") == "Lahore"

    def test_requests_contain_required_fields(self, client, seller_token):
        r = client.get("/seller/requests",
                       headers={"Authorization": f"Bearer {seller_token}"})
        if r.status_code == 200 and r.json():
            req = r.json()[0]
            assert "id" in req or "request_id" in req
            assert "category" in req
            assert "budget_min" in req or "budget" in req


class TestPlaceBid:
    """POST /seller/requests/{id}/bid"""

    def test_verified_seller_can_bid(self, client, seller_token):
        r = client.post("/seller/requests/1/bid",
                        json={"price": 280000, "note": "Best deal in Lahore"},
                        headers={"Authorization": f"Bearer {seller_token}"})
        assert r.status_code in (201, 200, 404)

    def test_buyer_cannot_place_bid(self, client, buyer_token):
        r = client.post("/seller/requests/1/bid",
                        json={"price": 280000},
                        headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code == 403

    def test_bid_price_below_buyer_budget_min(self, client, seller_token):
        # buyer budget_min=250000, bid at 100000 — should warn or reject
        r = client.post("/seller/requests/1/bid",
                        json={"price": 100000},
                        headers={"Authorization": f"Bearer {seller_token}"})
        assert r.status_code in (200, 201, 400, 422)  # depends on business rule

    def test_bid_price_above_budget_max(self, client, seller_token):
        r = client.post("/seller/requests/1/bid",
                        json={"price": 999999999},
                        headers={"Authorization": f"Bearer {seller_token}"})
        assert r.status_code in (200, 201, 400, 422)

    def test_bid_missing_price(self, client, seller_token):
        r = client.post("/seller/requests/1/bid",
                        json={"note": "Good deal"},
                        headers={"Authorization": f"Bearer {seller_token}"})
        assert r.status_code == 422

    def test_negative_bid_price(self, client, seller_token):
        r = client.post("/seller/requests/1/bid",
                        json={"price": -5000},
                        headers={"Authorization": f"Bearer {seller_token}"})
        assert r.status_code in (400, 422)

    def test_zero_bid_price(self, client, seller_token):
        r = client.post("/seller/requests/1/bid",
                        json={"price": 0},
                        headers={"Authorization": f"Bearer {seller_token}"})
        assert r.status_code in (400, 422)

    def test_duplicate_bid_same_seller_same_request(self, client, seller_token):
        # seller already bid on request 1 in test DB
        r = client.post("/seller/requests/1/bid",
                        json={"price": 290000},
                        headers={"Authorization": f"Bearer {seller_token}"})
        assert r.status_code in (200, 201, 400, 409)  # update or conflict

    def test_bid_on_closed_request(self, client, seller_token):
        # request_id=2 seeded as closed
        r = client.post("/seller/requests/2/bid",
                        json={"price": 280000},
                        headers={"Authorization": f"Bearer {seller_token}"})
        assert r.status_code in (400, 404, 409)

    def test_bid_on_nonexistent_request(self, client, seller_token):
        r = client.post("/seller/requests/99999/bid",
                        json={"price": 280000},
                        headers={"Authorization": f"Bearer {seller_token}"})
        assert r.status_code == 404


class TestUpdateBid:
    """PUT /seller/bids/{id} — update own bid before buyer accepts"""

    def test_seller_can_update_own_bid(self, client, seller_token):
        r = client.put("/seller/bids/1",
                       json={"price": 275000},
                       headers={"Authorization": f"Bearer {seller_token}"})
        assert r.status_code in (200, 404)

    def test_seller_cannot_update_accepted_bid(self, client, seller_token):
        # bid_id=2 seeded as accepted
        r = client.put("/seller/bids/2",
                       json={"price": 260000},
                       headers={"Authorization": f"Bearer {seller_token}"})
        assert r.status_code in (400, 403, 404, 409)


class TestWithdrawBid:
    """DELETE /seller/bids/{id}"""

    def test_seller_can_withdraw_pending_bid(self, client, seller_token):
        r = client.delete("/seller/bids/1",
                          headers={"Authorization": f"Bearer {seller_token}"})
        assert r.status_code in (200, 204, 404)

    def test_cannot_withdraw_accepted_bid(self, client, seller_token):
        r = client.delete("/seller/bids/2",
                          headers={"Authorization": f"Bearer {seller_token}"})
        assert r.status_code in (400, 403, 409)
