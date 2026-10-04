"""Paste or levels -> Intent. Prose becomes fields here and nowhere else.

Phase A: contract skeleton (ticker, strike, right, expiry, entry) -> OCC + entry_ceiling,
plus cheap, explicit field maps for PT zones, ordered targets, size fraction, speculative,
round, and session window. Anything not recognised stays in ``raw_thesis``.
"""

from __future__ import annotations

import re
from datetime import date

from .types import Intent, Proposal

_TICKER = re.compile(r"\$([A-Z]{1,6})\b(?!\d)")
_STRIKE = re.compile(r"\$?(\d+(?:\.\d+)?)\s*(CALLS?|PUTS?)\b", re.I)
_EXPIRY = re.compile(r"EXP(?:IRATION|IRY)?\.?\s*:?\s*(\d{1,2})/(\d{1,2})/(\d{2,4})", re.I)
_ENTRY = re.compile(r"\$?\s*(\d*\.\d+|\d+(?:\.\d+)?)\s*(?:avg\s*)?entry", re.I)
_PT_ZONE = re.compile(r"\$?(\d+(?:\.\d+)?)\s*/\s*\$?(\d+(?:\.\d+)?)\s*(?:final\s+zone\s+)?pt", re.I)
_PT_ORDERED = re.compile(r"\$?(\d+(?:\.\d+)?)\s*pt\s*(\d)", re.I)
_TARGETS = re.compile(r"target\s+\$?(\d+(?:\.\d+)?)(?:\s*,\s*\$?(\d+(?:\.\d+)?))*(?:\s*(?:,|and)\s*(?:finally\s+)?\$?(\d+(?:\.\d+)?))?", re.I)
_HOLD = re.compile(r"hold\s+of\s+\$?(\d+(?:\.\d+)?)\s*/\s*\$?(\d+(?:\.\d+)?)", re.I)
_FRACTION = re.compile(r"size\s+(\d)\s*/\s*(\d)", re.I)
_ROUND = re.compile(r"round\s*(\d)", re.I)
_NUM = re.compile(r"\$?(\d+(?:\.\d+)?)")


def build_occ(underlying: str, expiry: str, right: str, strike: float) -> str:
    y, m, d = (int(x) for x in expiry.split("-"))
    return f"{underlying.upper()}{y % 100:02d}{m:02d}{d:02d}{right.upper()}{int(round(strike * 1000)):08d}"


def parse_occ(occ: str) -> dict:
    m = re.match(r"^([A-Z]{1,6})(\d{2})(\d{2})(\d{2})([CP])(\d{8})$", occ.upper())
    if not m:
        raise ValueError(f"not an OCC symbol: {occ}")
    u, yy, mm, dd, r, k = m.groups()
    return {"underlying": u, "expiry": f"20{yy}-{mm}-{dd}", "right": r, "strike": int(k) / 1000}


def _expiry(text: str) -> str | None:
    m = _EXPIRY.search(text)
    if not m:
        return None
    mo, dd, yy = (int(x) for x in m.groups())
    if yy < 100:
        yy += 2000
    return date(yy, mo, dd).isoformat()


def _levels(text: str) -> list[dict]:
    out: list[dict] = []
    m = _PT_ZONE.search(text)
    if m:
        a, b = sorted(float(x) for x in m.groups())
        out.append({"role": "band", "lo": a, "hi": b, "seq": 1})
    for seq_m in _PT_ORDERED.finditer(text):
        px, seq = float(seq_m.group(1)), int(seq_m.group(2))
        out.append({"role": "target", "lo": px, "hi": px, "seq": seq})
    m = _HOLD.search(text)
    if m:
        a, b = sorted(float(x) for x in m.groups())
        out.append({"role": "hold", "lo": a, "hi": b, "seq": 0})
    m = _TARGETS.search(text)
    if m:
        nums = [float(x) for x in _NUM.findall(m.group(0))]
        for i, px in enumerate(nums, start=1):
            out.append({"role": "target", "lo": px, "hi": px, "seq": i})
    return out


def normalize(text: str, *, regular_size: int = 4) -> Intent:
    """Signal paste -> Intent. Raises ValueError if no ticker is present."""
    t = text.strip()
    tick = _TICKER.search(t)
    if not tick:
        raise ValueError("no $TICKER in text")
    underlying = tick.group(1)

    right = strike = None
    m = _STRIKE.search(t)
    if m:
        strike = float(m.group(1))
        right = "C" if m.group(2).upper().startswith("CALL") else "P"
    expiry = _expiry(t)
    em = _ENTRY.search(t)
    entry = float(em.group(1)) if em else None
    occ = build_occ(underlying, expiry, right, strike) if (expiry and right and strike) else None

    low = t.lower()
    speculative = any(k in low for k in ("high risk", "lotto", "size for $0", "or skip"))
    rm = _ROUND.search(t)
    rnd = int(rm.group(1)) if rm else 1
    session = "midday" if "lunch" in low else None
    chase = not any(k in low for k in ("patient", "no fomo", "no chase", "wait for backtest"))

    fm = _FRACTION.search(t)
    planned = regular_size
    if fm:
        num, den = int(fm.group(1)), int(fm.group(2))
        base = max(1, round(regular_size * num / den))
    elif speculative:
        base, planned = 1, 1
    else:
        base = 1
    add_on = "none"
    if "backtest" in low or "dca" in low:
        add_on = "underlying_retest" if ("level" in low or "band" in low) else "premium_retrace"

    return Intent(
        underlying=underlying,
        right=right,
        strike=strike,
        expiry=expiry,
        occ=occ,
        entry_ceiling=entry,
        side="buy",
        open_or_close="open",
        asset_class="option" if occ else "equity",
        planned_total=planned,
        base_qty=base,
        add_qty_room=max(0, planned - base),
        levels=_levels(t),
        add_on=add_on,
        speculative=speculative,
        round=rnd,
        session_window=session,
        chase_allowed=chase,
        raw_thesis=t,
    )


def propose(text: str, **kw) -> Proposal:
    """Normalize and decide PROPOSE vs STAND_DOWN on structural grounds only."""
    try:
        it = normalize(text, **kw)
    except ValueError as e:
        return Proposal(Intent(underlying="?"), note=str(e), status="STAND_DOWN")
    if it.occ is None:
        return Proposal(it, note="incomplete contract: need strike, right, expiry", status="STAND_DOWN")
    if it.entry_ceiling is None:
        return Proposal(it, note="no entry premium on paste", status="STAND_DOWN")
    return Proposal(it, note="contract + ceiling present")


__all__ = ["normalize", "propose", "build_occ", "parse_occ"]
