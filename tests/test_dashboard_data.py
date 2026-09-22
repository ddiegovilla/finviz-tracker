from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.dashboard_data import DashboardData
from src.models import FilterDefinition, Stock
from src.storage import Storage


NOW = datetime(2026, 9, 16, 18, tzinfo=ZoneInfo("America/Monterrey"))
FILTERS = [FilterDefinition("Momentum", "test-url"), FilterDefinition("Fortaleza", "test-url")]
STOCK = Stock("TESTA", "Test A", "Test Sector", "Test Industry")


def add_run(storage, timestamp=NOW, stocks=None, status="complete"):
    run_id = storage.start_run(FILTERS, timestamp, "America/Monterrey")
    if status in ("complete", "partial"):
        storage.save_filter(run_id, "Momentum", [STOCK] if stocks is None else stocks)
    else:
        storage.fail_filter(run_id, "Momentum", "Test failure")
    if status == "complete":
        storage.save_filter(run_id, "Fortaleza", [])
    else:
        storage.fail_filter(run_id, "Fortaleza", "Test failure")
    return storage.finish_run(run_id, timestamp)


def test_dashboard_uses_latest_complete_run_not_latest_failed_attempt(tmp_path):
    path = tmp_path / "history.db"
    storage = Storage(path)
    first = add_run(storage)
    add_run(storage, status="partial")
    add_run(storage, status="failed")
    storage.close()
    before = path.read_bytes()
    reader = DashboardData(path)
    overview = reader.overview()
    assert overview["snapshot"]["run"]["id"] == first["run"]["id"]
    assert overview["selected_attempt"]["status"] == "failed"
    assert overview["collected_days"] == 1
    assert overview["update_mode"] == "manual"
    reader.close()
    assert path.read_bytes() == before


def test_seven_collected_dates_not_seven_calendar_days(tmp_path):
    path = tmp_path / "history.db"
    storage = Storage(path)
    for offset in range(9):
        add_run(storage, NOW - timedelta(days=offset * 3))
    latest = add_run(storage, stocks=[])
    storage.close()
    reader = DashboardData(path)
    detail = reader.ticker_detail("testa")
    assert len(detail["observations"]) == 7
    assert detail["observations"][0]["date"] == "2026-08-29"
    assert detail["observations"][-1]["run_id"] == latest["run"]["id"]
    assert detail["observations"][-1]["match_count"] == 0
    assert detail["observations"][-1]["matched_filters"] == []
    assert detail["current"] is None
    assert detail["current_absence_known"]
    assert detail["days_appeared"] == 6
    reader.close()


def test_partial_is_visible_but_excluded_from_collected_history(tmp_path):
    path = tmp_path / "history.db"
    storage = Storage(path)
    add_run(storage, NOW - timedelta(days=1))
    add_run(storage, status="partial")
    storage.close()
    reader = DashboardData(path)
    assert reader.overview()["snapshot"]["run"]["status"] == "partial"
    detail = reader.ticker_detail("TESTA")
    assert not detail["current_absence_known"]
    assert len(detail["observations"]) == 1
    assert detail["observations"][0]["date"] == "2026-09-15"
    assert reader.overview("2026-09-15")["snapshot"]["run"]["status"] == "complete"
    reader.close()


def test_empty_database_and_uncollected_dates_are_not_fabricated(tmp_path):
    path = tmp_path / "history.db"
    Storage(path).close()
    reader = DashboardData(path)
    assert reader.overview()["snapshot"] is None
    assert reader.overview()["dates"] == []
    assert reader.overview("2026-09-16")["snapshot"] is None
    with pytest.raises(LookupError):
        reader.ticker_detail("TESTA")
    with pytest.raises(ValueError):
        reader.overview("not-a-date")
    with pytest.raises(Exception, match="readonly"):
        reader.connection.execute("DELETE FROM runs")
    reader.close()
