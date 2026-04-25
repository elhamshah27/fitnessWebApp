"""
Food API penetration tests.

Tests every angle of the food search, barcode, and log endpoints:
  - Happy path (real branded queries like Oreos, Chicken, etc.)
  - Edge cases (empty, whitespace, special characters, huge input)
  - Auth protection (all endpoints require login)
  - Input validation (bad types, missing fields, negative numbers)
  - Response shape (expected keys always present)

Run: python -m pytest tests/test_food_api.py -v
"""

import json
import os
import sys
import pytest

# Force a fresh test DB before main.py initializes its own DB at import time
_TEST_DB = os.path.join(os.path.dirname(__file__), "test.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB}")

# Make sure we can import main from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app, db, User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_app():
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{_TEST_DB}"
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SECRET_KEY"] = "test-secret"

    with app.app_context():
        db.drop_all()
        db.create_all()
        user = User(username="testuser", email="test@test.com", supabase_id="fake-supabase-id")
        db.session.add(user)
        db.session.commit()
        yield app
        db.drop_all()

    # Clean up test DB file (best-effort — Windows may hold the lock briefly)
    try:
        if os.path.exists(_TEST_DB):
            os.remove(_TEST_DB)
    except PermissionError:
        pass


@pytest.fixture
def client(test_app):
    return test_app.test_client()


@pytest.fixture
def logged_in_client(client, test_app):
    """Client with a session that has user_id set (bypasses Supabase auth)."""
    with test_app.app_context():
        user = User.query.filter_by(username="testuser").first()
        with client.session_transaction() as sess:
            sess["user_id"] = user.id
            sess["username"] = user.username
    return client


# ---------------------------------------------------------------------------
# AUTH PROTECTION — all food endpoints must redirect/401 without login
# ---------------------------------------------------------------------------

class TestAuthProtection:
    def test_food_search_requires_login(self, client):
        r = client.get("/api/food/search?q=oreo")
        assert r.status_code in (302, 401), "search must require login"

    def test_barcode_requires_login(self, client):
        r = client.get("/api/food/barcode/044000807429")
        assert r.status_code in (302, 401), "barcode endpoint must require login"

    def test_log_requires_login(self, client):
        r = client.post("/api/food/log", json={"name": "Oreo"})
        assert r.status_code in (302, 401), "log endpoint must require login"

    def test_delete_log_requires_login(self, client):
        r = client.delete("/api/food/log/1")
        assert r.status_code in (302, 401), "delete log must require login"


# ---------------------------------------------------------------------------
# FOOD SEARCH ENDPOINT  /api/food/search?q=...
# ---------------------------------------------------------------------------

class TestFoodSearch:
    def test_empty_query_returns_empty_list(self, logged_in_client):
        r = logged_in_client.get("/api/food/search?q=")
        assert r.status_code == 200
        data = r.get_json()
        assert data["products"] == []

    def test_whitespace_only_query(self, logged_in_client):
        r = logged_in_client.get("/api/food/search?q=   ")
        assert r.status_code == 200
        data = r.get_json()
        assert data["products"] == []

    def test_missing_q_param(self, logged_in_client):
        r = logged_in_client.get("/api/food/search")
        assert r.status_code == 200
        data = r.get_json()
        assert data["products"] == []

    def test_response_has_products_key(self, logged_in_client):
        r = logged_in_client.get("/api/food/search?q=apple")
        assert r.status_code == 200
        data = r.get_json()
        assert "products" in data

    def test_each_product_has_required_keys(self, logged_in_client):
        r = logged_in_client.get("/api/food/search?q=banana")
        assert r.status_code == 200
        products = r.get_json()["products"]
        required = {"name", "brand", "barcode", "image", "serving_size",
                    "calories", "protein", "carbs", "fat", "fiber", "sugar", "sodium"}
        for p in products:
            missing = required - p.keys()
            assert not missing, f"Product missing keys: {missing} — product: {p.get('name')}"

    def test_no_internal_fields_leaked(self, logged_in_client):
        r = logged_in_client.get("/api/food/search?q=chicken")
        products = r.get_json()["products"]
        for p in products:
            assert "_relevance" not in p, "Internal _relevance field leaked to client"
            assert "_source" not in p, "Internal _source field leaked to client"

    def test_max_25_results(self, logged_in_client):
        r = logged_in_client.get("/api/food/search?q=rice")
        products = r.get_json()["products"]
        assert len(products) <= 25

    def test_numeric_fields_are_numbers(self, logged_in_client):
        r = logged_in_client.get("/api/food/search?q=egg")
        products = r.get_json()["products"]
        numeric = ["calories", "protein", "carbs", "fat", "fiber", "sugar", "sodium"]
        for p in products:
            for field in numeric:
                assert isinstance(p[field], (int, float)), \
                    f"{field} is not numeric for product '{p.get('name')}': {p[field]}"

    def test_no_negative_macro_values(self, logged_in_client):
        r = logged_in_client.get("/api/food/search?q=milk")
        products = r.get_json()["products"]
        for p in products:
            for field in ["calories", "protein", "carbs", "fat"]:
                assert p[field] >= 0, \
                    f"Negative {field} for '{p.get('name')}': {p[field]}"

    # Branded product tests — these hit live APIs so they may be skipped in CI
    @pytest.mark.live
    def test_oreo_returns_results(self, logged_in_client):
        r = logged_in_client.get("/api/food/search?q=oreo")
        products = r.get_json()["products"]
        assert len(products) > 0, "Oreo search returned no results"
        names = [p["name"].lower() for p in products]
        assert any("oreo" in n for n in names), f"No Oreo product in results: {names[:5]}"

    @pytest.mark.live
    def test_branded_product_has_brand_name(self, logged_in_client):
        r = logged_in_client.get("/api/food/search?q=coca cola")
        products = r.get_json()["products"]
        assert len(products) > 0
        brands = [p["brand"] for p in products]
        assert any(b and b != "Generic" for b in brands), \
            "No branded results for Coca Cola"

    @pytest.mark.live
    def test_generic_food_returns_results(self, logged_in_client):
        r = logged_in_client.get("/api/food/search?q=chicken breast")
        products = r.get_json()["products"]
        assert len(products) > 0

    @pytest.mark.live
    def test_restaurant_food_results(self, logged_in_client):
        r = logged_in_client.get("/api/food/search?q=mcdonalds big mac")
        products = r.get_json()["products"]
        assert len(products) > 0


# ---------------------------------------------------------------------------
# EDGE CASES / SECURITY — SQL injection, XSS, huge payloads
# ---------------------------------------------------------------------------

class TestEdgeCases:
    PAYLOADS = [
        "'; DROP TABLE food_logs; --",
        "<script>alert('xss')</script>",
        "A" * 500,
        "🍕🍔🌮",
        "null",
        "undefined",
        "0",
        "../../../etc/passwd",
        "%00",
        "SELECT * FROM users",
    ]

    @pytest.mark.parametrize("payload", PAYLOADS)
    def test_search_does_not_crash_on_weird_input(self, logged_in_client, payload):
        r = logged_in_client.get(f"/api/food/search?q={payload}")
        assert r.status_code == 200, f"Crashed on input: {payload!r}"
        data = r.get_json()
        assert "products" in data

    @pytest.mark.parametrize("payload", PAYLOADS)
    def test_barcode_does_not_crash_on_weird_input(self, logged_in_client, payload):
        r = logged_in_client.get(f"/api/food/barcode/{payload}")
        assert r.status_code in (200, 400, 404)


# ---------------------------------------------------------------------------
# FOOD LOG ENDPOINT  POST /api/food/log
# ---------------------------------------------------------------------------

class TestFoodLog:
    BASE_PAYLOAD = {
        "name": "Oreo Cookies",
        "brand": "Nabisco",
        "barcode": "044000807429",
        "serving_size": 1,
        "serving_unit": "serving",
        "meal_type": "snack",
        "calories": 160,
        "protein": 1.5,
        "carbs": 25,
        "fat": 7,
        "fiber": 0.5,
        "sugar": 14,
        "sodium": 135,
    }

    def test_valid_log_succeeds(self, logged_in_client):
        r = logged_in_client.post("/api/food/log", json=self.BASE_PAYLOAD)
        assert r.status_code == 200
        data = r.get_json()
        assert data["success"] is True

    def test_response_has_success_key(self, logged_in_client):
        r = logged_in_client.post("/api/food/log", json=self.BASE_PAYLOAD)
        data = r.get_json()
        assert "success" in data

    def test_missing_name_still_handled(self, logged_in_client):
        payload = dict(self.BASE_PAYLOAD)
        del payload["name"]
        r = logged_in_client.post("/api/food/log", json=payload)
        assert r.status_code == 200  # should not 500

    def test_negative_calories_stored(self, logged_in_client):
        payload = {**self.BASE_PAYLOAD, "calories": -50}
        r = logged_in_client.post("/api/food/log", json=payload)
        assert r.status_code == 200

    def test_string_calories_handled(self, logged_in_client):
        payload = {**self.BASE_PAYLOAD, "calories": "not-a-number"}
        r = logged_in_client.post("/api/food/log", json=payload)
        # Should either succeed with 0 or return error — must not 500
        assert r.status_code == 200
        data = r.get_json()
        assert "success" in data

    def test_zero_serving_size(self, logged_in_client):
        payload = {**self.BASE_PAYLOAD, "serving_size": 0}
        r = logged_in_client.post("/api/food/log", json=payload)
        assert r.status_code == 200

    def test_empty_json_body(self, logged_in_client):
        r = logged_in_client.post(
            "/api/food/log",
            data="",
            content_type="application/json"
        )
        assert r.status_code in (200, 400)

    def test_xss_in_food_name(self, logged_in_client):
        payload = {**self.BASE_PAYLOAD, "name": "<script>alert(1)</script>"}
        r = logged_in_client.post("/api/food/log", json=payload)
        assert r.status_code == 200

    def test_sql_injection_in_food_name(self, logged_in_client):
        payload = {**self.BASE_PAYLOAD, "name": "'; DROP TABLE food_logs; --"}
        r = logged_in_client.post("/api/food/log", json=payload)
        assert r.status_code == 200
        # Verify tables still exist by doing another valid log
        r2 = logged_in_client.post("/api/food/log", json=self.BASE_PAYLOAD)
        assert r2.status_code == 200

    def test_very_long_food_name(self, logged_in_client):
        payload = {**self.BASE_PAYLOAD, "name": "X" * 500}
        r = logged_in_client.post("/api/food/log", json=payload)
        assert r.status_code == 200

    def test_all_meal_types_accepted(self, logged_in_client):
        for meal in ["breakfast", "lunch", "dinner", "snack"]:
            payload = {**self.BASE_PAYLOAD, "meal_type": meal}
            r = logged_in_client.post("/api/food/log", json=payload)
            assert r.status_code == 200, f"meal_type={meal} failed"


# ---------------------------------------------------------------------------
# DELETE LOG ENDPOINT  DELETE /api/food/log/<id>
# ---------------------------------------------------------------------------

class TestDeleteFoodLog:
    def test_delete_nonexistent_log(self, logged_in_client):
        r = logged_in_client.delete("/api/food/log/999999")
        assert r.status_code == 200
        data = r.get_json()
        assert data["success"] is False

    def test_delete_own_log(self, logged_in_client):
        # First create a log
        payload = {
            "name": "Test Food", "brand": "", "barcode": "",
            "serving_size": 1, "serving_unit": "serving", "meal_type": "snack",
            "calories": 100, "protein": 5, "carbs": 10, "fat": 3,
            "fiber": 1, "sugar": 2, "sodium": 50,
        }
        create_r = logged_in_client.post("/api/food/log", json=payload)
        assert create_r.get_json()["success"] is True

        # Get the log ID from the DB
        with app.app_context():
            from main import FoodLog, User
            user = User.query.filter_by(username="testuser").first()
            log = FoodLog.query.filter_by(user_id=user.id).order_by(FoodLog.id.desc()).first()
            log_id = log.id

        r = logged_in_client.delete(f"/api/food/log/{log_id}")
        assert r.status_code == 200
        data = r.get_json()
        assert data["success"] is True


# ---------------------------------------------------------------------------
# BARCODE ENDPOINT  GET /api/food/barcode/<barcode>
# ---------------------------------------------------------------------------

class TestBarcodeEndpoint:
    def test_response_has_found_key(self, logged_in_client):
        r = logged_in_client.get("/api/food/barcode/000000000000")
        assert r.status_code == 200
        data = r.get_json()
        assert "found" in data

    def test_invalid_barcode_returns_not_found(self, logged_in_client):
        r = logged_in_client.get("/api/food/barcode/000000000000")
        assert r.status_code == 200
        data = r.get_json()
        assert data["found"] is False

    @pytest.mark.live
    def test_oreo_barcode_lookup(self, logged_in_client):
        # Oreo original barcode
        r = logged_in_client.get("/api/food/barcode/044000807429")
        assert r.status_code == 200
        data = r.get_json()
        if data["found"]:
            product = data["product"]
            assert product["calories"] > 0
            assert "name" in product
