"""End-to-end tests for Calquate fitness app using Playwright."""
import re
import time
import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:5000"
TEST_EMAIL = f"e2e_test_{int(time.time())}@test.example.com"
TEST_PASSWORD = "TestPass123!"
TEST_USERNAME = f"testuser{int(time.time())}"


# ── Helpers ──────────────────────────────────────────────────────────────────

def register_user(page: Page, username: str, email: str, password: str):
    page.goto(f"{BASE_URL}/register")
    page.fill("#username", username)
    page.fill("#email", email)
    page.fill("#password", password)
    page.click("button[type=submit]")
    page.wait_for_url(re.compile(r"/(profile|dashboard)"), timeout=10000)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_home_page_loads(page: Page):
    """Home page returns 200 and shows the brand name."""
    page.goto(BASE_URL)
    expect(page).to_have_title(re.compile(r"Calquate", re.IGNORECASE))


def test_register_page_has_form(page: Page):
    """Register page shows required fields."""
    page.goto(f"{BASE_URL}/register")
    expect(page.locator("#username")).to_be_visible()
    expect(page.locator("#email")).to_be_visible()
    expect(page.locator("#password")).to_be_visible()


def test_login_page_uses_email_field(page: Page):
    """Login page uses email (not username) after Supabase migration."""
    page.goto(f"{BASE_URL}/login")
    expect(page.locator("#email")).to_be_visible()
    expect(page.locator("#password")).to_be_visible()
    # username field should NOT be present
    assert page.locator("#username").count() == 0


def test_login_wrong_credentials_shows_error(page: Page):
    """Login with bad credentials shows error flash."""
    page.goto(f"{BASE_URL}/login")
    page.fill("#email", "nobody@nowhere.invalid")
    page.fill("#password", "wrongpassword")
    page.click("button[type=submit]")
    # Should stay on login and show an error
    expect(page).to_have_url(re.compile(r"/login"))
    expect(page.locator(".alert, .flash, [class*='error'], [class*='danger']")).to_be_visible(timeout=5000)


def test_protected_routes_redirect_to_login(page: Page):
    """Dashboard, food, diary all redirect to login when unauthenticated."""
    for path in ["/dashboard", "/food", "/diary", "/profile"]:
        page.goto(f"{BASE_URL}{path}")
        expect(page).to_have_url(re.compile(r"/login"), timeout=5000)


def test_calculator_page_loads(page: Page):
    """Calculator is publicly accessible."""
    page.goto(f"{BASE_URL}/calculator")
    expect(page).to_have_title(re.compile(r"Calculator", re.IGNORECASE))
    expect(page.locator("form")).to_be_visible()


def test_calculator_results(page: Page):
    """Submitting calculator form shows BMI results."""
    page.goto(f"{BASE_URL}/calculator")
    page.fill("[name=height]", "175")
    page.fill("[name=weight]", "70")
    page.fill("[name=age]", "25")
    page.check("[name=gender][value=male]")
    page.select_option("[name=activity]", "1.55")
    page.click("button[type=submit]")
    page.wait_for_url(re.compile(r"/calculator/results"), timeout=8000)
    # Should show BMI value on results page
    body = page.inner_text("body")
    assert "BMI" in body or "bmi" in body.lower()


def test_404_page(page: Page):
    """Unknown route returns a styled 404 page."""
    response = page.goto(f"{BASE_URL}/this-page-does-not-exist")
    assert response.status == 404
