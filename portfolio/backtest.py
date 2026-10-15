"""Offline holdout backtest stats (no plots)."""

from __future__ import annotations

from typing import Any

import numpy as np

from .readers import CloseMatrix, covariance_matrix, log_returns, read_close_matrix
from .strategies import resolve_strategy, run_strategy


def _annualize_return(daily_returns: np.ndarray, periods: int = 252) -> float:
    if len(daily_returns) == 0:
        return 0.0
    total = float(np.prod(1.0 + daily_returns) - 1.0)
    years = len(daily_returns) / periods
    if years <= 0:
        return 0.0
    return float((1.0 + total) ** (1.0 / years) - 1.0)


def _annualize_vol(daily_returns: np.ndarray, periods: int = 252) -> float:
    if len(daily_returns) < 2:
        return 0.0
    return float(np.std(daily_returns, ddof=1) * np.sqrt(periods))


def _max_drawdown(cumulative: np.ndarray) -> float:
    if len(cumulative) == 0:
        return 0.0
    peak = np.maximum.accumulate(cumulative)
    dd = (cumulative - peak) / np.where(peak == 0, 1.0, peak)
    return float(np.min(dd))


def _effective_n(weights: dict[str, float]) -> float:
    w = np.array(list(weights.values()), dtype=float)
    w = w / w.sum()
    h = float(np.sum(w ** 2))
    return float(1.0 / h) if h > 0 else 0.0


def portfolio_daily_returns(
    closes: np.ndarray,
    symbols: list[str],
    weights: dict[str, float],
) -> np.ndarray:
    idx = {s: i for i, s in enumerate(symbols)}
    w = np.array([weights[s] for s in symbols], dtype=float)
    w = w / w.sum()
    simple = np.diff(closes, axis=0) / closes[:-1]
    return simple @ w


def backtest_holdout(
    universe_tickers: list[str],
    strategy: str,
    *,
    lookback_days: int = 250,
    holdout_bars: int = 30,
    long_only: bool = True,
    noise_filter: bool = False,
    eigen_index: int = 2,
    benchmark: str = "SPY",
    db_path=None,
) -> dict[str, Any]:
    """Fit on all but last ``holdout_bars``; report in-sample and holdout stats."""
    matrix = read_close_matrix(universe_tickers, lookback_days=lookback_days, db_path=db_path)
    if matrix.closes.shape[0] <= holdout_bars + 10:
        raise ValueError("Not enough aligned bars for holdout split")

    train_closes = matrix.closes[:-holdout_bars]
    test_closes = matrix.closes[-holdout_bars - 1 :]
    train_returns = log_returns(train_closes)
    cov = covariance_matrix(train_returns)
    if noise_filter:
        from .strategies.cov import apply_noise_filter

        cov = apply_noise_filter(train_returns)

    strategy_key = resolve_strategy(strategy)
    weights, _ = run_strategy(
        strategy_key,
        matrix.symbols,
        train_returns,
        cov,
        long_only=long_only,
        eigen_index=eigen_index,
    )

    insample_daily = portfolio_daily_returns(train_closes, matrix.symbols, weights)
    holdout_daily = portfolio_daily_returns(test_closes, matrix.symbols, weights)

    bench_stats: dict[str, Any] | None = None
    if benchmark.upper() in matrix.symbols:
        bidx = matrix.symbols.index(benchmark.upper())
        bench_holdout = np.diff(test_closes[:, bidx]) / test_closes[:-1, bidx]
        bench_stats = {
            "symbol": benchmark.upper(),
            "holdout_annual_return": round(_annualize_return(bench_holdout), 6),
            "holdout_annual_vol": round(_annualize_vol(bench_holdout), 6),
        }

    return {
        "strategy": strategy_key,
        "as_of": matrix.as_of,
        "holdout_bars": holdout_bars,
        "n_symbols": len(matrix.symbols),
        "concentration": {
            "max_weight": round(max(weights.values()), 6),
            "effective_n": round(_effective_n(weights), 4),
        },
        "in_sample": {
            "annual_return": round(_annualize_return(insample_daily), 6),
            "annual_vol": round(_annualize_vol(insample_daily), 6),
            "sharpe": round(
                _annualize_return(insample_daily) / _annualize_vol(insample_daily)
                if _annualize_vol(insample_daily) > 0
                else 0.0,
                4,
            ),
        },
        "holdout": {
            "annual_return": round(_annualize_return(holdout_daily), 6),
            "annual_vol": round(_annualize_vol(holdout_daily), 6),
            "sharpe": round(
                _annualize_return(holdout_daily) / _annualize_vol(holdout_daily)
                if _annualize_vol(holdout_daily) > 0
                else 0.0,
                4,
            ),
            "max_drawdown": round(
                _max_drawdown(np.cumprod(1.0 + holdout_daily)),
                6,
            ),
        },
        "benchmark": bench_stats,
        "weights": {k: round(v, 6) for k, v in weights.items()},
    }
