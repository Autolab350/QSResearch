"""Read-only price helpers from QSConnect DuckDB (marketdata)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import numpy as np

from .settings import get_settings


@dataclass
class CoverageReport:
    requested: int
    used: int
    missing: list[str] = field(default_factory=list)
    short: list[str] = field(default_factory=list)


@dataclass
class CloseMatrix:
    dates: list[str]
    symbols: list[str]
    closes: np.ndarray
    as_of: str
    coverage: CoverageReport


class CoverageError(Exception):
    """Raised when too few symbols pass the coverage gate."""

    def __init__(self, message: str, coverage: CoverageReport):
        super().__init__(message)
        self.coverage = coverage


def get_marketdata_db_path(db_path: Path | None = None) -> Path:
    return db_path or get_settings().marketdata_db_path


def read_close_matrix(
    tickers: list[str],
    *,
    lookback_days: int | None = None,
    min_bars: int | None = None,
    min_symbols: int | None = None,
    db_path: Path | None = None,
) -> CloseMatrix:
    """Build an aligned close matrix from QSConnect ``prices_daily``.

    Returns dates (oldest-first), symbols kept, and a T x N close array.
    Symbols with no rows land in ``coverage.missing``; symbols with fewer than
    ``min_bars`` rows land in ``coverage.short``. Optimization uses the
    intersection of trading dates across kept symbols.
    """
    settings = get_settings()
    lookback_days = lookback_days or settings.default_lookback_days
    min_bars = min_bars or settings.min_bars
    min_symbols = min_symbols or settings.min_symbols
    path = get_marketdata_db_path(db_path)

    if not path.exists():
        raise FileNotFoundError(
            f"QSConnect DuckDB not found at {path}. "
            "Warm bars with: cd App/QSConnect && python -m marketdata update-prices ..."
        )

    requested = sorted({t.strip().upper() for t in tickers if t and t.strip()})
    if not requested:
        raise ValueError("No tickers requested")

    con = duckdb.connect(str(path), read_only=True)
    try:
        per_symbol: dict[str, list[tuple[str, float]]] = {}
        missing: list[str] = []
        short: list[str] = []

        for symbol in requested:
            rows = con.execute(
                """
                SELECT date::VARCHAR AS d, close
                FROM prices_daily
                WHERE symbol = ? AND close IS NOT NULL
                ORDER BY date DESC
                LIMIT ?
                """,
                [symbol, lookback_days],
            ).fetchall()
            if not rows:
                missing.append(symbol)
                continue
            series = [(str(d), float(c)) for d, c in reversed(rows)]
            if len(series) < min_bars:
                short.append(symbol)
                continue
            per_symbol[symbol] = series

        used = sorted(per_symbol.keys())
        coverage = CoverageReport(
            requested=len(requested),
            used=len(used),
            missing=missing,
            short=short,
        )
        if len(used) < min_symbols:
            raise CoverageError(
                f"Only {len(used)} symbols pass coverage (need {min_symbols}). "
                f"Missing: {missing[:10]}{'...' if len(missing) > 10 else ''}. "
                f"Short: {short[:10]}{'...' if len(short) > 10 else ''}.",
                coverage,
            )

        date_sets = [set(d for d, _ in per_symbol[s]) for s in used]
        common_dates = sorted(set.intersection(*date_sets))
        if len(common_dates) < min_bars:
            raise CoverageError(
                f"Aligned history has {len(common_dates)} bars (need {min_bars}).",
                coverage,
            )

        closes = np.array(
            [
                [dict(per_symbol[s])[d] for s in used]
                for d in common_dates
            ],
            dtype=float,
        )
        return CloseMatrix(
            dates=common_dates,
            symbols=used,
            closes=closes,
            as_of=common_dates[-1],
            coverage=coverage,
        )
    finally:
        con.close()


def log_returns(closes: np.ndarray) -> np.ndarray:
    """Log returns from a T x N close matrix (returns T-1 x N)."""
    if closes.shape[0] < 2:
        raise ValueError("Need at least 2 closes for returns")
    with np.errstate(divide="ignore", invalid="ignore"):
        rets = np.diff(np.log(closes), axis=0)
    rets = np.nan_to_num(rets, nan=0.0, posinf=0.0, neginf=0.0)
    return rets


def covariance_matrix(returns: np.ndarray) -> np.ndarray:
    """Sample covariance with pseudo-inverse fallback."""
    if returns.shape[0] < 2:
        raise ValueError("Need at least 2 return rows for covariance")
    cov = np.cov(returns, rowvar=False)
    if cov.ndim == 0:
        cov = np.array([[float(cov)]])
    return cov
