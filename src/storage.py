import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from .aggregator import aggregate
from .models import FilterDefinition, Stock


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    run_date TEXT NOT NULL,
    run_timestamp TEXT NOT NULL,
    timezone TEXT NOT NULL,
    finished_timestamp TEXT,
    status TEXT NOT NULL CHECK(status IN ('running', 'complete', 'partial', 'failed', 'interrupted')),
    filter_count INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS runs_date ON runs(run_date, status);
CREATE TABLE IF NOT EXISTS filter_runs (
    run_id INTEGER NOT NULL REFERENCES runs(id),
    filter_name TEXT NOT NULL,
    position INTEGER NOT NULL,
    url TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending', 'success', 'failed')),
    ticker_count INTEGER,
    error TEXT,
    PRIMARY KEY (run_id, filter_name)
);
CREATE TABLE IF NOT EXISTS filter_results (
    run_id INTEGER NOT NULL,
    filter_name TEXT NOT NULL,
    ticker TEXT NOT NULL,
    company TEXT NOT NULL,
    sector TEXT NOT NULL,
    industry TEXT NOT NULL,
    PRIMARY KEY (run_id, filter_name, ticker),
    FOREIGN KEY (run_id, filter_name) REFERENCES filter_runs(run_id, filter_name)
);
CREATE TABLE IF NOT EXISTS ticker_results (
    run_id INTEGER NOT NULL REFERENCES runs(id),
    ticker TEXT NOT NULL,
    company TEXT NOT NULL,
    sector TEXT NOT NULL,
    industry TEXT NOT NULL,
    match_count INTEGER NOT NULL,
    matched_filters TEXT NOT NULL,
    PRIMARY KEY (run_id, ticker)
);
"""


class Storage:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def start_run(self, filters: list[FilterDefinition], timestamp: datetime, timezone_name: str) -> int:
        with self.connection:
            cursor = self.connection.execute(
                "INSERT INTO runs (run_date, run_timestamp, timezone, status, filter_count) VALUES (?, ?, ?, 'running', ?)",
                (timestamp.date().isoformat(), timestamp.isoformat(), timezone_name, len(filters)),
            )
            run_id = cursor.lastrowid
            self.connection.executemany(
                "INSERT INTO filter_runs (run_id, filter_name, position, url, status) VALUES (?, ?, ?, ?, 'pending')",
                [(run_id, definition.name, position, definition.url) for position, definition in enumerate(filters)],
            )
        return run_id

    def save_filter(self, run_id: int, name: str, stocks: list[Stock]) -> None:
        with self.connection:
            self.connection.executemany(
                "INSERT INTO filter_results VALUES (?, ?, ?, ?, ?, ?)",
                [(run_id, name, stock.ticker, stock.company, stock.sector, stock.industry) for stock in stocks],
            )
            self.connection.execute(
                "UPDATE filter_runs SET status = 'success', ticker_count = ?, error = NULL WHERE run_id = ? AND filter_name = ?",
                (len(stocks), run_id, name),
            )

    def fail_filter(self, run_id: int, name: str, error: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE filter_runs SET status = 'failed', error = ? WHERE run_id = ? AND filter_name = ?",
                (error, run_id, name),
            )

    def finish_run(self, run_id: int, timestamp: datetime, interrupted: bool = False) -> dict:
        filters = self.connection.execute(
            "SELECT * FROM filter_runs WHERE run_id = ? ORDER BY position", (run_id,)
        ).fetchall()
        successful = [row for row in filters if row["status"] == "success"]
        status = "complete" if len(successful) == len(filters) else "partial" if successful else "failed"
        if interrupted:
            status = "interrupted"
        results = {}
        for row in successful:
            stocks = self.connection.execute(
                "SELECT ticker, company, sector, industry FROM filter_results WHERE run_id = ? AND filter_name = ? ORDER BY ticker",
                (run_id, row["filter_name"]),
            ).fetchall()
            results[row["filter_name"]] = [Stock(**dict(stock)) for stock in stocks]
        with self.connection:
            self.connection.executemany(
                "INSERT INTO ticker_results VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (run_id, stock.ticker, stock.company, stock.sector, stock.industry, stock.match_count, json.dumps(stock.matched_filters, ensure_ascii=False))
                    for stock in aggregate(results)
                ],
            )
            self.connection.execute(
                "UPDATE runs SET status = ?, finished_timestamp = ? WHERE id = ?",
                (status, timestamp.isoformat(), run_id),
            )
        return self.snapshot(run_id)

    def snapshot(self, run_id: int) -> dict:
        run = self.connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if run is None:
            raise ValueError(f"Run {run_id} does not exist")
        filters = self.connection.execute(
            "SELECT filter_name, url, status, ticker_count, error FROM filter_runs WHERE run_id = ? ORDER BY position", (run_id,)
        ).fetchall()
        stocks = self.connection.execute(
            "SELECT ticker, company, sector, industry, match_count, matched_filters FROM ticker_results WHERE run_id = ? ORDER BY match_count DESC, ticker",
            (run_id,),
        ).fetchall()
        return {
            "run": dict(run),
            "filters": [dict(row) for row in filters],
            "stocks": [{**dict(row), "matched_filters": json.loads(row["matched_filters"])} for row in stocks],
        }

    def history(self, as_of: date, ticker: str | None = None, include_partial: bool = False) -> dict:
        start = as_of - timedelta(days=6)
        runs = self.connection.execute(
            "SELECT * FROM runs WHERE run_date BETWEEN ? AND ? ORDER BY id DESC",
            (start.isoformat(), as_of.isoformat()),
        ).fetchall()
        by_date = {}
        for run in runs:
            by_date.setdefault(run["run_date"], []).append(dict(run))
        coverage, tickers = [], {}
        for offset in range(7):
            day = (start + timedelta(days=offset)).isoformat()
            daily_runs = by_date.get(day, [])
            chosen = next((run for run in daily_runs if run["status"] == "complete"), None)
            if chosen is None and include_partial:
                chosen = next((run for run in daily_runs if run["status"] == "partial"), None)
            coverage.append({
                "date": day,
                "snapshot_run_id": chosen["id"] if chosen else None,
                "snapshot_status": chosen["status"] if chosen else "unavailable",
                "latest_attempt_status": daily_runs[0]["status"] if daily_runs else "not_scanned",
            })
            if chosen is None:
                continue
            for stock in self.snapshot(chosen["id"])["stocks"]:
                if ticker and stock["ticker"] != ticker.upper():
                    continue
                record = tickers.setdefault(stock["ticker"], {"ticker": stock["ticker"], "days_appeared": 0, "observations": []})
                record["days_appeared"] += 1
                record["observations"].append({
                    "date": day, "run_id": chosen["id"], "status": chosen["status"],
                    "filter_count": chosen["filter_count"], **stock,
                })
        return {"start_date": start.isoformat(), "end_date": as_of.isoformat(), "coverage": coverage, "tickers": [tickers[name] for name in sorted(tickers)]}
