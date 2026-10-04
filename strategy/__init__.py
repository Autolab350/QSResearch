"""strategy public surface: allocate + normalize. Proposes only."""

from .allocate import allocation, equal_weight, inverse_vol
from .signal import build_occ, normalize, parse_occ, propose
from .types import Allocation, Intent, Proposal

__all__ = [
    "Allocation",
    "Intent",
    "Proposal",
    "allocation",
    "equal_weight",
    "inverse_vol",
    "normalize",
    "propose",
    "build_occ",
    "parse_occ",
]
