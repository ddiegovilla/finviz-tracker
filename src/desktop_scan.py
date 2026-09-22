import logging
import sqlite3
import threading
from datetime import datetime
from contextlib import closing
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import load_filters
from .finviz_client import FinvizClient
from .main import write_json
from .pipeline import run_scan
from .storage import Storage


class ScanCancelled(BaseException):
    pass


class DesktopClient(FinvizClient):
    def __init__(self, path, cancelled):
        super().__init__(path, timeout=10, retries=1)
        self.cancelled = cancelled

    def _wait(self, seconds):
        if self.cancelled.wait(seconds):
            raise ScanCancelled()

    def _fetch(self, url, name, offset):
        if self.cancelled.is_set():
            raise ScanCancelled()
        result = super()._fetch(url, name, offset)
        if self.cancelled.is_set():
            raise ScanCancelled()
        return result


class ScanManager(logging.Handler):
    def __init__(self, directory: Path, timezone_name: str):
        super().__init__()
        self.directory = directory
        self.database = directory / "finviz_history.db"
        self.timezone = timezone_name
        self.guard = threading.Lock()
        self.cancelled = threading.Event()
        self.worker = None
        self.running = False
        self.revision = 0
        self.message = ""
        self.outcome = "idle"
        self.closing = False

    def emit(self, record):
        if record.threadName == "finviz-scan":
            with self.guard:
                self.message = record.getMessage()

    def status(self):
        today = datetime.now(ZoneInfo(self.timezone)).date().isoformat()
        complete = False
        if self.database.exists():
            with closing(sqlite3.connect(self.database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
                complete = connection.execute("SELECT 1 FROM runs WHERE run_date=? AND status='complete' LIMIT 1", (today,)).fetchone() is not None
        with self.guard:
            return {"running": self.running, "message": self.message, "outcome": self.outcome,
                    "revision": self.revision, "today": today, "complete_today": complete,
                    "timezone": self.timezone}

    def start(self):
        with self.guard:
            if self.running or self.closing:
                return False
            self.running = True
            self.message = "Starting seven-filter scan…"
            self.outcome = "running"
            self.cancelled.clear()
            self.worker = threading.Thread(target=self._run, name="finviz-scan")
            self.worker.start()
            return True

    def _run(self):
        storage = client = None
        outcome, message = "failed", "Scan stopped unexpectedly. Previous history is safe."
        logging.getLogger().addHandler(self)
        try:
            storage = Storage(self.database)
            client = DesktopClient(self.directory / "debug", self.cancelled)
            result = run_scan(client, storage, load_filters(), self.timezone)
            run = result["run"]
            write_json(self.directory / "scans" / run["run_date"] / f"run-{run['id']}.json", result)
            write_json(self.directory / "latest-scan.json", result)
            outcome = run["status"]
            message = f"Scan {outcome}. {len(result['stocks'])} stocks saved."
            if outcome != "complete":
                message += " Some filters failed; see the scan details and try again later."
        except ScanCancelled:
            outcome, message = "interrupted", "Scan stopped. Completed filters remain saved."
        except Exception:
            logging.exception("Desktop scan failed")
            outcome, message = "failed", "Scan failed. Previous history is safe. Check your connection and try again."
        finally:
            logging.getLogger().removeHandler(self)
            if client:
                client.close()
            if storage:
                storage.close()
            with self.guard:
                self.running = False
                self.revision += 1
                self.outcome, self.message = outcome, message

    def shutdown(self):
        with self.guard:
            self.closing = True
            self.cancelled.set()
            worker = self.worker
        if worker:
            worker.join()
