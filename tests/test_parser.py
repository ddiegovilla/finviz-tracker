import pytest

from src.parser import ParseError, parse_screener


def test_extracts_metadata_without_logo_text(screener_html):
    page = parse_screener(screener_html(("TESTA", "TEST-B"), total=1234, logo=True))
    assert page.total == 1234
    assert page.row_numbers == [1, 2]
    assert [stock.ticker for stock in page.stocks] == ["TESTA", "TEST-B"]
    assert page.stocks[0].company == "Test Company & Co"
    assert page.stocks[0].sector == "Test Sector"
    assert page.stocks[0].industry == "Test Industry"


def test_explicit_zero_is_valid(screener_html):
    assert parse_screener(screener_html(())).stocks == []
    assert parse_screener('<div id="screener-views-table"><div id="screener-total">0 Total</div>No results found.</div>').stocks == []


def test_current_finviz_empty_results_markup_is_valid():
    html = """
        <html><title>Stock Screener - Overview</title>
        <div id="screener-content">
          <table id="screener-views-table"><tr><td>
            <table id="js-screener-body-empty"><tr>
              <td class="count-text">0 Total</td>
            </tr></table>
          </td></tr></table>
        </div></html>
    """
    page = parse_screener(html)
    assert page.total == 0
    assert page.stocks == []
    assert page.row_numbers == []


@pytest.mark.parametrize("html", [
    '<html><title>Just a moment...</title><form id="challenge-form"></form></html>',
    '<html><title>Login</title></html>',
    '<div>No results found</div>',
    '<div class="count-text">0 Total</div>',
    '<table id="js-screener-body-empty"><tr><td class="count-text">0 Total</td></tr></table>',
    '<div id="screener-total">5 Total</div>',
    '<div id="screener-total">unknown Total</div>',
])
def test_failed_parsing_never_becomes_empty_results(html):
    with pytest.raises(ParseError):
        parse_screener(html)


def test_missing_column_fails(screener_html):
    with pytest.raises(ParseError, match="columns"):
        parse_screener(screener_html().replace("<th>Industry</th>", "<th>Country</th>"))


def test_missing_rows_fails(screener_html):
    with pytest.raises(ParseError, match="no stock rows"):
        parse_screener(screener_html((), total=3))


def test_ticker_link_must_match(screener_html):
    with pytest.raises(ParseError, match="ticker/link"):
        parse_screener(screener_html().replace("t=TESTA", "t=TESTB"))
