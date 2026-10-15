"""Weight projection helpers."""

from __future__ import annotations


def project_long_only(weights: dict[str, float]) -> dict[str, float]:
    clipped = {k: max(0.0, float(v)) for k, v in weights.items()}
    total = sum(clipped.values())
    if total <= 0:
        n = len(clipped)
        return {k: 1.0 / n for k in clipped}
    return {k: v / total for k, v in clipped.items()}
