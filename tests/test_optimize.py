"""Tests for optimize.run and compare."""

from __future__ import annotations

from pathlib import Path

from portfolio.optimize import compare, run
from portfolio.store.db import PortfolioStore


def test_run_persists(tmp_portfolio_db: Path, fixture_marketdata_db: Path):
    store = PortfolioStore(db_path=tmp_portfolio_db)
    payload = run(
        "test_small",
        "equal_weight",
        lookback_days=200,
        min_bars=120,
        min_symbols=5,
        store=store,
        marketdata_db=str(fixture_marketdata_db),
    )
    assert payload["run_id"] >= 1
    assert payload["strategy"] == "equal_weight"
    assert len(payload["allocations"]) == 5
    row = store.get_run(payload["run_id"])
    assert row is not None
    assert len(row["allocations"]) == 5


def test_compare_multiple_strategies(tmp_portfolio_db: Path, fixture_marketdata_db: Path):
    store = PortfolioStore(db_path=tmp_portfolio_db)
    payload = compare(
        "test_small",
        ["equal_weight", "min_var"],
        lookback_days=200,
        store=store,
        marketdata_db=str(fixture_marketdata_db),
    )
    assert "equal_weight" in payload["strategies"]
    assert "min_var" in payload["strategies"]
