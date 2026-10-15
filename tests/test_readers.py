"""Tests for readers and coverage gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from portfolio.readers import CoverageError, read_close_matrix


def test_close_matrix_deterministic(fixture_marketdata_db: Path):
    matrix = read_close_matrix(
        ["AAA", "BBB", "CCC", "DDD", "EEE"],
        lookback_days=250,
        min_bars=120,
        min_symbols=5,
        db_path=fixture_marketdata_db,
    )
    assert matrix.closes.shape[0] >= 120
    assert len(matrix.symbols) == 5
    assert matrix.as_of == matrix.dates[-1]
    assert matrix.coverage.used == 5


def test_missing_symbols_reported(fixture_marketdata_db: Path):
    matrix = read_close_matrix(
        ["AAA", "BBB", "CCC", "MISSING1", "MISSING2"],
        lookback_days=250,
        min_bars=120,
        min_symbols=3,
        db_path=fixture_marketdata_db,
    )
    assert "MISSING1" in matrix.coverage.missing
    assert matrix.coverage.used == 3


def test_too_few_symbols_errors(fixture_marketdata_db: Path):
    with pytest.raises(CoverageError) as exc:
        read_close_matrix(
            ["AAA", "BBB"],
            lookback_days=250,
            min_bars=120,
            min_symbols=5,
            db_path=fixture_marketdata_db,
        )
    assert exc.value.coverage.used == 2
