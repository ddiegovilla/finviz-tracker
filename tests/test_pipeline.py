import pytest

from src.models import FilterDefinition, Stock
from src.pipeline import run_scan
from src.storage import Storage


def test_failed_filter_does_not_destroy_successful_filters(tmp_path):
    filters = [FilterDefinition(name, "test-url") for name in ("First", "Fails", "Last")]
    processed = []
    class Client:
        def scrape_filter(self, definition):
            processed.append(definition.name)
            if definition.name == "Fails":
                raise RuntimeError("Test failure")
            return [Stock("TESTA", "Test A", "Sector", "Industry")]
    storage = Storage(tmp_path / "history.db")
    result = run_scan(Client(), storage, filters, "America/Monterrey")
    assert processed == ["First", "Fails", "Last"]
    assert result["run"]["status"] == "partial"
    assert result["stocks"][0]["matched_filters"] == ["First", "Last"]
    assert result["filters"][1]["ticker_count"] is None
    assert result["filters"][1]["error"] == "Test failure"
    storage.close()


@pytest.mark.parametrize("interrupt", [False, True])
def test_total_failure_or_interruption_is_never_complete(tmp_path, interrupt):
    class Client:
        def scrape_filter(self, definition):
            if interrupt:
                raise KeyboardInterrupt()
            raise RuntimeError("Test failure")
    storage = Storage(tmp_path / "history.db")
    filters = [FilterDefinition("Test", "test-url")]
    if interrupt:
        with pytest.raises(KeyboardInterrupt):
            run_scan(Client(), storage, filters, "America/Monterrey")
    else:
        run_scan(Client(), storage, filters, "America/Monterrey")
    assert storage.snapshot(1)["run"]["status"] == ("interrupted" if interrupt else "failed")
    assert storage.snapshot(1)["stocks"] == []
    storage.close()
