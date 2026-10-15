"""Inverse-volatility baseline."""

from __future__ import annotations

import numpy as np


def inverse_vol(symbols: list[str], returns: np.ndarray) -> dict[str, float]:
    if returns.shape[1] != len(symbols):
        raise ValueError("returns columns must match symbols")
    vols = np.std(returns, axis=0, ddof=1)
    vols = np.where(vols <= 1e-12, np.max(vols) if np.max(vols) > 0 else 1.0, vols)
    inv = 1.0 / vols
    inv_sum = float(np.sum(inv))
    weights = inv / inv_sum
    return {symbols[i]: float(weights[i]) for i in range(len(symbols))}
