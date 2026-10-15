"""Tests for rebalance proposals."""

from __future__ import annotations

import json
from pathlib import Path

from portfolio.rebalance import propose_rebalance


def test_rebalance_proposal(fixture_marketdata_db: Path, tmp_path: Path):
    holdings = tmp_path / "holdings.json"
    holdings.write_text(
        json.dumps(
            {
                "cash": 1000.0,
                "positions": [
                    {"ticker": "AAA", "shares": 10},
                    {"ticker": "BBB", "shares": 5},
                ],
            }
        ),
        encoding="utf-8",
    )
    target = {"AAA": 0.5, "BBB": 0.5}
    proposal = propose_rebalance(
        target,
        holdings,
        db_path=fixture_marketdata_db,
    )
    assert proposal["total_value"] > 0
    assert "deltas" in proposal
    assert "venue" not in proposal
