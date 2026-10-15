"""Maximum Sharpe ratio portfolio (naive expected returns from lookback mean)."""

from __future__ import annotations

import numpy as np


def max_sharpe(
    symbols: list[str],
    cov: np.ndarray,
    returns: np.ndarray,
) -> dict[str, float]:
    expected = np.mean(returns, axis=0)
    inverse = np.linalg.pinv(cov)
    ones = np.ones(len(symbols))
    numerator = inverse @ expected
    denominator = float(ones @ inverse @ expected)
    if abs(denominator) < 1e-12:
        raise ValueError("Degenerate covariance for max_sharpe")
    weights = numerator / denominator
    return {symbols[i]: float(weights[i]) for i in range(len(symbols))}
