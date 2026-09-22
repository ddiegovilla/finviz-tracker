from html import escape

import pytest


@pytest.fixture
def screener_html():
    def build(tickers=("TESTA",), offset=1, total=None, logo=False):
        count = len(tickers) if total is None else total
        rows = []
        for number, ticker in enumerate(tickers, start=offset):
            logo_html = '<a class="company-ticker"><span>T</span></a>' if logo else ""
            rows.append(
                f'<tr><td>{number}</td><td>{logo_html}<a class="tab-link" href="stock?t={escape(ticker)}">{escape(ticker)}</a></td>'
                '<td>Test Company &amp; Co</td><td>Test Sector</td><td>Test Industry</td></tr>'
            )
        return (
            '<html><title>Stock Screener</title><div id="screener-views-table">'
            f'<div id="screener-total">#{offset} / {count:,} Total</div>'
            '<table class="screener_table"><thead><tr><th>No.</th><th>Ticker</th>'
            '<th>Company</th><th>Sector</th><th>Industry</th></tr></thead>'
            + "".join(rows) + '</table></div></html>'
        )
    return build
