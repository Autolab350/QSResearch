"""Boundary checks — Portfolio must not import autodesk or marketdata."""

from __future__ import annotations

from pathlib import Path


def test_no_autodesk_or_marketdata_imports():
    root = Path(__file__).resolve().parents[1] / "portfolio"
    banned = ("import autodesk", "from autodesk", "import marketdata", "from marketdata")
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for token in banned:
                if token in stripped:
                    hits.append(f"{path.relative_to(root.parent)}: {stripped}")
    assert hits == [], f"Boundary violations: {hits}"
