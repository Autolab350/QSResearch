"""Portfolio CLI — proposes target weights, never sends orders."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .backtest import backtest_holdout
from .optimize import compare, run
from .readers import CoverageError
from .rebalance import propose_rebalance
from .settings import get_settings
from .store.db import PortfolioStore
from .strategies import list_strategies
from .universes.import_lists import import_all_lists


def _print_json(data: object) -> None:
    print(json.dumps(data, indent=2, default=str))


def cmd_init_db(_args: argparse.Namespace) -> int:
    store = PortfolioStore()
    print(f"Portfolio DB ready at {store.db_path}")
    print(f"Universes: {len(store.list_universes())}")
    return 0


def cmd_import_lists(_args: argparse.Namespace) -> int:
    counts = import_all_lists()
    if not counts:
        settings = get_settings()
        print(f"No list files found under {settings.lists_dir}")
        return 1
    for name, n in sorted(counts.items()):
        print(f"  {name}: {n} tickers")
    store = PortfolioStore()
    print(f"Done. universes={len(store.list_universes())}")
    return 0


def cmd_universes(_args: argparse.Namespace) -> int:
    for name in PortfolioStore().list_universes():
        print(name)
    return 0


def cmd_tickers(args: argparse.Namespace) -> int:
    tickers = PortfolioStore().load_universe(args.universe)
    for t in tickers:
        print(t)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    try:
        payload = run(
            args.universe,
            args.strategy,
            lookback_days=args.lookback,
            long_only=not args.long_short,
            noise_filter=args.noise_filter,
            eigen_index=args.eigen_index,
            marketdata_db=args.marketdata_db,
        )
    except CoverageError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        _print_json(payload)
    else:
        print(f"run_id={payload.get('run_id')} universe={payload['universe']} "
              f"strategy={payload['strategy']} as_of={payload['as_of']}")
        for row in payload["allocations"][:20]:
            print(f"  {row['ticker']:8s} {row['weight']:.4f}")
        if len(payload["allocations"]) > 20:
            print(f"  ... +{len(payload['allocations']) - 20} more")
        cov = payload["coverage"]
        if cov["missing"] or cov["short"]:
            print(f"coverage: used {cov['used']}/{cov['requested']}")
    if args.out:
        Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0


def cmd_show_run(args: argparse.Namespace) -> int:
    store = PortfolioStore()
    row = store.get_run(args.run_id)
    if not row:
        print(f"No run {args.run_id}", file=sys.stderr)
        return 1
    payload = {
        "run_id": row["id"],
        "universe": row["universe"],
        "strategy": row.get("strategy"),
        "as_of": row.get("as_of"),
        "source": row.get("source"),
        "lookback_days": row.get("lookback_days"),
        "allocations": row["allocations"],
        "params": row.get("params", {}),
    }
    if args.json:
        _print_json(payload)
    else:
        print(json.dumps(payload, indent=2))
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    strategies = args.strategies or list_strategies()
    try:
        payload = compare(
            args.universe,
            strategies,
            lookback_days=args.lookback,
            long_only=not args.long_short,
            noise_filter=args.noise_filter,
            eigen_index=args.eigen_index,
            marketdata_db=args.marketdata_db,
        )
    except CoverageError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    _print_json(payload)
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    store = PortfolioStore()
    tickers = store.load_universe(args.universe)
    try:
        stats = backtest_holdout(
            tickers,
            args.strategy,
            lookback_days=args.lookback,
            holdout_bars=args.holdout,
            long_only=not args.long_short,
            noise_filter=args.noise_filter,
            marketdata_db=args.marketdata_db,
        )
    except CoverageError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    _print_json(stats)
    return 0


def cmd_rebalance(args: argparse.Namespace) -> int:
    store = PortfolioStore()
    row = store.get_run(args.run_id)
    if not row:
        print(f"No run {args.run_id}", file=sys.stderr)
        return 1
    weights = {a["ticker"]: a["weight"] for a in row["allocations"]}
    try:
        proposal = propose_rebalance(
            weights,
            Path(args.holdings),
            db_path=Path(args.marketdata_db) if args.marketdata_db else None,
        )
    except (ValueError, CoverageError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    _print_json(proposal)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    row = PortfolioStore().get_run(args.run_id)
    if not row:
        print(f"No run {args.run_id}", file=sys.stderr)
        return 1
    payload = {
        "run_id": row["id"],
        "universe": row["universe"],
        "strategy": row.get("strategy"),
        "as_of": row.get("as_of"),
        "source": row.get("source"),
        "lookback_days": row.get("lookback_days"),
        "allocations": row["allocations"],
    }
    out = Path(args.out)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


def cmd_info(_args: argparse.Namespace) -> int:
    settings = get_settings()
    store = PortfolioStore()
    print(f"portfolio {__version__}")
    print(f"db: {store.db_path}")
    print(f"marketdata: {settings.marketdata_db_path}")
    print(f"lists: {settings.lists_dir}")
    print(f"strategies: {', '.join(list_strategies())}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="portfolio", description="Target weight proposals")
    p.add_argument("--version", action="version", version=f"portfolio {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Ensure portfolio.db schema exists")
    sub.add_parser("import-lists", help="Import ticker lists from config/lists/")
    sub.add_parser("universes", help="List universe names")
    sub.add_parser("info", help="Show paths and strategies")

    pt = sub.add_parser("tickers", help="List tickers in a universe")
    pt.add_argument("--universe", required=True)

    pr = sub.add_parser("run", help="Run one strategy")
    pr.add_argument("--universe", required=True)
    pr.add_argument("--strategy", required=True)
    pr.add_argument("--lookback", type=int, default=None)
    pr.add_argument("--long-short", action="store_true")
    pr.add_argument("--noise-filter", action="store_true")
    pr.add_argument("--eigen-index", type=int, default=2)
    pr.add_argument("--json", action="store_true")
    pr.add_argument("--out", help="Write allocation JSON to path")
    pr.add_argument("--marketdata-db")

    ps = sub.add_parser("show-run", help="Show a persisted run")
    ps.add_argument("run_id", type=int)
    ps.add_argument("--json", action="store_true")

    pc = sub.add_parser("compare", help="Run multiple strategies on one universe")
    pc.add_argument("--universe", required=True)
    pc.add_argument("--strategies", nargs="+")
    pc.add_argument("--lookback", type=int, default=None)
    pc.add_argument("--long-short", action="store_true")
    pc.add_argument("--noise-filter", action="store_true")
    pc.add_argument("--eigen-index", type=int, default=2)
    pc.add_argument("--marketdata-db")

    pb = sub.add_parser("backtest", help="Offline holdout stats")
    pb.add_argument("--universe", required=True)
    pb.add_argument("--strategy", required=True)
    pb.add_argument("--lookback", type=int, default=250)
    pb.add_argument("--holdout", type=int, default=30)
    pb.add_argument("--long-short", action="store_true")
    pb.add_argument("--noise-filter", action="store_true")
    pb.add_argument("--marketdata-db")

    pre = sub.add_parser("rebalance", help="Propose share deltas vs holdings file")
    pre.add_argument("--run-id", type=int, required=True)
    pre.add_argument("--holdings", required=True, help="JSON holdings file")
    pre.add_argument("--marketdata-db")

    pe = sub.add_parser("export", help="Export run to allocation JSON")
    pe.add_argument("run_id", type=int)
    pe.add_argument("--out", required=True)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "init-db": cmd_init_db,
        "import-lists": cmd_import_lists,
        "universes": cmd_universes,
        "tickers": cmd_tickers,
        "run": cmd_run,
        "show-run": cmd_show_run,
        "compare": cmd_compare,
        "backtest": cmd_backtest,
        "rebalance": cmd_rebalance,
        "export": cmd_export,
        "info": cmd_info,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
