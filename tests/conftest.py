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


@pytest.fixture
def screener_grid_html():
    """Minimal server-rendered grid introduced by Finviz in October 2026."""
    def build(tickers=("TESTA",), offset=1, total=None):
        count = len(tickers) if total is None else total
        rows = []
        for number, ticker in enumerate(tickers, start=offset):
            rows.append(
                '<div role="row"><div role="presentation">'
                f'<div role="gridcell">{number}</div><div role="gridcell">'
                f'<a href="/quote?t={escape(ticker)}&amp;b=1">'
                '<span aria-hidden="true"><img alt=""><span>T</span></span>'
                f'<span>{escape(ticker)}</span></a></div></div><div role="presentation">'
                '<div role="gridcell">Test Company &amp; Co</div>'
                '<div role="gridcell">Test Sector</div>'
                '<div role="gridcell">Test Industry</div></div></div>'
            )
        return (
            '<div class="fv-table screener_results"><div class="fv-table_toolbar">'
            f'<p class="fv-table_toolbar-count">#{offset} / {count:,} Total</p></div>'
            '<div role="grid"><div role="rowgroup"><div role="row">'
            '<div role="presentation"><div role="columnheader">No.</div>'
            '<div role="columnheader">Ticker</div></div><div role="presentation">'
            '<div role="columnheader">Company</div><div role="columnheader">Sector</div>'
            '<div role="columnheader">Industry</div></div></div>'
            + "".join(rows) + '</div></div></div>'
        )
    return build
