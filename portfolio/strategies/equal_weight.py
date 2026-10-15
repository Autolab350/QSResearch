"""Equal-weight baseline."""

from __future__ import annotations


def equal_weight(symbols: list[str]) -> dict[str, float]:
    n = len(symbols)
    if n == 0:
        raise ValueError("No symbols for equal_weight")
    w = 1.0 / n
    return {s: w for s in symbols}
