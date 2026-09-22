"""Browser smoke test for a generated GitHub Pages dashboard."""

import argparse
import json

from playwright.sync_api import sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8766")
    parser.add_argument("--chrome", default="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    args = parser.parse_args()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chrome)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url)
        page.locator(".metrics").wait_for()
        assert page.locator('meta[name="finviz-data-mode"]').get_attribute("content") == "static"
        stocks = int(page.locator(".metric-value").first.inner_text())
        assert stocks > 0
        assert page.locator("footer > span:last-child").inner_text() == "Published scans · Updates appear automatically"
        page.get_by_role("link", name="Screener", exact=True).click()
        page.locator("#stock-rows tr").first.wait_for()
        ticker = page.locator("#stock-rows .ticker-link").first.inner_text()
        page.get_by_role("button", name=ticker, exact=True).first.click()
        page.locator(".history-table").wait_for()
        assert page.locator(".history-table tbody tr").count() > 0
        assert not errors, errors
        print(json.dumps({"passed": True, "stocks": stocks, "ticker_detail": ticker}))
        browser.close()


if __name__ == "__main__":
    main()
