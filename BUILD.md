# Portfolio application build plan

**Filed:** 23.08.2026  
**Parent:** MAT `App/`  
**Companion apps:** MarketData (bars) · Autodesk (orders only when you choose to act)

Portfolio proposes target weights from a universe and strategy. It never sends orders.

---

## 1. Roles

| Path | Job |
|------|-----|
| `App/QSConnect/` | Ingest bars and chain into DuckDB |
| `App/QSResearch/` | Universe → optimizer → target weights (+ optional rebalance diff) |
| `App/Omega/` | Order ticket JSON in → venue out |

Seam between propose and send: **allocation JSON** (weights), later optionally rebalance proposal JSON. Portfolio reads MarketData DuckDB read-only via `duckdb` — it does not import the `marketdata` package. Autodesk is not imported by Portfolio.

Upstream reference after land: `Holding/MAT-apps/QSResearch/database/portfolio/` (synced source; not a second runtime).

Strategy math is rewritten from published Eiten / PyPortfolioOpt ideas under MIT. No GPL tree is vendored.

---

## 2. Output shape

```json
{
  "run_id": 3,
  "universe": "research_growth",
  "strategy": "min_var",
  "as_of": "2026-08-22",
  "source": "marketdata.prices_daily",
  "lookback_days": 250,
  "long_only": true,
  "allocations": [{"ticker": "AAPL", "weight": 0.1842}],
  "coverage": {"requested": 24, "used": 21, "missing": ["XYZ"], "short": ["ABCD"]}
}
```

No `venue`, `qty`, `side`, or order fields in allocation output.

---

## 3. Phases (landed in v0.1.0)

### Phase 0 — Land package

**Done when**

```bash
cd App/QSResearch
/opt/homebrew/bin/python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
portfolio init-db
portfolio universes   # 54 universes from copied portfolio.db
pytest
rg -n "autodesk|import marketdata|from marketdata" App/QSResearch/portfolio/  # empty
```

### Phase 1 — Returns and coverage gate

- `read_close_matrix()` from `prices_daily` with date intersection
- Fail closed: missing/short symbols reported; run errors if `used < min_symbols` (default 5)
- `as_of` = last aligned bar date

### Phase 2 — Strategies (MIT rewrites)

| CLI name | Description |
|----------|-------------|
| `equal_weight` | Baseline |
| `inverse_vol` | Inverse-vol baseline |
| `min_var` | Minimum variance |
| `max_sharpe` | Max Sharpe (naive lookback mean returns) |
| `eigen` | Eigen portfolio (default index 2) |

Optional `--noise-filter` applies Marchenko-Pastur RMT on covariance. Long-only is default.

Genetic algo is **not** in v1.

### Phase 3 — Run, persist, emit

```bash
portfolio run --universe default --strategy equal_weight --json
portfolio show-run 3
portfolio export 3 --out out/allocation.json
```

Warm bars first when coverage fails:

```bash
cd App/QSConnect
python -m marketdata update-prices --provider alpaca --symbols AAPL MSFT ...
```

### Phase 4 — Compare and holdout backtest

```bash
portfolio compare --universe default --strategies equal_weight min_var max_sharpe
portfolio backtest --universe default --strategy min_var --holdout 30
```

Stats labelled in-sample vs holdout. No plots.

### Phase 5 — Rebalance proposal (optional)

```bash
portfolio rebalance --run-id 3 --holdings examples/holdings.json
```

Produces share deltas only. **Autodesk blocker:** `order_ticket.schema.json` requires `occ` for non-crypto READY tickets — equity share tickets need an Autodesk schema branch in a separate PR.

### Phase 6 — Later

HRP, CVaR, risk parity, sector caps, genetic algo — only if baselines + Eiten-class set are insufficient.

---

## 4. Technical gates

- Portfolio does not place orders.
- Portfolio does not import `marketdata` or `autodesk`.
- Closes from MarketData only — never invented.
- Stock/ETF weights only — no 0DTE options ladder math.
- `pytest` offline with fixture DuckDB.
- `App/QSResearch/data/*.db` gitignored; working copy seeded from MAT `portfolio.db`.

---

## 5. Target tree

```
App/QSResearch/
├── BUILD.md
├── pyproject.toml
├── readme.md
├── config/lists/          # optional ticker JSON/txt for import-lists
├── data/portfolio.db      # gitignored working state
├── examples/
│   └── allocation.json
├── portfolio/
│   ├── cli.py
│   ├── settings.py
│   ├── readers.py
│   ├── optimize.py
│   ├── backtest.py
│   ├── rebalance.py
│   ├── universes/import_lists.py
│   ├── strategies/        # equal_weight, inverse_vol, min_var, max_sharpe, eigen, cov
│   └── store/             # schema.sql, db.py
└── tests/
```

**Environment**

| Variable | Default |
|----------|---------|
| `PORTFOLIO_DB_PATH` | `data/portfolio.db` |
| `PORTFOLIO_MARKETDATA_DB` | `../QSConnect/data/marketdata.duckdb` |
| `PORTFOLIO_LISTS_DIR` | `config/lists/` |
| `PORTFOLIO_LOOKBACK_DAYS` | 250 |
| `PORTFOLIO_MIN_BARS` | 120 |
| `PORTFOLIO_MIN_SYMBOLS` | 5 |

---

## 6. Agent workflow

Signal IN: “build a defensive book from income_watchlist” → `portfolio run` → show weights + optional `portfolio backtest` → owner says go → (later) rebalance proposal → (later, separate) Autodesk equity tickets.

Brain outside, hands in Autodesk — same discipline as options.
