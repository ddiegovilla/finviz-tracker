import json
from datetime import datetime
from zoneinfo import ZoneInfo

from src.models import FilterDefinition, Stock
from src.static_site import export_site
from src.storage import Storage


def test_static_site_exports_api_data_and_relative_assets(tmp_path):
    database = tmp_path / "history.db"
    storage = Storage(database)
    filters = [FilterDefinition("Momentum", "test-url")]
    timestamp = datetime(2026, 9, 22, 16, tzinfo=ZoneInfo("America/Monterrey"))
    run_id = storage.start_run(filters, timestamp, "America/Monterrey")
    storage.save_filter(run_id, "Momentum", [Stock("TESTA", "Test A", "Technology", "Software")])
    storage.finish_run(run_id, timestamp)
    storage.close()

    output = tmp_path / "site"
    bundle = export_site(database, output)

    assert bundle["latest_date"] == "2026-09-22"
    assert bundle["overviews"]["2026-09-22"]["snapshot"]["stocks"][0]["ticker"] == "TESTA"
    assert bundle["tickers"]["2026-09-22"]["TESTA"]["days_appeared"] == 1
    saved = json.loads((output / "site-data.json").read_text())
    assert saved == bundle
    html = (output / "index.html").read_text()
    assert '<meta name="finviz-data-mode" content="static">' in html
    assert 'href="./styles.css"' in html
    assert (output / ".nojekyll").exists()


def test_static_site_supports_an_empty_history(tmp_path):
    database = tmp_path / "empty.db"
    Storage(database).close()
    bundle = export_site(database, tmp_path / "empty-site")
    assert bundle["latest_date"] is None
    assert bundle["overviews"][""]["dates"] == []
    assert bundle["overviews"][""]["snapshot"] is None
