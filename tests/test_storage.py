from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.models import FilterDefinition, Stock
from src.storage import Storage


FILTERS = [FilterDefinition("Momentum", "test-url"), FilterDefinition("Volumen climático", "test-url")]
STOCK = Stock("TESTA", "Test A", "Sector", "Industry")
NOW = datetime(2026, 9, 16, 12, tzinfo=ZoneInfo("America/Monterrey"))


@pytest.fixture
def storage(tmp_path):
    database = Storage(tmp_path / "test.db")
    yield database
    database.close()


def save_run(storage, timestamp=NOW, stocks=None, partial=False):
    run_id = storage.start_run(FILTERS, timestamp, "America/Monterrey")
    storage.save_filter(run_id, "Momentum", [STOCK] if stocks is None else stocks)
    if partial:
        storage.fail_filter(run_id, "Volumen climático", "blocked")
    else:
        storage.save_filter(run_id, "Volumen climático", [STOCK] if stocks is None else stocks)
    return storage.finish_run(run_id, timestamp)


def test_persists_consolidation_and_exact_unicode_filters(storage):
    result = save_run(storage)
    assert result["run"]["status"] == "complete"
    assert result["stocks"][0]["match_count"] == 2
    assert result["stocks"][0]["matched_filters"] == ["Momentum", "Volumen climático"]
    assert storage.snapshot(result["run"]["id"]) == result


def test_seven_calendar_days_and_one_complete_snapshot_per_day(storage):
    save_run(storage, NOW - timedelta(days=7))
    save_run(storage, NOW - timedelta(days=6))
    save_run(storage, NOW + timedelta(days=1))
    save_run(storage)
    latest_complete = save_run(storage)
    save_run(storage, partial=True)
    history = storage.history(date(2026, 9, 16))
    assert len(history["coverage"]) == 7
    assert history["tickers"][0]["days_appeared"] == 2
    assert [row["date"] for row in history["tickers"][0]["observations"]] == ["2026-09-10", "2026-09-16"]
    assert history["coverage"][-1]["snapshot_run_id"] == latest_complete["run"]["id"]
    assert history["coverage"][-1]["latest_attempt_status"] == "partial"


def test_partial_days_are_opt_in_and_missing_days_are_visible(storage):
    save_run(storage, partial=True)
    assert storage.history(NOW.date())["tickers"] == []
    history = storage.history(NOW.date(), ticker="testa", include_partial=True)
    assert history["tickers"][0]["observations"][0]["status"] == "partial"
    assert history["coverage"][0]["latest_attempt_status"] == "not_scanned"
    assert storage.history(NOW.date(), ticker="ABSENT", include_partial=True)["tickers"] == []


def test_latest_complete_empty_snapshot_replaces_earlier_matches(storage):
    save_run(storage)
    save_run(storage, stocks=[])
    assert storage.history(NOW.date())["tickers"] == []
    assert storage.history(NOW.date())["coverage"][-1]["snapshot_status"] == "complete"


def test_persistence_survives_reopening(tmp_path):
    path = tmp_path / "history.db"
    storage = Storage(path)
    result = save_run(storage)
    storage.close()
    reopened = Storage(path)
    assert reopened.snapshot(result["run"]["id"]) == result
    reopened.close()
