"""Portfolio SQLite read/write."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from ..settings import get_settings

DEFAULT_UNIVERSE = "default"
DEFAULT_TICKERS = [
    "AAPL",
    "META",
    "NFLX",
    "SQQQ",
    "TSLA",
    "MSFT",
    "AMZN",
    "AMD",
    "NVDA",
]

_RUNS_MIGRATION_COLUMNS = (
    ("as_of", "TEXT"),
    ("lookback_days", "INTEGER"),
    ("n_symbols", "INTEGER"),
    ("source", "TEXT"),
    ("status", "TEXT"),
)


class PortfolioStore:
    def __init__(self, db_path: Path | None = None):
        settings = get_settings()
        self.db_path = Path(db_path) if db_path else settings.db_path
        self.schema_path = settings.schema_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()
        self._ensure_default_universe()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_schema(self) -> None:
        schema = self.schema_path.read_text(encoding="utf-8")
        with self._connect() as conn:
            conn.executescript(schema)
            self._migrate_runs_columns(conn)

    def _migrate_runs_columns(self, conn: sqlite3.Connection) -> None:
        existing = {
            row[1]
            for row in conn.execute("PRAGMA table_info(runs)").fetchall()
        }
        for name, col_type in _RUNS_MIGRATION_COLUMNS:
            if name not in existing:
                conn.execute(f"ALTER TABLE runs ADD COLUMN {name} {col_type}")

    def _ensure_default_universe(self) -> None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM universes WHERE name = ?",
                (DEFAULT_UNIVERSE,),
            ).fetchone()
            if row:
                return
            self.upsert_universe(
                DEFAULT_UNIVERSE,
                DEFAULT_TICKERS,
                description="Seeded from classic Eiten stocks list",
                conn=conn,
            )

    def upsert_universe(
        self,
        name: str,
        tickers: Iterable[str],
        description: str = "",
        sector: str = "",
        tags: str = "",
        conn: sqlite3.Connection | None = None,
    ) -> int:
        own = conn is None
        conn = conn or self._connect()
        try:
            conn.execute(
                "INSERT INTO universes (name, description) VALUES (?, ?) "
                "ON CONFLICT(name) DO UPDATE SET description = excluded.description",
                (name, description),
            )
            universe_id = conn.execute(
                "SELECT id FROM universes WHERE name = ?", (name,)
            ).fetchone()["id"]

            clean = sorted({t.strip().upper() for t in tickers if t and t.strip()})
            for ticker in clean:
                conn.execute(
                    "INSERT INTO instruments (ticker, sector, tags, active) VALUES (?, ?, ?, 1) "
                    "ON CONFLICT(ticker) DO UPDATE SET "
                    "sector = COALESCE(NULLIF(excluded.sector, ''), instruments.sector), "
                    "tags = CASE WHEN excluded.tags != '' THEN excluded.tags ELSE instruments.tags END, "
                    "active = 1",
                    (ticker, sector, tags),
                )
                conn.execute(
                    "INSERT OR IGNORE INTO universe_members (universe_id, ticker) VALUES (?, ?)",
                    (universe_id, ticker),
                )
            if own:
                conn.commit()
            return len(clean)
        finally:
            if own:
                conn.close()

    def list_universes(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT name FROM universes ORDER BY name").fetchall()
        return [r["name"] for r in rows]

    def load_universe(self, name: str = DEFAULT_UNIVERSE) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT m.ticker
                FROM universe_members m
                JOIN universes u ON u.id = m.universe_id
                JOIN instruments i ON i.ticker = m.ticker
                WHERE u.name = ? AND i.active = 1
                ORDER BY m.ticker
                """,
                (name,),
            ).fetchall()
        tickers = [r["ticker"] for r in rows]
        if not tickers:
            raise ValueError(f"Universe '{name}' is empty or missing in {self.db_path}")
        return tickers

    def start_run(
        self,
        universe: str,
        strategy: str,
        params: dict[str, Any],
        *,
        as_of: str,
        lookback_days: int,
        n_symbols: int,
        source: str,
        status: str = "ok",
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO runs (
                    universe, strategy, params_json, as_of, lookback_days,
                    n_symbols, source, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    universe,
                    strategy,
                    json.dumps(params, default=str),
                    as_of,
                    lookback_days,
                    n_symbols,
                    source,
                    status,
                ),
            )
            return int(cur.lastrowid)

    def save_allocation(
        self,
        run_id: int,
        strategy: str,
        weights: dict[str, float],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE runs SET strategy = COALESCE(strategy, ?) WHERE id = ?",
                (strategy, run_id),
            )
            for ticker, weight in weights.items():
                ticker = str(ticker).upper()
                conn.execute(
                    "INSERT INTO instruments (ticker, active) VALUES (?, 1) "
                    "ON CONFLICT(ticker) DO NOTHING",
                    (ticker,),
                )
                conn.execute(
                    """
                    INSERT INTO allocations (run_id, strategy, ticker, weight)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(run_id, strategy, ticker)
                    DO UPDATE SET weight = excluded.weight, created_at = datetime('now')
                    """,
                    (run_id, strategy, ticker, float(weight)),
                )

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if not row:
                return None
            allocations = conn.execute(
                """
                SELECT ticker, weight, strategy
                FROM allocations
                WHERE run_id = ?
                ORDER BY weight DESC, ticker
                """,
                (run_id,),
            ).fetchall()
        run = dict(row)
        run["params"] = json.loads(run["params_json"]) if run.get("params_json") else {}
        run["allocations"] = [
            {"ticker": a["ticker"], "weight": float(a["weight"])} for a in allocations
        ]
        if allocations:
            run["strategy"] = allocations[0]["strategy"]
        return run

    def list_runs(self, universe: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if universe:
                rows = conn.execute(
                    """
                    SELECT id, universe, strategy, as_of, lookback_days, n_symbols,
                           source, status, created_at
                    FROM runs
                    WHERE universe = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (universe, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, universe, strategy, as_of, lookback_days, n_symbols,
                           source, status, created_at
                    FROM runs
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]
