"""Strategy registry and shared helpers."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

from .cov import apply_noise_filter
from .eigen import eigen_weights
from .equal_weight import equal_weight
from .inverse_vol import inverse_vol
from .max_sharpe import max_sharpe
from .min_variance import min_variance
from .project import project_long_only

StrategyFn = Callable[..., dict[str, float]]

STRATEGIES: dict[str, StrategyFn] = {
    "equal_weight": equal_weight,
    "inverse_vol": inverse_vol,
    "min_var": min_variance,
    "max_sharpe": max_sharpe,
    "eigen": eigen_weights,
}

STRATEGY_ALIASES = {
    "equal-weight": "equal_weight",
    "inv_vol": "inverse_vol",
    "minimum_variance": "min_var",
    "minimum_variance_portfolio": "min_var",
    "maximum_sharpe": "max_sharpe",
    "eigen_portfolio": "eigen",
}


def resolve_strategy(name: str) -> str:
    key = name.strip().lower()
    if key in STRATEGIES:
        return key
    if key in STRATEGY_ALIASES:
        return STRATEGY_ALIASES[key]
    known = ", ".join(sorted(STRATEGIES))
    raise ValueError(f"Unknown strategy '{name}'. Known: {known}")


def list_strategies() -> list[str]:
    return sorted(STRATEGIES)


def run_strategy(
    name: str,
    symbols: list[str],
    returns: np.ndarray,
    cov: np.ndarray,
    *,
    long_only: bool = True,
    noise_filter: bool = False,
    eigen_index: int = 2,
) -> tuple[dict[str, float], dict[str, Any]]:
    key = resolve_strategy(name)
    working_cov = apply_noise_filter(returns) if noise_filter else cov

    if key == "equal_weight":
        weights = equal_weight(symbols)
    elif key == "inverse_vol":
        weights = inverse_vol(symbols, returns)
    elif key == "min_var":
        weights = min_variance(symbols, working_cov)
    elif key == "max_sharpe":
        weights = max_sharpe(symbols, working_cov, returns)
    elif key == "eigen":
        weights = eigen_weights(symbols, working_cov, eigen_index=eigen_index)
    else:
        raise ValueError(f"Strategy not implemented: {key}")

    projected = False
    if long_only:
        before = weights.copy()
        weights = project_long_only(weights)
        projected = any(abs(weights[k] - before.get(k, 0)) > 1e-9 for k in weights)

    total = sum(weights.values())
    if total <= 0:
        raise ValueError(f"Strategy '{key}' produced non-positive total weight")
    weights = {k: v / total for k, v in weights.items()}
    meta = {"long_only_projected": projected}
    return weights, meta
