"""Read-only dashboard queries layered over the existing scan storage."""

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .storage import Storage


class DashboardData(Storage):
    def __init__(self, path: Path):
        self.connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA query_only = ON")
        self.connection.execute("BEGIN")

    def overview(self, selected_date: str | None = None) -> dict:
        if selected_date:
            date.fromisoformat(selected_date)
        dates = [row[0] for row in self.connection.execute("SELECT DISTINCT run_date FROM runs ORDER BY run_date DESC")]
        selected_date = selected_date or (dates[0] if dates else None)
        latest = self.connection.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 1").fetchone()
        timezone_name = latest["timezone"] if latest else "America/Monterrey"
        attempts = self.connection.execute(
            "SELECT * FROM runs WHERE run_date = ? ORDER BY id DESC", (selected_date,)
        ).fetchall()
        chosen = next((run for run in attempts if run["status"] == "complete"), None)
        if chosen is None:
            chosen = next((run for run in attempts if run["status"] == "partial"), None)
        collected = self.collected_runs(selected_date) if selected_date else []
        return {
            "today": datetime.now(ZoneInfo(timezone_name)).date().isoformat(),
            "timezone": timezone_name,
            "dates": dates,
            "selected_date": selected_date,
            "latest_attempt": dict(latest) if latest else None,
            "selected_attempt": dict(attempts[0]) if attempts else None,
            "snapshot": self.snapshot(chosen["id"]) if chosen else None,
            "collected_days": len(collected),
            "update_mode": "manual",
        }

    def collected_runs(self, as_of: str) -> list[dict]:
        rows = self.connection.execute(
            "SELECT * FROM runs WHERE id IN ("
            "SELECT MAX(id) FROM runs WHERE status = 'complete' AND run_date <= ? "
            "GROUP BY run_date ORDER BY run_date DESC LIMIT 7) ORDER BY run_date",
            (as_of,),
        ).fetchall()
        return [dict(row) for row in rows]

    def ticker_detail(self, ticker: str, selected_date: str | None = None) -> dict:
        overview = self.overview(selected_date)
        ticker = ticker.upper()
        snapshot = overview["snapshot"]
        current = next((stock for stock in snapshot["stocks"] if stock["ticker"] == ticker), None) if snapshot else None
        observations = []
        metadata = current
        for run in self.collected_runs(overview["selected_date"]) if overview["selected_date"] else []:
            stock = self.connection.execute(
                "SELECT * FROM ticker_results WHERE run_id = ? AND ticker = ?", (run["id"], ticker)
            ).fetchone()
            if stock:
                metadata = current or dict(stock)
            observations.append({
                "date": run["run_date"], "run_id": run["id"], "filter_count": run["filter_count"],
                "match_count": stock["match_count"] if stock else 0,
                "matched_filters": json.loads(stock["matched_filters"]) if stock else [],
            })
        if metadata is None:
            raise LookupError(f"No collected observations for {ticker}")
        complete = snapshot is not None and snapshot["run"]["status"] == "complete"
        return {
            "ticker": ticker,
            "company": metadata["company"], "sector": metadata["sector"], "industry": metadata["industry"],
            "selected_date": overview["selected_date"],
            "current": current,
            "current_absence_known": complete,
            "snapshot_status": snapshot["run"]["status"] if snapshot else "unavailable",
            "filter_count": snapshot["run"]["filter_count"] if snapshot else None,
            "observations": observations,
            "days_appeared": sum(day["match_count"] > 0 for day in observations),
        }
