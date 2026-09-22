# Finviz Multi-Filter Automation — Project Brief

## Goal
Build a local-first Python project that automatically evaluates seven Finviz screeners, combines the results by ticker, and shows:
- Which stocks matched today.
- How many of the 7 filters each stock matched.
- Exactly which filters each stock matched.
- The history of matches over the last 7 days.

Frontend/dashboard work comes **after** the data pipeline is proven reliable.

## Recommended architecture
Start with Python for the data engine. Keep the first version local and simple.

Suggested stack:
- Python 3.12+
- requests + BeautifulSoup (first attempt for Finviz extraction)
- pandas for merging/counting/results
- SQLite for persistent 7-day history
- pytest for basic tests
- Later frontend: Streamlit for fastest local dashboard, or a separate frontend if desired

Do not start with React/Node or cloud hosting. First prove that all 7 Finviz filters can be read reliably.

## Core workflow
1. Load the 7 screener definitions.
2. Request each Finviz screener URL.
3. Parse every result page, including pagination if needed.
4. Extract at minimum:
   - ticker
   - company
   - sector
   - industry
5. Tag every extracted ticker with the filter it came from.
6. Merge all filters by ticker.
7. Compute:
   - match_count: 0-7
   - matched_filters: exact filter names
8. Save a dated daily snapshot.
9. Maintain/query the last 7 days of snapshots.
10. Produce a simple CLI/table output before building the frontend.

## Desired output for today
Example:

| Ticker | Company | Sector | Industry | Match Count | Matched Filters |
|---|---|---|---|---:|---|
| NVDA | NVIDIA | Technology | Semiconductors | 5/7 | Momentum, Fortaleza, Strong up trend 1, Strong up trend 2, Volumen climático |

Sort by `match_count` descending, then ticker ascending.

## Desired 7-day history
For every ticker, be able to answer:
- On which dates did it appear?
- How many filters did it match on each date?
- Which filters did it match on each date?
- Number of days it appeared during the last 7 calendar days.

Example conceptual record:

NVDA
- 2026-09-16: 5/7 — Momentum, Fortaleza, Strong up trend 1, Strong up trend 2, Volumen climático
- 2026-09-15: 4/7 — ...
- 2026-09-14: 6/7 — ...

## The 7 filters

### 1. Momentum
URL:
https://finviz.com/screener?v=111&f=cap_smallover%2Cfa_epsqoq_o25%2Cfa_epsyoyttm_pos%2Cfa_netmargin_pos%2Cfa_roe_pos%2Cfa_salesqoq_o10%2Cfa_salesyoyttm_pos%2Csh_avgvol_o100%2Csh_price_o10%2Cta_highlow52w_a50h%2Cta_sma20_sa50%2Cta_sma200_pa%2Cta_sma50_pa&ft=4&preset=s151555367

### 2. Fortaleza
URL:
https://finviz.com/screener?v=111&f=cap_smallover%2Cind_stocksonly%2Csh_avgvol_o200%2Cta_averagetruerange_o1%2Cta_highlow52w_a40h%2Cta_perf_ytdup%2Cta_perf2_4wup%2Cta_sma20_pa%2Cta_sma200_pa%2Cta_sma50_pa20&ft=4&o=sma50&preset=s151565349

### 3. Strong up trend 1
URL:
https://finviz.com/screener?v=111&f=cap_midover,sh_avgvol_o200,sh_price_o10,sh_relvol_o2,ta_gap_u,ta_highlow52w_nh,ta_pattern_channelup,ta_rsi_ob60,ta_sma200_pa&ft=4&preset=s149592627

### 4. Strong up trend 2
URL:
https://finviz.com/screener?v=111&f=cap_midover%2Csh_avgvol_o200%2Csh_price_o10%2Csh_relvol_o2%2Cta_sma20_pa%2Cta_sma200_pa%2Cta_sma50_pa&ft=4&o=perfytd&preset=s149592625

### 5. Strong up trend 3
URL:
https://finviz.com/screener?v=111&f=sh_avgvol_o200,sh_price_o10,ta_gap_u,ta_highlow52w_nh,ta_pattern_channelup,ta_rsi_ob60,ta_sma200_pa&ft=4&preset=s1495926355

### 6. Volumen climático
URL:
https://finviz.com/screener?v=111&f=cap_large%2Cind_stocksonly%2Csh_curvol_o5000%2Csh_relvol_o1.5%2Cta_change_u%2Cta_perf_1wup%2Cta_perf2_4wup&ft=4&preset=s149592629

### 7. Ganadores semanales
URL:
https://finviz.com/screener?v=111&f=sh_avgvol_o100%2Csh_price_o5%2Cta_perf_1w20o&ft=4&r=21&preset=s151629466

Important: `r=21` is only a pagination offset for the second results page. The scraper must not depend on this fixed value; it should start from the first page and handle pagination automatically.

## Filter display names
Use the names exactly as listed above for now:
1. Momentum
2. Fortaleza
3. Strong up trend 1
4. Strong up trend 2
5. Strong up trend 3
6. Volumen climático
7. Ganadores semanales

Later we may add friendly aliases such as “Momentum Extremo”, “Tendencia Fuerte”, etc., but do not change names unless explicitly requested.

## Reliability requirements
- Handle Finviz pagination.
- Use a realistic User-Agent.
- Add small delays between requests; avoid aggressive scraping.
- Detect HTTP errors, bot/challenge pages, or unexpected markup.
- Never silently return an empty set when parsing failed.
- Log how many tickers were found per filter.
- Save the raw HTML of a failed page for debugging.
- Do not require Finviz Elite or paid APIs for v1.
- Do not ask for or store the user's Finviz password.

## Data model suggestion
SQLite tables:

### runs
- id
- run_date
- run_timestamp
- status

### filter_results
- run_id
- filter_name
- ticker
- company
- sector
- industry

Unique key suggestion: `(run_id, filter_name, ticker)`.

This makes it easy to reconstruct daily rankings and the last 7 days.

## Suggested project structure
```text
finviz-filter-tracker/
├── README.md
├── requirements.txt
├── .gitignore
├── config/
│   └── filters.json
├── data/
│   └── finviz_history.db
├── src/
│   ├── __init__.py
│   ├── finviz_client.py
│   ├── parser.py
│   ├── aggregator.py
│   ├── storage.py
│   └── main.py
└── tests/
    ├── test_parser.py
    └── test_aggregator.py
```

## First milestone
Do not build a polished UI yet.

The first milestone is complete only when running one command, for example:

```bash
python -m src.main
```

prints a reliable table containing all current stocks from all enabled filters, match counts, and exact matched filters, and stores the run in SQLite.

Also include a second command or option to print the last 7 days of history.

## Implementation strategy
Start with `requests` + `BeautifulSoup`.

If Finviz blocks direct requests or the result table cannot reliably be parsed, switch only the acquisition layer to Playwright while keeping the parser/aggregator/storage architecture unchanged.

## Important boundary
The software is a research/data-organization tool. It should not make buy/sell recommendations, price predictions, or automatically place trades.

## What to do first
1. Scaffold the repository.
2. Put filter configuration in one file.
3. Implement one screener first (Momentum).
4. Verify extraction and pagination.
5. Generalize to all complete URLs.
6. Implement aggregation.
7. Implement SQLite history.
8. Add basic tests and README instructions.
9. Stop before frontend and report what works, what failed, and any Finviz limitations encountered.

## Missing information
None for the initial backend milestone. All 7 Finviz screener URLs are now available.
