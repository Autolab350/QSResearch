"""Tests for portfolio strategies."""

from __future__ import annotations

import numpy as np

from portfolio.readers import covariance_matrix, log_returns
from portfolio.strategies import run_strategy


def _synthetic(n: int = 8, t: int = 200, seed: int = 7):
    rng = np.random.default_rng(seed)
    symbols = [f"S{i}" for i in range(n)]
    rets = rng.normal(0.0003, 0.015, size=(t, n))
    cov = covariance_matrix(rets)
    return symbols, rets, cov


def test_equal_weight_sums_to_one():
    symbols, rets, cov = _synthetic()
    weights, _ = run_strategy("equal_weight", symbols, rets, cov)
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert len(weights) == len(symbols)


def test_all_strategies_normalize():
    symbols, rets, cov = _synthetic()
    for name in ("inverse_vol", "min_var", "max_sharpe", "eigen"):
        weights, _ = run_strategy(name, symbols, rets, cov, long_only=True)
        assert abs(sum(weights.values()) - 1.0) < 1e-6


def test_min_var_lower_variance_than_equal_weight():
    symbols, rets, cov = _synthetic(n=8, t=250)
    ew, _ = run_strategy("equal_weight", symbols, rets, cov)
    mv, _ = run_strategy("min_var", symbols, rets, cov)
    w_ew = np.array([ew[s] for s in symbols])
    w_mv = np.array([mv[s] for s in symbols])
    var_ew = float(w_ew @ cov @ w_ew)
    var_mv = float(w_mv @ cov @ w_mv)
    assert var_mv <= var_ew + 1e-6


def test_long_only_projection():
    symbols, rets, cov = _synthetic()
    weights, meta = run_strategy("max_sharpe", symbols, rets, cov, long_only=True)
    assert all(w >= -1e-9 for w in weights.values())
    assert meta["long_only_projected"] in (True, False)
