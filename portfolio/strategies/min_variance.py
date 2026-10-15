"""Minimum variance portfolio."""

from __future__ import annotations

import numpy as np


def min_variance(symbols: list[str], cov: np.ndarray) -> dict[str, float]:
    inverse = np.linalg.pinv(cov)
    ones = np.ones(len(symbols))
    raw = inverse @ ones
    denom = float(ones @ raw)
    if abs(denom) < 1e-12:
        raise ValueError("Degenerate covariance for min_variance")
    weights = raw / denom
    return {symbols[i]: float(weights[i]) for i in range(len(symbols))}
