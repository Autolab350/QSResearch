"""Shared pytest fixtures."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import duckdb
import numpy as np
import pytest

from portfolio.store.db import PortfolioStore


@pytest.fixture
def tmp_portfolio_db(tmp_path: Path) -> Path:
    db = tmp_path / "portfolio.db"
    store = PortfolioStore(db_path=db)
    store.upsert_universe("test_small", ["AAA", "BBB", "CCC", "DDD", "EEE"])
    store.upsert_universe("test_two", ["AAA", "BBB"])
    return db


@pytest.fixture
def fixture_marketdata_db(tmp_path: Path) -> Path:
    db = tmp_path / "marketdata.duckdb"
    con = duckdb.connect(str(db))
    con.execute(
        """
        CREATE TABLE prices_daily (
            symbol VARCHAR,
            date DATE,
            open DOUBLE,
            high DOUBLE,
            low DOUBLE,
            close DOUBLE,
            volume BIGINT,
            PRIMARY KEY (symbol, date)
        )
        """
    )
    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE", "SPY"]
    rng = np.random.default_rng(42)
    dates = [f"2024-{m:02d}-{d:02d}" for m in range(1, 13) for d in range(1, 29)]
    dates = dates[:250]
    for sym in symbols:
        price = 100.0 + rng.uniform(-10, 10)
        rows = []
        for d in dates:
            price *= 1.0 + rng.normal(0.0005, 0.01)
            rows.append((sym, d, price, price, price, price, 1_000_000))
        con.executemany(
            "INSERT INTO prices_daily VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    con.close()
    return db
