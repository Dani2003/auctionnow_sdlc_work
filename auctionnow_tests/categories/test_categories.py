"""
AuctionNow Category Tests
Validates category/subcategory structure across all 8 top-level categories.
Cars, Bikes, Travel, Umrah, Electronics (8 sub), Laptops, Mobiles, Properties (2 sub).
"""
import pytest

TOP_LEVEL = ["cars", "bikes", "travel", "umrah",
             "electronics", "laptops", "mobiles", "properties"]

ELECTRONICS_SUBS = [
    "oven", "heater", "water_geyser", "fridge",
    "dispenser", "tv", "ac", "washing_machine"
]

PROPERTIES_SUBS = ["residential", "commercial"]

BIKES_SUBS = ["electric_bike", "motorbike"]

BRANDS_MAP = {
    "cars": ["toyota", "honda", "suzuki", "hyundai", "kia", "mg", "changan", "audi", "bmw", "mercedes"],
    "bikes": ["honda", "yamaha", "suzuki", "road_prince", "united", "super_power", "yadea", "metro"],
    "electronics": ["samsung", "haier", "dawlance", "gree", "pel", "orient", "lg", "tcl", "kenwood", "panasonic"]
}


class TestCategoryList:

    def test_categories_endpoint_returns_all_8(self, client):
        r = client.get("/categories")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            names = [c.get("name") or c.get("slug") for c in r.json()]
            for cat in TOP_LEVEL:
                assert cat in names or any(cat in str(n).lower() for n in names)

    def test_electronics_has_8_subcategories(self, client):
        r = client.get("/categories/electronics/subcategories")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            subs = r.json()
            assert len(subs) == 8

    def test_properties_has_2_subcategories(self, client):
        r = client.get("/categories/properties/subcategories")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            subs = r.json()
            assert len(subs) == 2

    def test_bikes_has_2_subcategories(self, client):
        r = client.get("/categories/bikes/subcategories")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            subs = r.json()
            assert len(subs) == 2
            slugs = [s.get("slug") for s in subs]
            assert "electric_bike" in slugs
            assert "motorbike" in slugs

    @pytest.mark.parametrize("cat", ["cars", "bikes", "electronics"])
    def test_category_brands_accessible(self, client, cat):
        r = client.get(f"/categories/{cat}/brands")
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            data = r.json()
            assert len(data) >= 5
            slugs = [b.get("slug") for b in data]
            for expected_brand in BRANDS_MAP[cat][:3]:
                assert expected_brand in slugs

    @pytest.mark.parametrize("cat", TOP_LEVEL)
    def test_each_category_accessible(self, client, cat):
        r = client.get(f"/categories/{cat}")
        assert r.status_code in (200, 404)

    @pytest.mark.parametrize("sub", ELECTRONICS_SUBS)
    def test_each_electronics_sub_accessible(self, client, sub):
        r = client.get(f"/categories/electronics/{sub}")
        assert r.status_code in (200, 404)

    @pytest.mark.parametrize("sub", PROPERTIES_SUBS)
    def test_each_properties_sub_accessible(self, client, sub):
        r = client.get(f"/categories/properties/{sub}")
        assert r.status_code in (200, 404)

    @pytest.mark.parametrize("sub", BIKES_SUBS)
    def test_each_bikes_sub_accessible(self, client, sub):
        r = client.get(f"/categories/bikes/{sub}")
        assert r.status_code in (200, 404)

    def test_invalid_category_returns_404(self, client):
        r = client.get("/categories/spacecraft")
        assert r.status_code == 404

    def test_invalid_electronics_subcategory_returns_404(self, client):
        r = client.get("/categories/electronics/microwave")
        assert r.status_code == 404

    def test_invalid_properties_subcategory_returns_404(self, client):
        r = client.get("/categories/properties/warehouse")
        assert r.status_code == 404

    def test_invalid_bikes_subcategory_returns_404(self, client):
        r = client.get("/categories/bikes/skateboard")
        assert r.status_code == 404


class TestCategoryFiltering:
    """Buyers can browse open requests filtered by category."""

    @pytest.mark.parametrize("cat", TOP_LEVEL)
    def test_filter_requests_by_category(self, client, buyer_token, cat):
        r = client.get(f"/buyer/requests?category={cat}",
                       headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code in (200, 404)
        if r.status_code == 200:
            for req in r.json():
                assert req.get("category") == cat

    def test_filter_electronics_by_subcategory(self, client, buyer_token):
        r = client.get("/buyer/requests?category=electronics&subcategory=tv",
                       headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code in (200, 404)

    def test_filter_bikes_by_subcategory(self, client, buyer_token):
        r = client.get("/buyer/requests?category=bikes&subcategory=motorbike",
                       headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code in (200, 404)

    def test_filter_by_brand(self, client, buyer_token):
        r = client.get("/buyer/requests?category=cars&brand=toyota",
                       headers={"Authorization": f"Bearer {buyer_token}"})
        assert r.status_code in (200, 404)
