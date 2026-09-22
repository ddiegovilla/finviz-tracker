"""Optional browser checks against a running dashboard and its real saved data."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    parser.add_argument("--chrome", default="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    parser.add_argument("--desktop-session", type=Path, help="Private session.json from a running desktop app")
    args = parser.parse_args()
    launch_url = args.url
    if args.desktop_session:
        launch_url = json.loads(args.desktop_session.read_text())["url"]
        parts = urlsplit(launch_url)
        args.url = f"{parts.scheme}://{parts.netloc}"
    output = Path("data/ui-review")
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chrome)
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, color_scheme="light")
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(launch_url)
        page.locator(".metrics").wait_for()
        payload = page.request.get(args.url + "/api/overview").json()
        stocks = payload["snapshot"]["stocks"]
        assert str(len(stocks)) == page.locator(".metric-value").first.inner_text()
        page.screenshot(path=str(output / "dashboard-light.png"), full_page=True)
        page.emulate_media(color_scheme="dark")
        page.screenshot(path=str(output / "dashboard-dark.png"), full_page=True)
        page.emulate_media(color_scheme="light")
        page.get_by_role("link", name="Screener", exact=True).click()
        page.locator("#stock-rows tr").first.wait_for()
        assert page.locator("#stock-rows tr").count() == min(50, len(stocks))
        page.screenshot(path=str(output / "screener-light.png"), full_page=True)
        page.locator('[data-group="sectors"] summary').click()
        for sector in ("Technology", "Energy"):
            page.get_by_role("checkbox", name=sector, exact=True).check()
        page.locator('[data-group="names"] summary').click()
        for name in ("Momentum", "Fortaleza"):
            page.get_by_role("checkbox", name=name, exact=True).check()
        expected_all = [stock for stock in stocks if stock["sector"] in ("Technology", "Energy") and all(name in stock["matched_filters"] for name in ("Momentum", "Fortaleza"))]
        assert page.locator("#result-count strong").inner_text() == str(len(expected_all))
        page.locator('input[name="filter-mode"][value="any"]').check()
        expected_any = [stock for stock in stocks if stock["sector"] in ("Technology", "Energy") and any(name in stock["matched_filters"] for name in ("Momentum", "Fortaleza"))]
        assert page.locator("#result-count strong").inner_text() == str(len(expected_any))
        page.locator('input[name="filter-mode"][value="all"]').check()
        page.locator("#screener-title").click()
        page.screenshot(path=str(output / "screener-filtered.png"), full_page=True)
        page.get_by_role("button", name="Reset filters", exact=True).click()
        page.get_by_role("searchbox", name="Search ticker or company").fill("zzzz-no-match-zzzz")
        assert page.locator("#table-empty").is_visible()
        page.get_by_role("button", name="Clear all filters").click()
        ticker = stocks[0]["ticker"]
        page.get_by_role("searchbox", name="Search ticker or company").fill(ticker)
        trigger = page.get_by_role("button", name=ticker, exact=True)
        trigger.click()
        page.locator(".history-table").wait_for()
        detail = page.request.get(args.url + f"/api/ticker?ticker={ticker}").json()
        assert page.locator(".history-table tbody tr").count() == len(detail["observations"])
        chart_maximum = max(detail["filter_count"], *(day["filter_count"] for day in detail["observations"]))
        for position, day in enumerate(detail["observations"]):
            column = page.locator(".history-column").nth(position)
            height = column.bounding_box()["height"]
            bar_height = column.locator(".history-bar").bounding_box()["height"]
            assert abs(bar_height - height * day["match_count"] / chart_maximum) < 1
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement === document.body || document.querySelector('#ticker-dialog').contains(document.activeElement)")
        page.locator("#close-detail").focus()
        page.screenshot(path=str(output / "ticker-detail.png"), animations="disabled")
        page.keyboard.press("Escape")
        assert not page.locator("#ticker-dialog").is_visible()
        assert trigger.evaluate("node => node === document.activeElement")
        page.get_by_role("button", name="Reset filters", exact=True).click()
        page.locator('[data-sort="ticker"]').click()
        first_ticker = page.locator("#stock-rows .ticker-link").first.inner_text()
        assert first_ticker == sorted(stock["ticker"] for stock in stocks)[0]
        page.locator('[data-sort="ticker"]').click()
        assert page.locator("th").first.get_attribute("aria-sort") == "descending"
        page.emulate_media(color_scheme="dark")
        page.screenshot(path=str(output / "screener-dark.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(output / "screener-mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        for group in ("sectors", "industries", "names", "counts"):
            page.locator(f'[data-group="{group}"] summary').click()
            bounds = page.locator(f'[data-group="{group}"] .filter-menu').bounding_box()
            assert bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= 390
            page.keyboard.press("Escape")
        page.get_by_role("link", name="Dashboard", exact=True).click()
        page.screenshot(path=str(output / "dashboard-mobile.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.emulate_media(reduced_motion="reduce")
        page.locator(".leader .ticker-link").first.click()
        page.locator(".history-table").wait_for()
        page.screenshot(path=str(output / "detail-mobile.png"), animations="disabled")
        page.keyboard.press("Escape")
        page.set_viewport_size({"width": 320, "height": 780})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.evaluate("document.documentElement.style.fontSize = '32px'")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Dashboard overflows at 200% text size"
        page.screenshot(path=str(output / "dashboard-large-text.png"), full_page=True)
        page.get_by_role("link", name="Screener", exact=True).click()
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Screener overflows at 200% text size"
        recovery_page = context.new_page()
        recovery_page.route("**/api/overview", lambda route: route.fulfill(status=503, json={"error": "Scan data temporarily unavailable."}))
        recovery_page.goto(args.url)
        recovery_page.get_by_role("alert").wait_for()
        assert recovery_page.get_by_role("button", name="Refresh data").is_enabled()
        recovery_page.unroute("**/api/overview")
        recovery_page.get_by_role("button", name="Refresh data").click()
        recovery_page.locator(".metrics").wait_for()
        assert recovery_page.locator("#notice").get_attribute("role") != "alert"
        recovery_page.route("**/api/overview", lambda route: route.fulfill(json={"empty": True, "message": "No scans yet."}))
        recovery_page.reload()
        recovery_page.get_by_role("heading", name="Your research starts with a scan").wait_for()
        recovery_page.get_by_role("link", name="Screener", exact=True).click()
        recovery_page.get_by_role("heading", name="No saved results for this date").wait_for(state="visible")
        recovery_page.close()
        assert not errors, errors
        report = {"passed": True, "stocks": len(stocks), "all_filter_matches": len(expected_all), "any_filter_matches": len(expected_any), "history_days": len(detail["observations"]), "large_text_200_percent": "passed", "browser_errors": errors, "screenshots": str(output)}
        (output / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        browser.close()


if __name__ == "__main__":
    main()
