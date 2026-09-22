import json

import pytest

from src.storage import Storage
from src.web import make_handler


def request(path, database, host="127.0.0.1:8765"):
    handler = object.__new__(make_handler(database))
    handler.path = path
    handler.headers = {"Host": host}
    responses = []
    handler.respond = lambda status, body, content_type: responses.append((status, body, content_type))
    handler.do_GET()
    return responses[0]


def test_missing_database_gives_onboarding_without_creating_file(tmp_path):
    path = tmp_path / "missing.db"
    status, body, content_type = request("/api/overview", path)
    assert status == 200
    assert json.loads(body)["empty"]
    assert not path.exists()


@pytest.mark.parametrize("path", ["/data/finviz_history.db", "/../src/main.py", "/%2e%2e/README.md", "/api/scan"])
def test_only_explicit_assets_and_read_endpoints_are_served(tmp_path, path):
    assert request(path, tmp_path / "missing.db")[0] == 404


def test_invalid_dates_and_tickers_are_client_errors(tmp_path):
    path = tmp_path / "history.db"
    Storage(path).close()
    assert request("/api/overview?date=invalid", path)[0] == 400
    assert request("/api/ticker", path)[0] == 400
    assert request("/api/ticker?ticker=NOTFOUND", path)[0] == 404


def test_local_host_and_static_assets(tmp_path):
    assert request("/", tmp_path / "missing.db", host="untrusted.example")[0] == 403
    status, body, content_type = request("/", tmp_path / "missing.db")
    assert status == 200
    assert "text/html" in content_type
    assert b"Overlap" in body
