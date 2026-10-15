"""Tests for offline holdout backtest."""

from __future__ import annotations

from pathlib import Path

from portfolio.backtest import backtest_holdout
from portfolio.store.db import PortfolioStore


def test_backtest_holdout(tmp_portfolio_db: Path, fixture_marketdata_db: Path):
    store = PortfolioStore(db_path=tmp_portfolio_db)
    tickers = store.load_universe("test_small")
    stats = backtest_holdout(
        tickers,
        "equal_weight",
        lookback_days=200,
        holdout_bars=30,
        db_path=fixture_marketdata_db,
    )
    assert "in_sample" in stats
    assert "holdout" in stats
    assert stats["strategy"] == "equal_weight"
