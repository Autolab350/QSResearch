"""Strategy outputs: Allocation, Intent, Proposal. Facts only, no prose semantics."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date


@dataclass(frozen=True)
class Allocation:
    weights: dict[str, float]
    method: str = "equal_weight"

    def __post_init__(self) -> None:
        total = round(sum(self.weights.values()), 6)
        if self.weights and abs(total - 1.0) > 1e-6:
            raise ValueError(f"weights must sum to 1, got {total}")


@dataclass
class Intent:
    """One normalized trade idea. Everything Omega gates can read is a field here."""

    underlying: str
    right: str | None = None  # "C" | "P" | None for shares
    strike: float | None = None
    expiry: str | None = None  # YYYY-MM-DD
    occ: str | None = None
    entry_ceiling: float | None = None  # max price to pay (debit) or min credit (credit)
    side: str = "buy"  # buy | sell
    open_or_close: str = "open"
    asset_class: str = "option"  # equity | option | crypto | future
    planned_total: int = 1
    base_qty: int = 1
    add_qty_room: int = 0
    levels: list[dict] = field(default_factory=list)  # {role, lo, hi, seq}
    add_on: str = "none"  # premium_retrace | underlying_retest | none
    speculative: bool = False
    round: int = 1
    session_window: str | None = None  # open | midday | close | None
    chase_allowed: bool = True
    raw_thesis: str = ""
    source: str = "paste"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Intent":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    @property
    def dte(self) -> int | None:
        if not self.expiry:
            return None
        y, m, d = (int(x) for x in self.expiry.split("-"))
        return (date(y, m, d) - date.today()).days


@dataclass(frozen=True)
class Proposal:
    intent: Intent
    note: str = ""
    status: str = "PROPOSE"  # PROPOSE | STAND_DOWN


__all__ = ["Allocation", "Intent", "Proposal"]
