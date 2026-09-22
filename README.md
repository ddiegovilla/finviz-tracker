# Finviz Filter Tracker

## macOS desktop application

Build the Apple Silicon application with `./scripts/build_macos.sh`. Open
`dist/Finviz Tracker.app`, or share `dist/Finviz Tracker-macOS-arm64.dmg`.
Python is included; recipients do not need Terminal. The native window includes
Run Scan, progress, saved history, and File → Import History. Desktop data lives in
`~/Library/Application Support/Finviz Tracker/`, outside the app bundle.
See [macOS build, migration, Gatekeeper, and distribution instructions](docs/MACOS_APP.md).
For another Mac, use the [short recipient guide](docs/MACOS_RECIPIENT_GUIDE.md).
The [release guide](docs/MACOS_RELEASE.md) separates private ad-hoc builds from
future Developer ID signing and notarization. [Portability diagnostics](docs/MACOS_PORTABILITY.md)
cover launch failures.
The CLI and browser development workflow below remain unchanged.

## Free hosted website

The project now includes a static exporter and a scheduled GitHub Pages workflow. This lets everyone use one public URL and receive updates without reinstalling the macOS app. See [the one-time GitHub Pages setup](docs/WEB_DEPLOYMENT.md). The hosted version runs scheduled scans in GitHub Actions and preserves the same complete/partial data safeguards as the desktop app.

Local Python pipeline and browser dashboard for the seven screeners in `PROJECT_BRIEF_FINVIZ_AUTOMATION.md`. The pipeline reads every result page, combines stocks by ticker, and saves daily observations in SQLite and JSON. The Overlap dashboard explores those saved observations without modifying the backend or database. No account credentials, paid API, recommendations, or trading integration.

## Install

Requires Python 3.12 or newer and internet access to Finviz. Run these commands from this repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Runtime dependencies are only `requests` and `beautifulsoup4`; aggregation uses Python dictionaries and persistence uses the standard-library SQLite module. This implementation was tested with Python 3.14.2.

## Run a complete scan

```bash
python -m src.main
```

Equivalent explicit command, also writing a convenient latest-result export:

```bash
python -m src.main scan --output data/latest-scan.json
```

Without activating the environment:

```bash
.venv/bin/python -m src.main
```

Each scan prints all tickers sorted by match count descending, then ticker ascending. The table includes company, sector, industry, count out of seven, and the exact filter names. Progress and errors go to stderr, including the filter, pagination offset, and collected/reported totals. Requests are sequential with a two-second minimum delay between page requests.

Every completed attempt writes:

- `data/finviz_history.db`: persistent runs, filter observations, statuses, and consolidated ticker results.
- `data/scans/YYYY-MM-DD/run-ID.json`: a dated JSON snapshot containing run metadata, per-filter counts/errors, and ranked stocks.
- `data/debug/*.html`: raw responses when an HTTP, redirect, parsing, or pagination check fails. Network failures without a response have no HTML to save.

Paths default to this repository regardless of the working directory. `--db /path/to/history.db` relocates the database and its adjacent `scans/` and `debug/` directories. `--output` writes an additional JSON export. Runtime data is ignored by Git; back up the database separately.

Machine-readable stdout:

```bash
python -m src.main scan --format json --output data/latest-scan.json
```

Exit codes: `0` means all configured filters succeeded; `1` means an incomplete or failed scan; `2` means a command/configuration/storage error; `130` means interrupted. History commands return `0` even when the selected window has no observations; inspect coverage in the output.

## Last seven calendar days

```bash
python -m src.main history
python -m src.main history --ticker FRO
python -m src.main history --as-of 2026-09-16 --format json
python -m src.main history --output data/history.json
```

The window includes the selected date and six preceding calendar days, including weekends. Each ticker shows dates observed, match counts, exact filter names, and the number of distinct days it appeared. Coverage lists every date, including days never scanned.

Multiple runs on one day remain stored. History uses the latest **complete** run for each date, so reruns do not inflate days seen or combine matches from different times. A later failed run does not replace an earlier complete snapshot. A later complete run with zero matches does replace earlier matches. Historical rows are retained indefinitely; the query selects only the seven-day window.

Partial scans are excluded by default. To use the latest partial run on a date with no complete run:

```bash
python -m src.main history --include-partial
```

Partial observations are labeled and their match counts are lower bounds. A failed filter is unknown, never treated as a successful zero-result filter. A genuinely empty filter is successful only if Finviz explicitly reports zero results. If any page of a filter fails, that filter's incomplete page collection is excluded, while other successful filters remain saved.

Scan dates use `America/Monterrey` by default, captured at scan start. Override with `--timezone America/New_York` if needed, and use the same timezone consistently for a database. Scan timestamps include the UTC offset; log timestamps use the host's local time. History does not fetch historical Finviz data or fill in dates before you began collecting snapshots.

## Verified live result

On **2026-09-16**, a real scan of all seven configured URLs completed successfully in about 36 seconds, reading 16 result pages and producing **206 unique tickers** from 237 filter matches:

| Filter | Tickers |
|---|---:|
| Momentum | 151 |
| Fortaleza | 34 |
| Strong up trend 1 | 1 |
| Strong up trend 2 | 14 |
| Strong up trend 3 | 5 |
| Volumen climático | 3 |
| Ganadores semanales | 29 |

Two actual rows from that saved scan:

| Ticker | Company | Sector | Industry | Matches | Matched Filters |
|---|---|---|---|---:|---|
| FRO | Frontline Plc | Energy | Oil & Gas Midstream | 4/7 | Momentum, Fortaleza, Strong up trend 3, Volumen climático |
| RVTY | Revvity Inc | Healthcare | Diagnostics & Research | 4/7 | Fortaleza, Strong up trend 1, Strong up trend 2, Strong up trend 3 |

These are recorded observations, not fixed expected results. Future scans will differ.

## Open the dashboard

From this repository, in a second terminal:

```bash
.venv/bin/python -m src.web
```

Open **http://127.0.0.1:8765** in your browser. Stop the server with Ctrl-C. No frontend package install, Node build, or additional runtime dependency is needed. The browser needs JavaScript and a current Chrome, Safari, or Firefox version.

Optional configuration:

```bash
.venv/bin/python -m src.web --port 8766 --db /absolute/path/to/finviz_history.db
```

The server binds to loopback only. It is intended for local personal use, not public internet hosting. It serves an explicit list of frontend assets and opens SQLite in read-only mode; the database, scan command, and arbitrary filesystem paths are not exposed through the browser.

### Dashboard

- Unique stocks, highest filter overlap, multiple-match stocks, and sector/industry totals.
- Highest-overlap ticker cards, with exact filter names and a seven-position membership strip.
- Match-count distribution, sector composition, industry breakdown, and per-filter coverage.
- Select a chart bar or category to open that subset in the Screener.
- Date selection, visible scan provenance, incomplete-scan warnings, and an explicit stale-date notice.
- Native system light/dark appearance, responsive layout, keyboard controls, reduced-motion support, and accessible chart labels.

### Screener

All six columns are sortable; match count descending is the default. Search ticker/company, combine multiple sectors, industries, match counts, and matched filters, or reset the selections. Choices within sector/industry/count use OR; categories combine using AND. Selected Finviz filters use **All (AND)** by default, with **Any (OR)** available.

For example, Technology + Energy and Momentum + Fortaleza in All mode means `(Technology OR Energy) AND Momentum AND Fortaleza`. Selected values remain visible as removable chips. The table includes a result count, page-size control, pagination, sticky column headers, and horizontal scrolling on narrow screens.

### Ticker detail and history

Select a ticker to open its detail panel with metadata, current filter matches, a bar chart, and an exact historical membership table. Escape or the close button dismisses it and returns focus. The dashboard shows up to **seven collected dates with complete scans**, choosing the latest complete run on each date. These dates may span more than seven calendar days. The CLI continues to use its original **seven-calendar-day** window.

A ticker absent from a complete collected scan gets a genuine zero for that date. Uncollected dates are not fabricated, and partial scans are excluded from the history chart. Partial current observations remain visibly marked as lower bounds. A one-day history is shown as one bar, with an explanation that new observations will appear as scans accumulate.

### Refreshing and daily updates

**Scans are still manual.** The dashboard does not contact Finviz or launch scans. Run `python -m src.main` to collect a new snapshot. **Refresh data** rereads SQLite only. While the dashboard is open and idle, it checks saved results every 60 seconds; it defers updates during input, filter-menu use, or ticker-detail inspection to preserve focus. The Latest date option follows new collected dates; a specifically selected date stays selected.

SQLite is the source of truth. `data/latest-scan.json` is only an optional export and can lag behind the database if a scan was run without `--output`. Every run has a new ID; same-day reruns and all previous dates remain intact. A newer failed attempt never replaces a complete snapshot for that date. No new history schema or migration is required.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The frontend's pure filtering/sorting tests use Node's built-in test runner (Node is optional for development tests, not required to run the app):

```bash
node --test tests/test_frontend.mjs
```

Optional browser checks use your installed Chrome and a running dashboard:

```bash
python -m pip install -r requirements-browser.txt
python scripts/check_dashboard.py
```

On a machine with Chrome in another location, pass `--chrome /path/to/chrome`. These checks use the real saved scan for counts, filter combinations, detail/history, sorting, light/dark screenshots, narrow layouts, keyboard behavior, and enlarged text. Screenshots are written to `data/ui-review/`. The design rationale and completed Apple-design audit are in [docs/DESIGN_REVIEW.md](docs/DESIGN_REVIEW.md).

Tests run offline, use synthetic records only inside temporary test databases, and cover parsing, ticker logo handling, empty/challenge pages, exact URL preservation, pagination, repeated/missing pages, redirects, HTTP retries, aggregation, filter failure isolation, interruption, persistence, and seven-day history selection. The scan command itself is the opt-in live integration test against all seven real URLs. A successful live scan must exit `0` and report `7/7 filters succeeded`.

## Structure

```text
config/filters.json       Exact names and complete original URLs from the brief
src/config.py            Configuration loading and validation
src/models.py            Stock, filter, page, and ranking records
src/finviz_client.py     HTTP acquisition, pacing, retries, and pagination checks
src/parser.py            Strict HTML extraction and challenge detection
src/aggregator.py        Deduplication, exact filter membership, and ranking
src/storage.py           SQLite persistence and seven-day snapshot queries
src/pipeline.py          Scan orchestration and per-filter failure isolation
src/main.py              CLI tables and JSON exports
src/dashboard_data.py    Read-only queries; reuses existing snapshot reconstruction
src/web.py               Local HTTP server and JSON read endpoints
frontend/index.html      Accessible application shell and navigation
frontend/styles.css      Responsive semantic light/dark styles
frontend/app.js           Dashboard, filtering controls, table, and ticker details
frontend/logic.js         Pure filter, sort, and distribution functions
frontend/favicon.svg     Local vector application mark
scripts/check_dashboard.py  Optional real-data browser checks
docs/DESIGN_REVIEW.md     Design decisions, HIG references, and audit findings
docs/DAILY_SCANS.md       Scheduling options and recommended macOS setup
tests/                   Offline regression tests
requirements.txt         Runtime dependencies
requirements-dev.txt     Test dependencies
requirements-browser.txt Optional browser-testing dependency
data/                    Generated database, snapshots, and failed-page HTML
```

SQLite tables:

- `runs`: calendar date, timezone, start/end timestamps, overall status, and filter count.
- `filter_runs`: configured URL, exact filter name/order, pending/success/failed status, count, and error.
- `filter_results`: company/sector/industry per `(run_id, filter_name, ticker)`.
- `ticker_results`: consolidated metadata, `match_count`, and JSON `matched_filters` per `(run_id, ticker)`.

Successful filters commit individually. Normal completion writes consolidated results and the final status in one transaction. Ctrl-C preserves completed filters and marks the run interrupted. A hard process kill can leave a run marked `running`; it is excluded from history, and a new scan creates a separate run.

## Finviz behavior and limitations

- The original URLs are stored unchanged. The client removes the initial `r=21` from Ganadores semanales and changes only `r` for pagination. It starts every filter at the first row and continues until the advertised total is reached.
- Finviz currently redirects URLs to remove `preset` and normalize comma encoding. The scraper follows that server redirect and verifies that view, filters, sort order, and pagination remain unchanged. No password or preset access is required for these explicit filter URLs.
- Direct `requests` acquisition worked for every filter in the live validation; a browser fallback was unnecessary. If access changes, inspect saved HTML first. Acquisition can be replaced while retaining the parser, aggregator, and storage modules.
- Timeouts and selected transient HTTP failures have bounded retries. HTTP 429 is retried with backoff and numeric `Retry-After` support; a requested cooldown over 60 seconds stops that filter so the scan can continue. Persistent blocks or markup changes produce explicit failures.
- Finviz is a live website: results can change while pages are read. The scraper rejects changing totals, duplicate tickers, and unexpected row numbers. It cannot provide an atomic market-wide snapshot or detect every possible membership change with an unchanged count. Rerun an incomplete scan, preferably when results are stable.
- Only fields present in the source are stored. Filters without `ind_stocksonly` can include ETFs or other instruments; the scraper preserves those results exactly.
- History starts with actual collected scans. The initial live run supplies one observed day; previous days remain unavailable.

## Daily operation and next work

Run one scan daily at your chosen time. No scheduler is installed automatically. Once ready, a local scheduler can invoke the absolute interpreter/module path from this repository, for example:

```bash
cd /Users/diegovillanuevafernandez/finviz-filter-tracker
/Users/diegovillanuevafernandez/finviz-filter-tracker/.venv/bin/python -m src.main scan --output data/latest-scan.json
```

The recommended macOS automation is a user LaunchAgent that invokes this existing command once daily. See [docs/DAILY_SCANS.md](docs/DAILY_SCANS.md) for the options, sleep/wake limitations, and configuration plan. **No scheduler has been installed or enabled.**

Next steps are choosing a daily scan time, adding the LaunchAgent with bounded failure handling, and collecting several days of real observations. Then consider saved screener presets and comparison with the previous collected day. Avoid overlapping scans; keep the database backed up.
