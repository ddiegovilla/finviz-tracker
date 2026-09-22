import json

from src.main import main
from src.models import FilterDefinition, Stock


def test_cli_scan_persists_json_and_history(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("src.main.load_filters", lambda path: [FilterDefinition("Test", "test-url")])
    monkeypatch.setattr("src.main.FinvizClient.scrape_filter", lambda self, definition: [Stock("TESTA", "Test A", "Sector", "Industry")])
    database = tmp_path / "history.db"
    export = tmp_path / "latest.json"
    assert main(["scan", "--db", str(database), "--output", str(export), "--format", "json"]) == 0
    snapshot = json.loads(capsys.readouterr().out)
    assert snapshot == json.loads(export.read_text())
    saved = tmp_path / "scans" / snapshot["run"]["run_date"] / "run-1.json"
    assert json.loads(saved.read_text()) == snapshot
    assert main(["history", "--db", str(database), "--as-of", snapshot["run"]["run_date"], "--format", "json"]) == 0
    history = json.loads(capsys.readouterr().out)
    assert history["tickers"][0]["days_appeared"] == 1
    assert history["tickers"][0]["observations"][0]["matched_filters"] == ["Test"]


def test_cli_failed_scan_has_nonzero_exit_and_visible_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("src.main.load_filters", lambda path: [FilterDefinition("Test", "test-url")])
    def fail(self, definition):
        raise RuntimeError("Test blocked page")
    monkeypatch.setattr("src.main.FinvizClient.scrape_filter", fail)
    assert main(["scan", "--db", str(tmp_path / "history.db")]) == 1
    output = capsys.readouterr().out
    assert "FAILED" in output
    assert "unknown tickers" in output
    assert "INCOMPLETE" in output
