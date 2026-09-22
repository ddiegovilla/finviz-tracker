"""Export the existing dashboard and saved scans as a GitHub Pages site."""

import argparse
import json
import shutil
from pathlib import Path

from .config import ROOT
from .dashboard_data import DashboardData


ASSETS = ("index.html", "styles.css", "app.js", "logic.js", "desktop.js", "favicon.svg")


def build_bundle(database: Path) -> dict:
    if not database.is_file():
        raise FileNotFoundError(f"Scan database does not exist: {database}")
    reader = DashboardData(database)
    try:
        latest = reader.overview()
        dates = latest["dates"]
        overviews = {}
        tickers = {}
        if not dates:
            latest["update_mode"] = "published"
            overviews[""] = latest
            tickers[""] = {}
        for scan_date in dates:
            overview = reader.overview(scan_date)
            overview["update_mode"] = "published"
            overviews[scan_date] = overview
            tickers[scan_date] = {}
            snapshot = overview["snapshot"]
            for stock in snapshot["stocks"] if snapshot else []:
                ticker = stock["ticker"]
                tickers[scan_date][ticker] = reader.ticker_detail(ticker, scan_date)
        return {
            "latest_date": dates[0] if dates else None,
            "overviews": overviews,
            "tickers": tickers,
        }
    finally:
        reader.close()


def export_site(database: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    for filename in ASSETS:
        source = ROOT / "frontend" / filename
        destination = output / filename
        if filename == "index.html":
            html = source.read_text(encoding="utf-8").replace(
                '<meta name="finviz-data-mode" content="api">',
                '<meta name="finviz-data-mode" content="static">',
            )
            destination.write_text(html, encoding="utf-8")
        else:
            shutil.copy2(source, destination)
    bundle = build_bundle(database)
    (output / "site-data.json").write_text(
        json.dumps(bundle, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    (output / ".nojekyll").touch()
    return bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a static Finviz Tracker site.")
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "finviz_history.db")
    parser.add_argument("--output", type=Path, default=ROOT / "site")
    args = parser.parse_args()
    bundle = export_site(args.db, args.output)
    stock_count = 0
    if bundle["latest_date"]:
        snapshot = bundle["overviews"][bundle["latest_date"]]["snapshot"]
        stock_count = len(snapshot["stocks"]) if snapshot else 0
    print(f"Static site written to {args.output} ({len(bundle['overviews'])} dates, {stock_count} latest stocks)")


if __name__ == "__main__":
    main()
