import re
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup

from .models import ScreenerPage, Stock


class ParseError(ValueError):
    pass


def parse_screener(html: str) -> ScreenerPage:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
    if any(marker in title for marker in ("just a moment", "access denied", "captcha", "attention required")) or soup.select_one("#challenge-form, #cf-challenge-running"):
        raise ParseError("Finviz returned a bot/challenge page")

    # Finviz uses a separate result-count element when a valid screener has no
    # matches. Keep the selectors narrow so an unrelated "0 Total" elsewhere
    # on the page can never turn a malformed response into a successful scan.
    total_element = soup.select_one(
        "#screener-total, #js-screener-body-empty .count-text"
    )
    if total_element is None:
        raise ParseError("Missing screener result count; possible challenge or changed markup")
    count_text = total_element.get_text(" ", strip=True)
    count_match = re.search(r"([\d,]+)\s+Total\b", count_text, re.I)
    if count_match is None:
        count_match = re.search(r"Total:\s*([\d,]+)", count_text, re.I)
    if count_match is None:
        raise ParseError(f"Unrecognized result count: {count_text!r}")
    total = int(count_match.group(1).replace(",", ""))

    table = soup.select_one("table.screener_table")
    if table is None:
        if total == 0 and soup.select_one("#screener-content, #screener-table, #screener-views-table"):
            return ScreenerPage([], [], 0)
        raise ParseError("Missing screener overview table")

    required = ("No.", "Ticker", "Company", "Sector", "Industry")
    header = table.find("tr")
    if header is None:
        raise ParseError("Missing table header")
    headers = [cell.get_text(" ", strip=True) for cell in header.find_all(["th", "td"], recursive=False)]
    if not all(name in headers for name in required):
        raise ParseError(f"Missing required overview columns: {headers}")
    positions = {name: headers.index(name) for name in required}
    stocks, row_numbers = [], []
    for row in table.find_all("tr"):
        if row is header:
            continue
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue
        if len(cells) != len(headers):
            raise ParseError("Malformed screener row; column count changed")
        fields = {name: cells[position].get_text(" ", strip=True) for name, position in positions.items()}
        ticker_cell = cells[positions["Ticker"]]
        ticker_link = ticker_cell.select_one("a.tab-link")
        if ticker_link is None:
            ticker_link = ticker_cell.select_one('a[href*="t="]')
        if ticker_link is None:
            raise ParseError("Missing ticker link")
        ticker = ticker_link.get_text(strip=True)
        linked_ticker = parse_qs(urlsplit(ticker_link.get("href", "")).query).get("t", [])
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-^/]*", ticker) or linked_ticker != [ticker]:
            raise ParseError(f"Invalid ticker/link: {ticker!r}")
        if not fields["No."].isdigit() or not all(fields[name] for name in ("Company", "Sector", "Industry")):
            raise ParseError(f"Missing metadata or invalid row number for {ticker}")
        row_numbers.append(int(fields["No."]))
        stocks.append(Stock(ticker, fields["Company"], fields["Sector"], fields["Industry"]))

    if total > 0 and not stocks:
        raise ParseError("Positive result count but no stock rows")
    if total == 0 and stocks:
        raise ParseError("Zero result count contradicts stock rows")
    return ScreenerPage(stocks, row_numbers, total)
