"""Eigen portfolio from covariance eigendecomposition."""

from __future__ import annotations

import numpy as np


def eigen_weights(
    symbols: list[str],
    cov: np.ndarray,
    *,
    eigen_index: int = 2,
) -> dict[str, float]:
    if eigen_index < 1:
        raise ValueError("eigen_index must be >= 1")
    _, eig_vectors = np.linalg.eigh(cov)
    idx = -eigen_index
    vec = eig_vectors[:, idx]
    total = float(np.sum(vec))
    if abs(total) < 1e-12:
        raise ValueError("Eigen vector sums to zero")
    weights = vec / total
    return {symbols[i]: float(weights[i]) for i in range(len(symbols))}
