import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote_plus, urlsplit, urlunsplit

import requests

from .models import FilterDefinition, Stock
from .parser import ParseError, parse_screener


LOGGER = logging.getLogger(__name__)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class ScrapeError(RuntimeError):
    pass


def page_url(url: str, offset: int) -> str:
    if offset < 1:
        raise ValueError("Pagination offsets start at 1")
    parts = urlsplit(url)
    parameters = [part for part in parts.query.split("&") if unquote_plus(part.split("=", 1)[0]) != "r"]
    if offset != 1:
        parameters.append(f"r={offset}")
    return urlunsplit(parts._replace(query="&".join(parameters)))


def validate_response_url(requested_url: str, response_url: str) -> None:
    requested = parse_qs(urlsplit(requested_url).query)
    response = urlsplit(response_url)
    if response.hostname not in ("finviz.com", "www.finviz.com") or response.path not in ("/screener", "/screener.ashx"):
        raise ScrapeError(f"Unexpected redirect: {response_url}")
    actual = parse_qs(response.query)
    for parameter in ("v", "f", "ft", "o"):
        if requested.get(parameter) != actual.get(parameter):
            raise ScrapeError(f"Redirect changed screener parameter {parameter}")
    if requested.get("r", ["1"]) != actual.get("r", ["1"]):
        raise ScrapeError("Redirect changed pagination offset")


class FinvizClient:
    def __init__(self, debug_dir: Path, delay: float = 2.0, timeout: float = 30.0, retries: int = 2):
        if delay < 0 or timeout <= 0 or retries < 0:
            raise ValueError("Invalid request timing or retry settings")
        self.debug_dir = debug_dir
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
        self.last_request = None

    def close(self) -> None:
        self.session.close()

    def _wait(self, seconds: float) -> None:
        time.sleep(seconds)

    def _save_failure(self, name: str, offset: int, html: str) -> Path:
        self.debug_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = self.debug_dir / f"{timestamp}-{slug}-r{offset}.html"
        path.write_text(html, encoding="utf-8")
        LOGGER.error("Failed-page HTML saved to %s", path)
        return path

    def _fetch(self, url: str, name: str, offset: int) -> str:
        for attempt in range(self.retries + 1):
            if self.last_request is not None:
                self._wait(max(0, self.delay - (time.monotonic() - self.last_request)))
            try:
                response = self.session.get(url, timeout=self.timeout)
            except requests.RequestException as error:
                if attempt == self.retries:
                    raise ScrapeError(f"Request failed for {url}: {error}") from error
                LOGGER.warning("%s r=%d: network error, retry %d/%d", name, offset, attempt + 1, self.retries)
                self._wait(2 ** (attempt + 1))
                continue
            finally:
                self.last_request = time.monotonic()

            response.encoding = "utf-8"
            if response.status_code != 200:
                self._save_failure(name, offset, response.text)
                retryable = response.status_code in (429, 500, 502, 503, 504)
                if retryable and attempt < self.retries:
                    retry_after = response.headers.get("Retry-After", "")
                    wait = max(2 ** (attempt + 1), int(retry_after)) if retry_after.isdigit() else 2 ** (attempt + 1)
                    if wait > 60:
                        raise ScrapeError(f"HTTP {response.status_code}; server requests {wait}s cooldown; rerun later")
                    LOGGER.warning("%s: HTTP %d, retrying in %ss", name, response.status_code, wait)
                    self._wait(wait)
                    continue
                raise ScrapeError(f"HTTP {response.status_code} for {url}")
            try:
                validate_response_url(url, response.url)
            except ScrapeError:
                self._save_failure(name, offset, response.text)
                raise
            return response.text
        raise ScrapeError("Retry limit exceeded")

    def scrape_filter(self, definition: FilterDefinition) -> list[Stock]:
        stocks = []
        seen = set()
        offset = 1
        expected_total = None
        while True:
            url = page_url(definition.url, offset)
            LOGGER.info("%s: fetching offset %d", definition.name, offset)
            html = self._fetch(url, definition.name, offset)
            try:
                page = parse_screener(html)
                if expected_total is None:
                    expected_total = page.total
                if page.total != expected_total:
                    raise ParseError(f"Result count changed during pagination ({expected_total} -> {page.total}); rerun scan")
                if page.row_numbers != list(range(offset, offset + len(page.stocks))):
                    raise ParseError("Row numbers do not match requested page; pagination may have repeated")
                if len(stocks) + len(page.stocks) > expected_total:
                    raise ParseError("Parsed more rows than Finviz reported")
                for stock in page.stocks:
                    if stock.ticker in seen:
                        raise ParseError(f"Duplicate ticker across pages: {stock.ticker}; results may have shifted")
                    seen.add(stock.ticker)
                if not page.stocks and len(stocks) != expected_total:
                    raise ParseError("Unexpected empty page before all results were read")
            except ParseError as error:
                self._save_failure(definition.name, offset, html)
                raise ScrapeError(f"{definition.name} r={offset}: {error}") from error
            stocks.extend(page.stocks)
            LOGGER.info("%s: page returned %d tickers (%d/%d)", definition.name, len(page.stocks), len(stocks), expected_total)
            if len(stocks) == expected_total:
                LOGGER.info("%s: complete, %d tickers", definition.name, len(stocks))
                return stocks
            offset += len(page.stocks)
