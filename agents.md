TITLE: 04.10.2026-agents
SUMMARY: Folder App/QSResearch — desk name Portfolio. Package portfolio. Proposes weights only. MAP.md first.
CATEGORY: agents

**Folder:** `App/QSResearch/`. **Say to owner:** **Portfolio** (not “QSResearch” in chat unless discussing folder map). **Code:** `portfolio` CLI / package. Map: [`../../MAP.md`](../../MAP.md). Default notes: `data/notes/day/`.

Stack: **QSConnect** facts (`App/QSConnect`, `marketdata`) · **Autodesk** place (`App/Omega`) only when owner sends.

Chat with the owner is ordinary sentences. Proposes weights — never sends orders.

SETUP

{
  "commands": [
    "python3.12 -m venv .venv && source .venv/bin/activate",
    "pip install -e \".[dev]\"",
    "portfolio init-db",
    "portfolio universes",
    "pytest"
  ]
}

RULES

{
  "items": [
    "Never commit .env, .venv/, or data/*.db.",
    "Read closes read-only from QSConnect DuckDB (`App/QSConnect/data/marketdata.duckdb`) — do not import marketdata package.",
    "Do not import autodesk. Seam is allocation JSON, not a live order.",
    "Fail closed on missing bars: name missing/short symbols; never invent closes.",
    "Warm bars via `cd App/QSConnect && python -m marketdata update-prices` before blaming Portfolio coverage.",
    "Stock/ETF weights only — no 0DTE options ladder math in this app.",
    "Desk notes: default data/notes/day/; see root MAP.md. Folder QSResearch; say Portfolio to owner."
  ]
}

{
  "commands": [
    "portfolio run --universe default --strategy equal_weight --json",
    "portfolio compare --universe default --strategies equal_weight min_var",
    "portfolio backtest --universe default --strategy min_var",
    "portfolio show-run 1"
  ]
}
