from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from src.config import ROOT, load_filters
from src.finviz_client import FinvizClient, ScrapeError, page_url, validate_response_url
from src.models import FilterDefinition


URL = "https://finviz.com/screener?v=111&f=first%2Csecond&ft=4&r=21&preset=test"


def test_configuration_urls_exactly_match_brief():
    brief = (ROOT / "PROJECT_BRIEF_FINVIZ_AUTOMATION.md").read_text()
    filters = load_filters()
    assert len(filters) == 7
    assert all(definition.url in brief for definition in filters)
    assert filters[5].name == "Volumen climático"


def test_pagination_changes_only_offset():
    assert page_url(URL, 1) == URL.replace("&r=21", "")
    assert page_url(URL, 41) == URL.replace("&r=21", "") + "&r=41"


def test_all_pages_start_at_first_even_if_config_has_r21(tmp_path, monkeypatch, screener_html):
    client = FinvizClient(tmp_path, delay=0)
    offsets = []
    def fetch(url, name, offset):
        offsets.append(offset)
        assert parse_qs(urlsplit(url).query).get("r", ["1"]) == [str(offset)]
        tickers = [f"TEST{number}" for number in range(offset, min(offset + 20, 24))]
        return screener_html(tickers, offset=offset, total=23)
    monkeypatch.setattr(client, "_fetch", fetch)
    assert len(client.scrape_filter(FilterDefinition("Test", URL))) == 23
    assert offsets == [1, 21]
    client.close()


@pytest.mark.parametrize("failure", ["repeated", "duplicate", "changed_total", "empty", "challenge"])
def test_incomplete_pagination_raises_and_saves_html(tmp_path, monkeypatch, screener_html, failure):
    client = FinvizClient(tmp_path, delay=0)
    def fetch(url, name, offset):
        if offset == 1:
            return screener_html(("TESTA",), total=2)
        if failure == "repeated":
            return screener_html(("TESTA",), total=2)
        if failure == "duplicate":
            return screener_html(("TESTA",), offset=2, total=2)
        if failure == "changed_total":
            return screener_html(("TESTB",), offset=2, total=3)
        if failure == "empty":
            return screener_html((), offset=2, total=2)
        return '<title>Just a moment...</title>'
    monkeypatch.setattr(client, "_fetch", fetch)
    with pytest.raises(ScrapeError):
        client.scrape_filter(FilterDefinition("Test", URL))
    assert len(list(tmp_path.glob("*.html"))) == 1
    client.close()


def test_redirect_can_drop_preset_but_not_filters_or_sort():
    requested = page_url(URL, 1)
    validate_response_url(requested, requested.replace("%2C", ",").replace("&preset=test", ""))
    with pytest.raises(ScrapeError):
        validate_response_url(requested, requested.replace("first%2Csecond", "first"))
    with pytest.raises(ScrapeError):
        validate_response_url(requested + "&o=sma50", requested)
    with pytest.raises(ScrapeError):
        validate_response_url(requested, "https://finviz.com/login")


def test_rate_limit_retries_and_keeps_failed_response(tmp_path, monkeypatch, screener_html):
    client = FinvizClient(tmp_path, delay=0)
    responses = []
    for status, html in [(429, "Rate limited"), (200, screener_html())]:
        response = requests.Response()
        response.status_code = status
        response.url = page_url(URL, 1)
        response._content = html.encode()
        responses.append(response)
    monkeypatch.setattr(client.session, "get", lambda *args, **kwargs: responses.pop(0))
    monkeypatch.setattr("src.finviz_client.time.sleep", lambda seconds: None)
    assert len(client.scrape_filter(FilterDefinition("Test", URL))) == 1
    assert next(tmp_path.glob("*.html")).read_text() == "Rate limited"
    client.close()
