# Portfolio application

Universe → optimizer → target weights. Proposes allocations; never sends orders.

Prices are read read-only from the QSConnect DuckDB (`prices_daily`). See `BUILD.md` for the full build plan.

```bash
cd App/QSResearch
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
portfolio init-db
portfolio universes
portfolio run --universe default --strategy equal_weight --json
```
