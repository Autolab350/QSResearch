"""Target weights. Small, stdlib, deterministic."""

from __future__ import annotations

import math
from statistics import pstdev

from .types import Allocation


def equal_weight(symbols: list[str]) -> dict[str, float]:
    syms = [s.upper() for s in dict.fromkeys(symbols) if s]
    if not syms:
        return {}
    w = 1.0 / len(syms)
    out = {s: round(w, 6) for s in syms}
    # push rounding dust onto the first name so weights sum to exactly 1
    out[syms[0]] = round(out[syms[0]] + (1.0 - sum(out.values())), 6)
    return out


def inverse_vol(closes: dict[str, list[float]], lookback: int = 20) -> dict[str, float]:
    """Weights proportional to 1 / realized vol. Names with too few closes are dropped."""
    inv: dict[str, float] = {}
    for sym, xs in closes.items():
        if len(xs) < lookback + 1:
            continue
        rets = [math.log(xs[i] / xs[i - 1]) for i in range(len(xs) - lookback, len(xs))]
        vol = pstdev(rets)
        if vol > 0:
            inv[sym.upper()] = 1.0 / vol
    if not inv:
        return {}
    tot = sum(inv.values())
    out = {s: round(v / tot, 6) for s, v in inv.items()}
    first = next(iter(out))
    out[first] = round(out[first] + (1.0 - sum(out.values())), 6)
    return out


def allocation(symbols: list[str], method: str = "equal_weight", closes: dict | None = None) -> Allocation:
    if method == "equal_weight":
        return Allocation(equal_weight(symbols), method)
    if method == "inverse_vol":
        return Allocation(inverse_vol(closes or {}), method)
    raise ValueError(f"unknown method {method!r}")


__all__ = ["equal_weight", "inverse_vol", "allocation"]
