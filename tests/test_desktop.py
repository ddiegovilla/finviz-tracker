import json
import sys
import threading
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from src.app_paths import app_data_dir, migrate_history, prepare_data_dir, resource_root
from src.config import load_filters
from src.desktop_scan import ScanManager
from src.desktop_server import desktop_handler
from src.storage import Storage


def test_app_data_paths(tmp_path):
    assert app_data_dir(tmp_path, "darwin") == tmp_path / "Library/Application Support/Finviz Tracker"
    assert app_data_dir(tmp_path, "linux") == tmp_path / ".local/share/finviz-tracker"


def test_directories_are_created_idempotently(tmp_path):
    directory = tmp_path / "new" / "Finviz Tracker"
    assert prepare_data_dir(directory) == directory
    prepare_data_dir(directory)
    assert all((directory / name).is_dir() for name in ("logs", "scans", "debug"))


def test_frozen_resources_are_separate_from_writable_data(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "app/Contents/Resources"), raising=False)
    assert resource_root() == tmp_path / "app/Contents/Resources"
    assert app_data_dir(tmp_path, "darwin") != resource_root()


def test_migration_preserves_source_and_never_overwrites_destination(tmp_path):
    source, destination = tmp_path / "old", tmp_path / "new"
    storage = Storage(source / "finviz_history.db")
    run_id = storage.start_run(load_filters(), datetime.now(ZoneInfo("UTC")), "UTC")
    storage.close()
    snapshot = source / "scans" / "2026-09-16" / "run-1.json"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text('{"test": true}')
    original = (source / "finviz_history.db").read_bytes()
    assert migrate_history(source, destination)
    assert (source / "finviz_history.db").read_bytes() == original
    assert (destination / "scans/2026-09-16/run-1.json").read_text() == snapshot.read_text()
    assert not migrate_history(source, destination)
    migrated = Storage(destination / "finviz_history.db")
    assert migrated.snapshot(run_id)["run"]["id"] == run_id
    assert migrated.connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 1
    migrated.close()


def test_missing_or_invalid_migration_does_not_create_database(tmp_path):
    assert not migrate_history(tmp_path / "missing", tmp_path / "new")
    source = tmp_path / "invalid"
    source.mkdir()
    (source / "finviz_history.db").write_text("not a database")
    with pytest.raises(Exception):
        migrate_history(source, tmp_path / "new")
    assert not (tmp_path / "new/finviz_history.db").exists()
    assert not (tmp_path / "new/migration.db.tmp").exists()


def test_daily_complete_check_and_concurrent_scan_guard(tmp_path, monkeypatch):
    manager = ScanManager(prepare_data_dir(tmp_path), "UTC")
    assert not manager.status()["complete_today"]
    storage = Storage(manager.database)
    filters = load_filters()
    run_id = storage.start_run(filters, datetime.now(ZoneInfo("UTC")), "UTC")
    for definition in filters:
        storage.save_filter(run_id, definition.name, [])
    storage.finish_run(run_id, datetime.now(ZoneInfo("UTC")))
    storage.close()
    assert manager.status()["complete_today"]
    barrier = threading.Event()
    monkeypatch.setattr(manager, "_run", lambda: barrier.wait(2))
    assert manager.start()
    assert not manager.start()
    barrier.set()
    manager.shutdown()
    assert not manager.start()


def test_failed_scan_keeps_history_and_releases_guard(tmp_path, monkeypatch):
    manager = ScanManager(prepare_data_dir(tmp_path), "UTC")
    def fail():
        raise RuntimeError("test configuration failure")
    monkeypatch.setattr("src.desktop_scan.load_filters", fail)
    assert manager.start()
    manager.worker.join(5)
    assert manager.status()["outcome"] == "failed"
    assert not manager.status()["running"]
    assert manager.database.exists()


def desktop_request(tmp_path, method, path, **headers):
    manager = ScanManager(prepare_data_dir(tmp_path), "UTC")
    manager.start = lambda: True
    handler = object.__new__(desktop_handler(manager, "test-token"))
    handler.server = SimpleNamespace(server_port=1234)
    handler.path = path
    handler.headers = {"Host": "127.0.0.1:1234", **headers}
    responses = []
    handler.respond = lambda status, body, content_type: responses.append((status, json.loads(body)))
    getattr(handler, f"do_{method}")()
    return responses[0]


def test_desktop_reads_require_session_cookie(tmp_path):
    assert desktop_request(tmp_path, "GET", "/api/overview")[0] == 403
    assert desktop_request(tmp_path, "GET", "/api/desktop", Cookie="finviz_session=test-token")[0] == 200


def test_scan_requires_origin_cookie_and_csrf(tmp_path):
    headers = {"Cookie": "finviz_session=test-token", "Origin": "http://127.0.0.1:1234", "X-Finviz-Token": "test-token"}
    assert desktop_request(tmp_path, "POST", "/api/scan", **headers)[0] == 202
    for key in headers:
        incomplete = {name: value for name, value in headers.items() if name != key}
        assert desktop_request(tmp_path, "POST", "/api/scan", **incomplete)[0] == 403
    headers["Origin"] = "https://untrusted.example"
    assert desktop_request(tmp_path, "POST", "/api/scan", **headers)[0] == 403


def test_desktop_rejects_foreign_hosts_and_command_endpoints(tmp_path):
    assert desktop_request(tmp_path, "GET", "/api/desktop", Host="untrusted.example", Cookie="finviz_session=test-token")[0] == 403
    headers = {"Cookie": "finviz_session=test-token", "Origin": "http://127.0.0.1:1234", "X-Finviz-Token": "test-token"}
    assert desktop_request(tmp_path, "POST", "/api/shell", **headers)[0] == 404
