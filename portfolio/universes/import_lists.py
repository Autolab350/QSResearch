"""Load ticker list JSON/txt into portfolio.db."""

from __future__ import annotations

import json
import re
import sqlite3
import zipfile
from pathlib import Path

from ..settings import get_settings
from ..store.db import PortfolioStore

TICKER_LINE = re.compile(r"^([A-Z][A-Z0-9.\-]{0,6})\b")
PAREN_TICKER = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,6})\)\s*$")


def parse_tickers_from_text(text: str) -> list[str]:
    tickers: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("---"):
            continue
        m = PAREN_TICKER.search(line)
        if m:
            tickers.append(m.group(1))
            continue
        m = TICKER_LINE.match(line)
        if m:
            tickers.append(m.group(1))
    return tickers


def import_txt_universe(store: PortfolioStore, path: Path, name: str) -> int:
    tickers = parse_tickers_from_text(path.read_text(encoding="utf-8"))
    return store.upsert_universe(name, tickers, description=f"Imported from {path.name}")


def import_bucket_watchlist(
    store: PortfolioStore,
    path: Path,
    *,
    prefix: str,
    default_tags: str,
) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    total = 0
    for key, block in data.get("watchlist", {}).items():
        tickers = block.get("stocks", [])
        desc = block.get("description", "")
        strategy = block.get("strategy", "")
        as_of = block.get("as_of", "")
        source = block.get("source", "")
        meta = " | ".join(p for p in (desc, strategy) if p)
        if as_of or source:
            meta = f"{meta} | as_of={as_of} source={source}".strip(" |")
        tags = block.get("tags", default_tags)
        tag_str = ",".join(tags) if isinstance(tags, list) else str(tags)
        n = store.upsert_universe(
            f"{prefix}_{key}",
            tickers,
            description=meta,
            sector=key.replace("_", " "),
            tags=tag_str,
        )
        total += n
    return total


def import_sectors_json(store: PortfolioStore, path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    total = 0

    for key, block in data.get("universes", {}).items():
        tickers = block.get("tickers", [])
        sector = block.get("sector", key.replace("_", " "))
        etf = block.get("etf", "")
        desc = block.get("description", "")
        if not desc and etf:
            desc = f"{sector} ({etf})"
        tags = block.get("tags", ["sector"])
        tag_str = ",".join(tags) if isinstance(tags, list) else str(tags)
        name = f"sector_{key}"
        total += store.upsert_universe(
            name, tickers, description=desc, sector=sector, tags=tag_str
        )

    for key, tickers in data.get("macro_indicators", {}).items():
        if tickers:
            total += store.upsert_universe(
                f"macro_{key}",
                tickers,
                description=f"Macro indicators: {key.replace('_', ' ')}",
                tags="macro",
            )

    for key, tickers in data.get("commodities_futures", {}).items():
        if tickers:
            total += store.upsert_universe(
                f"commodity_{key}",
                tickers,
                description=f"Commodity futures: {key.replace('_', ' ')}",
                tags="commodity,futures",
            )

    return total


def import_eiten_json(store: PortfolioStore, path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    total = 0

    def walk(obj, prefix: str = "catalog") -> None:
        nonlocal total
        if isinstance(obj, dict):
            for key, val in obj.items():
                walk(val, f"{prefix}_{key}" if prefix else key)
        elif isinstance(obj, list):
            tickers = [str(x).upper() for x in obj if isinstance(x, str)]
            if tickers:
                uni = prefix.replace("/", "_").lower()[:120]
                total += store.upsert_universe(
                    uni,
                    tickers,
                    description=f"From {path.name}",
                    tags="catalog",
                )

    walk(data)
    return total


def extract_zip_json(lists_dir: Path) -> Path | None:
    for zpath in sorted(lists_dir.glob("Eiten_Ticker_Universe*.zip")):
        with zipfile.ZipFile(zpath) as zf:
            for name in zf.namelist():
                if name.endswith(".json"):
                    out = lists_dir / Path(name).name
                    out.write_bytes(zf.read(name))
                    return out
    return None


def import_all_lists(
    store: PortfolioStore | None = None,
    lists_dir: Path | None = None,
) -> dict[str, int]:
    settings = get_settings()
    store = store or PortfolioStore()
    lists_dir = lists_dir or settings.lists_dir
    counts: dict[str, int] = {}

    income = lists_dir / "income_watchlist.json"
    if income.exists():
        counts["income_watchlist"] = import_bucket_watchlist(
            store, income, prefix="income", default_tags="income,options"
        )

    research = lists_dir / "research_watchlist.json"
    if research.exists():
        counts["research_watchlist"] = import_bucket_watchlist(
            store, research, prefix="research", default_tags="research,watchlist"
        )

    sectors_json = lists_dir / "sectors.json"
    if sectors_json.exists():
        counts["sectors"] = import_sectors_json(store, sectors_json)

    scans_dir = lists_dir / "scans"
    if scans_dir.is_dir():
        for txt in sorted(scans_dir.glob("*.txt")):
            name = txt.stem.replace("-", "_")
            counts[name] = import_txt_universe(store, txt, name)

    json_path = lists_dir / "Eiten_Ticker_Universe_2026-07-26.json"
    if not json_path.exists():
        json_path = extract_zip_json(lists_dir) or json_path
    if json_path.exists():
        counts["eiten_catalog"] = import_eiten_json(store, json_path)

    for txt in sorted(lists_dir.glob("*.txt")):
        if txt.name in ("stocks.txt", "all_stocks.txt"):
            counts[txt.stem] = import_txt_universe(store, txt, txt.stem)

    return counts


def list_tickers(universe: str, db_path: Path | None = None) -> list[str]:
    store = PortfolioStore(db_path=db_path)
    return store.load_universe(universe)


def list_universes(db_path: Path | None = None) -> list[str]:
    store = PortfolioStore(db_path=db_path)
    return store.list_universes()
