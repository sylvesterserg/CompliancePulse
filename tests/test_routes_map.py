from pathlib import Path


def test_ui_templates_exist():
    templates = [
        "dashboard.html",
        "rules.html",
        "scans.html",
        "reports.html",
        "partials/rules_table.html",
        "partials/scans_table.html",
        "partials/schedules_table.html",
        "partials/reports_table.html",
        "partials/rule_groups.html",
        "modals/rule_new.html",
        "modals/scan_trigger.html",
        "modals/schedule_new.html",
        "modals/report_view.html",
        "auth/login.html",
        "auth/logout.html",
        "auth/register.html",
        "auth/org_create.html",
        "layout.html",
    ]
    root = Path("frontend/templates")
    missing = [t for t in templates if not (root / t).exists()]
    assert not missing, f"Missing templates: {missing}"


def test_static_assets_present():
    static_root = Path("frontend/static")
    assert (static_root / "css" / "app.css").exists()
    assert (static_root / "js" / "htmx.js").exists()


def test_health_and_api_routes_present():
    # Basic smoke check for file presence that corresponds to routes
    assert Path("backend/app/main.py").exists()
    # Health and API endpoints are defined in main.py
    text = Path("backend/app/main.py").read_text(encoding="utf-8")
    assert "@app.get(\"/api\")" in text
    assert "@app.get(\"/health\")" in text
    assert "@app.get(\"/api/version\")" in text
    assert "@app.get(\"/api/ping\")" in text
