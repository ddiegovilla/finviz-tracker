import threading
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.app_paths import prepare_data_dir
from src.config import load_filters
from src.desktop_scan import DesktopClient, ScanCancelled, ScanManager
from src.models import Stock
from src.storage import Storage


def test_cancel_interrupts_wait_and_never_requests_network(tmp_path):
    cancelled = threading.Event()
    cancelled.set()
    client = DesktopClient(tmp_path, cancelled)
    try:
        with pytest.raises(ScanCancelled):
            client._wait(60)
        with pytest.raises(ScanCancelled):
            client._fetch("https://finviz.com", "test", 1)
    finally:
        client.close()


def test_scan_exports_and_preserves_prior_dates(tmp_path, monkeypatch):
    manager = ScanManager(prepare_data_dir(tmp_path), "UTC")
    filters = load_filters()
    storage = Storage(manager.database)
    earlier = storage.start_run(filters, datetime(2026, 1, 1, tzinfo=ZoneInfo("UTC")), "UTC")
    for definition in filters:
        storage.save_filter(earlier, definition.name, [])
    storage.finish_run(earlier, datetime(2026, 1, 1, tzinfo=ZoneInfo("UTC")))
    storage.close()

    class FixtureClient:
        def __init__(self, *args):
            pass

        def scrape_filter(self, definition):
            return [Stock("FIXTURE", "Fixture Company", "Fixture Sector", "Fixture Industry")]

        def close(self):
            pass

    monkeypatch.setattr("src.desktop_scan.DesktopClient", FixtureClient)
    assert manager.start()
    manager.worker.join(5)
    assert manager.status()["outcome"] == "complete"
    assert manager.status()["complete_today"]
    assert (tmp_path / "latest-scan.json").exists()
    assert len(list((tmp_path / "scans").glob("*/*.json"))) == 1
    storage = Storage(manager.database)
    assert storage.snapshot(earlier)["run"]["run_date"] == "2026-01-01"
    assert storage.connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 2
    storage.close()


def test_interrupted_scan_retains_completed_filters(tmp_path, monkeypatch):
    manager = ScanManager(prepare_data_dir(tmp_path), "UTC")

    class InterruptingClient:
        def __init__(self, *args):
            self.calls = 0

        def scrape_filter(self, definition):
            self.calls += 1
            if self.calls == 2:
                raise ScanCancelled()
            return [Stock("FIXTURE", "Fixture Company", "Fixture Sector", "Fixture Industry")]

        def close(self):
            pass

    monkeypatch.setattr("src.desktop_scan.DesktopClient", InterruptingClient)
    assert manager.start()
    manager.worker.join(5)
    assert manager.status()["outcome"] == "interrupted"
    assert not manager.status()["complete_today"]
    storage = Storage(manager.database)
    assert storage.snapshot(1)["run"]["status"] == "interrupted"
    assert storage.snapshot(1)["stocks"][0]["match_count"] == 1
    storage.close()
