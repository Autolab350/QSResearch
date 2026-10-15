"""Central configuration for the Portfolio application."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parent

load_dotenv(REPO_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    db_path: Path
    marketdata_db_path: Path
    lists_dir: Path
    default_lookback_days: int
    min_bars: int
    min_symbols: int

    @property
    def schema_path(self) -> Path:
        return PACKAGE_DIR / "store" / "schema.sql"


def _resolve_path(raw: str | None, default: Path) -> Path:
    if raw:
        p = Path(raw)
    else:
        p = default
    if not p.is_absolute():
        p = REPO_ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def get_settings() -> Settings:
    default_md = REPO_ROOT.parent / "QSConnect" / "data" / "marketdata.duckdb"
    md_raw = os.getenv("PORTFOLIO_MARKETDATA_DB") or os.getenv("MARKETDATA_DB_PATH")
    lists_raw = os.getenv("PORTFOLIO_LISTS_DIR")
    return Settings(
        db_path=_resolve_path(os.getenv("PORTFOLIO_DB_PATH"), REPO_ROOT / "data" / "portfolio.db"),
        marketdata_db_path=_resolve_path(md_raw, default_md),
        lists_dir=_resolve_path(lists_raw, REPO_ROOT / "config" / "lists"),
        default_lookback_days=int(os.getenv("PORTFOLIO_LOOKBACK_DAYS", "250")),
        min_bars=int(os.getenv("PORTFOLIO_MIN_BARS", "120")),
        min_symbols=int(os.getenv("PORTFOLIO_MIN_SYMBOLS", "5")),
    )
