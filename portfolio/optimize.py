"""Run optimizer and persist allocation proposals."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .readers import CoverageError, covariance_matrix, log_returns, read_close_matrix
from .settings import get_settings
from .store.db import PortfolioStore
from .strategies import list_strategies, resolve_strategy, run_strategy

SOURCE = "marketdata.prices_daily"


def run(
    universe: str,
    strategy: str,
    *,
    lookback_days: int | None = None,
    long_only: bool = True,
    noise_filter: bool = False,
    eigen_index: int = 2,
    min_bars: int | None = None,
    min_symbols: int | None = None,
    store: PortfolioStore | None = None,
    marketdata_db: str | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    """Optimize a universe and return an allocation payload."""
    settings = get_settings()
    store = store or PortfolioStore()
    lookback_days = lookback_days or settings.default_lookback_days
    strategy_key = resolve_strategy(strategy)

    tickers = store.load_universe(universe)
    from pathlib import Path

    db_path = Path(marketdata_db) if marketdata_db else None
    matrix = read_close_matrix(
        tickers,
        lookback_days=lookback_days,
        min_bars=min_bars,
        min_symbols=min_symbols,
        db_path=db_path,
    )
    returns = log_returns(matrix.closes)
    cov = covariance_matrix(returns)
    if noise_filter:
        from .strategies.cov import apply_noise_filter

        cov = apply_noise_filter(returns)

    raw_weights, meta = run_strategy(
        strategy_key,
        matrix.symbols,
        returns,
        cov,
        long_only=long_only,
        noise_filter=False,
        eigen_index=eigen_index,
    )

    allocations = [
        {"ticker": t, "weight": round(w, 6)}
        for t, w in sorted(raw_weights.items(), key=lambda x: (-x[1], x[0]))
    ]

    payload: dict[str, Any] = {
        "universe": universe,
        "strategy": strategy_key,
        "as_of": matrix.as_of,
        "source": SOURCE,
        "lookback_days": lookback_days,
        "long_only": long_only,
        "noise_filter": noise_filter,
        "eigen_index": eigen_index if strategy_key == "eigen" else None,
        "long_only_projected": meta.get("long_only_projected", False),
        "allocations": allocations,
        "coverage": asdict(matrix.coverage),
    }

    if persist:
        params = {
            "long_only": long_only,
            "noise_filter": noise_filter,
            "eigen_index": eigen_index,
        }
        run_id = store.start_run(
            universe,
            strategy_key,
            params,
            as_of=matrix.as_of,
            lookback_days=lookback_days,
            n_symbols=len(matrix.symbols),
            source=SOURCE,
        )
        store.save_allocation(run_id, strategy_key, raw_weights)
        payload["run_id"] = run_id

    return payload


def compare(
    universe: str,
    strategies: list[str],
    *,
    lookback_days: int | None = None,
    long_only: bool = True,
    noise_filter: bool = False,
    eigen_index: int = 2,
    store: PortfolioStore | None = None,
    marketdata_db: str | None = None,
) -> dict[str, Any]:
    """Run multiple strategies on one universe under a single run id."""
    settings = get_settings()
    store = store or PortfolioStore()
    lookback_days = lookback_days or settings.default_lookback_days
    from pathlib import Path

    db_path = Path(marketdata_db) if marketdata_db else None
    tickers = store.load_universe(universe)
    matrix = read_close_matrix(tickers, lookback_days=lookback_days, db_path=db_path)
    returns = log_returns(matrix.closes)
    cov = covariance_matrix(returns)
    if noise_filter:
        from .strategies.cov import apply_noise_filter

        cov = apply_noise_filter(returns)

    resolved = [resolve_strategy(s) for s in strategies]
    params = {
        "strategies": resolved,
        "long_only": long_only,
        "noise_filter": noise_filter,
        "eigen_index": eigen_index,
    }
    run_id = store.start_run(
        universe,
        ",".join(resolved),
        params,
        as_of=matrix.as_of,
        lookback_days=lookback_days,
        n_symbols=len(matrix.symbols),
        source=SOURCE,
    )

    results: dict[str, list[dict[str, Any]]] = {}
    for name in resolved:
        weights, _meta = run_strategy(
            name,
            matrix.symbols,
            returns,
            cov,
            long_only=long_only,
            eigen_index=eigen_index,
        )
        store.save_allocation(run_id, name, weights)
        results[name] = [
            {"ticker": t, "weight": round(w, 6)}
            for t, w in sorted(weights.items(), key=lambda x: (-x[1], x[0]))
        ]

    return {
        "run_id": run_id,
        "universe": universe,
        "as_of": matrix.as_of,
        "source": SOURCE,
        "lookback_days": lookback_days,
        "strategies": results,
        "coverage": asdict(matrix.coverage),
    }
