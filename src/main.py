import argparse
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import ROOT, load_filters
from .finviz_client import FinvizClient
from .pipeline import run_scan
from .storage import Storage


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [max(len(header), *(len(row[position]) for row in rows)) if rows else len(header) for position, header in enumerate(headers)]
    print(" | ".join(header.ljust(width) for header, width in zip(headers, widths)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(value.ljust(width) for value, width in zip(row, widths)))


def print_snapshot(snapshot: dict) -> None:
    run = snapshot["run"]
    successful = sum(result["status"] == "success" for result in snapshot["filters"])
    print(f"Run {run['id']} | {run['run_date']} ({run['timezone']}) | {run['status'].upper()} | {successful}/{run['filter_count']} filters succeeded | {len(snapshot['stocks'])} unique tickers")
    for result in snapshot["filters"]:
        count = result["ticker_count"] if result["status"] == "success" else "unknown"
        print(f"  {result['filter_name']}: {result['status']} — {count} tickers" + (f" — {result['error']}" if result["error"] else ""))
    if run["status"] != "complete":
        print("INCOMPLETE: match counts are lower bounds; failed filters are unknown.")
    print_table(
        ["Ticker", "Company", "Sector", "Industry", "Matches", "Matched Filters"],
        [[stock["ticker"], stock["company"], stock["sector"], stock["industry"], f"{stock['match_count']}/{run['filter_count']}", ", ".join(stock["matched_filters"])] for stock in snapshot["stocks"]],
    )


def print_history(history: dict) -> None:
    print(f"History: {history['start_date']} through {history['end_date']} (7 calendar days)")
    for day in history["coverage"]:
        print(f"  {day['date']}: {day['snapshot_status']} (latest attempt: {day['latest_attempt_status']})")
    rows = []
    for ticker in history["tickers"]:
        for observation in ticker["observations"]:
            rows.append([ticker["ticker"], str(ticker["days_appeared"]), observation["date"], f"{observation['match_count']}/{observation['filter_count']}", observation["status"], ", ".join(observation["matched_filters"])])
    print_table(["Ticker", "Days Seen", "Date", "Matches", "Status", "Matched Filters"], rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan seven Finviz screeners and store daily match history.")
    parser.add_argument("command", nargs="?", choices=("scan", "history"), default="scan")
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "finviz_history.db")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "filters.json")
    parser.add_argument("--timezone", default="America/Monterrey", help="Calendar timezone for scans and today's history window")
    parser.add_argument("--delay", type=float, default=2.0, help="Minimum seconds between page requests (default: 2)")
    parser.add_argument("--format", choices=("table", "json"), default="table")
    parser.add_argument("--output", type=Path, help="Additional JSON export path")
    parser.add_argument("--ticker", help="History: show only this ticker")
    parser.add_argument("--as-of", type=date.fromisoformat, help="History: final date of the 7-day window (YYYY-MM-DD)")
    parser.add_argument("--include-partial", action="store_true", help="History: use a partial scan only when no complete scan exists that day")
    return parser


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    storage = None
    client = None
    try:
        timezone = ZoneInfo(args.timezone)
        storage = Storage(args.db)
        if args.command == "history":
            result = storage.history(args.as_of or datetime.now(timezone).date(), args.ticker, args.include_partial)
            exit_code = 0
        else:
            filters = load_filters(args.config)
            client = FinvizClient(args.db.parent / "debug", delay=args.delay)
            result = run_scan(client, storage, filters, args.timezone)
            run = result["run"]
            export_path = args.db.parent / "scans" / run["run_date"] / f"run-{run['id']}.json"
            write_json(export_path, result)
            logging.info("Saved SQLite run to %s and JSON to %s", args.db, export_path)
            exit_code = 0 if run["status"] == "complete" else 1
        if args.output:
            write_json(args.output, result)
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "history":
            print_history(result)
        else:
            print_snapshot(result)
        return exit_code
    except KeyboardInterrupt:
        logging.error("Scan interrupted; completed filters remain in SQLite")
        return 130
    except Exception:
        logging.exception("Command failed")
        return 2
    finally:
        if client is not None:
            client.close()
        if storage is not None:
            storage.close()


if __name__ == "__main__":
    sys.exit(main())
