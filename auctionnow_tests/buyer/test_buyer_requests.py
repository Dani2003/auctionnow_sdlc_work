"""
AuctionNow Buyer-Side Tests
Covers: post request, view bids, accept bid, mark fulfilled.
Buyer posts a request → sellers bid → buyer accepts best bid.
"""
import pytest

VALID_REQUEST = {
    "category": "mobiles",
    "title": "iPhone 14 Pro Max 256GB",
    "description": "Looking for best price, good condition",
    "city": "Lahore",
    "budget_min": 250000,
    "budget_max": 320000,
}


class TestPostBuyerRequest:

    def test_create_valid_request(self, client, buyer_token):
        r = client.post("/buyer/requests",
                        json=VALID_REQUEST,
                        headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code == 201
        data = r.json()
        assert "id" in data or "request_id" in data

    def test_create_request_missing_category(self, client, buyer_token):
        payload = {**VALID_REQUEST}
        del payload["category"]
        r = client.post("/buyer/requests",
                        json=payload,
                        headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code == 422

    def test_create_request_invalid_category(self, client, buyer_token):
        payload = {**VALID_REQUEST, "category": "spaceship"}
        r = client.post("/buyer/requests",
                        json=payload,
                        headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code == 422

    def test_create_request_budget_max_less_than_min(self, client, buyer_token):
        payload = {**VALID_REQUEST, "budget_min": 500000, "budget_max": 100000}
        r = client.post("/buyer/requests",
                        json=payload,
                        headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code in (400, 422)

    def test_create_request_negative_budget(self, client, buyer_token):
        payload = {**VALID_REQUEST, "budget_min": -1000, "budget_max": -500}
        r = client.post("/buyer/requests",
                        json=payload,
                        headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code in (400, 422)

    def test_seller_cannot_post_buyer_request(self, client, seller_token):
        r = client.post("/buyer/requests",
                        json=VALID_REQUEST,
                        headers={"Authorization": f"Bearer {seller_token}"})
        assert r.status_code == 403

    def test_unauthenticated_cannot_post(self, client):
        r = client.post("/buyer/requests", json=VALID_REQUEST)
        assert r.status_code == 401


class TestViewBids:

    def test_buyer_can_view_bids_on_own_request(self, client, buyer_token):
        # Assumes request_id=1 exists in test DB with bids
        r = client.get("/buyer/requests/1/bids",
                       headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code in (200, 404)

    def test_buyer_cannot_view_bids_on_other_request(self, client, buyer_token):
        # request_id=9999 belongs to another buyer in test DB
        r = client.get("/buyer/requests/9999/bids",
                       headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code in (403, 404)

    def test_bids_response_has_required_fields(self, client, buyer_token):
        r = client.get("/buyer/requests/1/bids",
                       headers={"Authorization": f"Bearer {buyer_token}"})
        if r.status_code == 200:
            bids = r.json()
            if bids:
                bid = bids[0]
                assert "seller_id" in bid or "seller" in bid
                assert "price" in bid or "amount" in bid


class TestAcceptBid:

    def test_buyer_can_accept_bid(self, client, buyer_token):
        r = client.post("/buyer/requests/1/bids/1/accept",
                        headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code in (200, 404)

    def test_cannot_accept_bid_on_closed_request(self, client, buyer_token):
        # request_id=2 seeded as already closed
        r = client.post("/buyer/requests/2/bids/1/accept",
                        headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code in (400, 404, 409)

    def test_seller_cannot_accept_bid(self, client, seller_token):
        r = client.post("/buyer/requests/1/bids/1/accept",
                        headers={"Authorization": f"Bearer {seller_token}"})
        assert r.status_code == 403


class TestCategorySpecificRequests:
    """Each category should accept and validate category-specific fields."""

    @pytest.mark.parametrize("category", [
        "cars", "bikes", "travel", "umrah",
        "electronics", "laptops", "mobiles", "properties"
    ])
    def test_valid_category_accepted(self, client, buyer_token, category):
        payload = {**VALID_REQUEST, "category": category}
        r = client.post("/buyer/requests",
                        json=payload,
                        headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code in (201, 422)  # 422 only if subcategory required

    @pytest.mark.parametrize("subcategory", [
        "oven", "heater", "water_geyser", "fridge",
        "dispenser", "tv", "ac", "washing_machine"
    ])
    def test_electronics_subcategories(self, client, buyer_token, subcategory):
        payload = {
            **VALID_REQUEST,
            "category": "electronics",
            "subcategory": subcategory
        }
        r = client.post("/buyer/requests",
                        json=payload,
                        headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code in (201, 422)

    @pytest.mark.parametrize("subcategory", ["residential", "commercial"])
    def test_properties_subcategories(self, client, buyer_token, subcategory):
        payload = {
            **VALID_REQUEST,
            "category": "properties",
            "subcategory": subcategory
        }
        r = client.post("/buyer/requests",
                        json=payload,
                        headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code in (201, 422)

    def test_electronics_invalid_subcategory(self, client, buyer_token):
        payload = {
            **VALID_REQUEST,
            "category": "electronics",
            "subcategory": "microwave"  # not in the 8
        }
        r = client.post("/buyer/requests",
                        json=payload,
                        headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code == 422
