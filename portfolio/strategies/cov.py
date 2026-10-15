"""Random matrix theory covariance filter (Marchenko-Pastur)."""

from __future__ import annotations

import numpy as np


def apply_noise_filter(returns: np.ndarray) -> np.ndarray:
    """Filter noise eigenvalues from the correlation matrix, then rebuild cov."""
    variances = np.diag(np.cov(returns, rowvar=False))
    std = np.sqrt(np.maximum(variances, 1e-12))
    corr = np.corrcoef(returns, rowvar=False)
    if corr.ndim == 0:
        return np.array([[float(variances)]])

    eig_values, eig_vectors = np.linalg.eigh(corr)
    q = returns.shape[1] / returns.shape[0]
    max_theoretical = (1.0 + np.sqrt(1.0 / q)) ** 2
    filtered = eig_values.copy()
    filtered[filtered <= max_theoretical] = 0.0

    rebuilt = eig_vectors @ np.diag(filtered) @ eig_vectors.T
    np.fill_diagonal(rebuilt, 1.0)
    cov = np.diag(std) @ rebuilt @ np.diag(std)
    return cov
