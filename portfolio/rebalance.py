"""Rebalance proposal: target weights vs current holdings → share deltas.

Portfolio stops at the proposal JSON. Autodesk equity tickets require a
separate schema branch (order_ticket.schema.json currently requires ``occ``
for non-crypto venues).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .readers import get_marketdata_db_path, read_close_matrix
from .settings import get_settings


def _load_holdings(path: Path) -> tuple[float, dict[str, float]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cash = float(data.get("cash", 0.0))
    positions: dict[str, float] = {}
    for row in data.get("positions", []):
        ticker = str(row["ticker"]).upper()
        positions[ticker] = float(row.get("shares", 0))
    return cash, positions


def _largest_remainder(shares_float: dict[str, float], total_shares: int) -> dict[str, int]:
    floors = {k: int(v) for k, v in shares_float.items()}
    remainder = total_shares - sum(floors.values())
    if remainder <= 0:
        return floors
    frac = sorted(
        ((k, shares_float[k] - floors[k]) for k in shares_float),
        key=lambda x: (-x[1], x[0]),
    )
    out = floors.copy()
    for i in range(remainder):
        out[frac[i % len(frac)][0]] += 1
    return out


def propose_rebalance(
    target_weights: dict[str, float],
    holdings_path: Path,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Compute buy/sell share deltas to move toward target weights."""
    cash, positions = _load_holdings(holdings_path)
    tickers = sorted(set(target_weights) | set(positions))
    settings = get_settings()
    path = get_marketdata_db_path(db_path)

    prices: dict[str, float] = {}
    if path.exists():
        matrix = read_close_matrix(
            tickers,
            lookback_days=5,
            min_bars=1,
            min_symbols=1,
            db_path=path,
        )
        for i, sym in enumerate(matrix.symbols):
            prices[sym] = float(matrix.closes[-1, i])

    missing_prices = [t for t in tickers if t not in prices]
    if missing_prices:
        raise ValueError(
            f"No closes for: {missing_prices[:10]}. "
            "Warm bars in QSConnect (App/QSConnect, marketdata update-prices) before rebalancing."
        )

    position_value = sum(positions.get(t, 0) * prices[t] for t in tickers)
    total_value = cash + position_value
    if total_value <= 0:
        raise ValueError("Portfolio value must be positive")

    target_shares_float = {
        t: (target_weights.get(t, 0.0) * total_value) / prices[t] for t in tickers
    }
    total_target_shares = int(round(sum(target_shares_float.values())))
    target_shares = _largest_remainder(target_shares_float, total_target_shares)

    deltas: list[dict[str, Any]] = []
    for t in tickers:
        current = int(positions.get(t, 0))
        target = target_shares.get(t, 0)
        delta = target - current
        if delta == 0:
            continue
        side = "buy" if delta > 0 else "sell"
        deltas.append(
            {
                "ticker": t,
                "side": side,
                "shares": abs(delta),
                "price": round(prices[t], 4),
                "notional": round(abs(delta) * prices[t], 2),
                "current_shares": current,
                "target_shares": target,
            }
        )

    residual_cash = cash - sum(
        d["notional"] if d["side"] == "buy" else -d["notional"] for d in deltas
    )

    return {
        "total_value": round(total_value, 2),
        "cash_start": round(cash, 2),
        "cash_residual_est": round(residual_cash, 2),
        "holdings_source": str(holdings_path),
        "deltas": deltas,
        "note": (
            "Proposal only — not an order. Autodesk equity tickets need an equity "
            "branch on order_ticket.schema.json (occ is required today)."
        ),
    }
