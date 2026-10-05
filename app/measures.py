"""Household measures ("misure casalinghe"): tappable grams for a food."""

import json
from functools import lru_cache
from pathlib import Path

from app.config import PROJECT_ROOT
from app.textsearch import normalize

MEASURES_FILE = PROJECT_ROOT / "data" / "household_measures_it.json"


@lru_cache(maxsize=1)
def _load(path: Path = MEASURES_FILE) -> list[tuple[tuple[str, ...], tuple[tuple[str, int], ...]]]:
    data = json.loads(path.read_text(encoding="utf-8"))["measures"]
    return [(tuple(normalize(m) for m in e["match"]), tuple((c[0], int(c[1])) for c in e["chips"])) for e in data]


def measures_for(name: str, synonyms: str | None = None, category: str | None = None) -> list[tuple[str, int]]:
    """Chips for a food: the first entry whose words all occur in the food's text."""
    text = " " + normalize(" ".join(p for p in (name, synonyms, category) if p)) + " "
    for matches, chips in _load():
        for m in matches:
            if all(f" {w}" in text for w in m.split()):
                return list(chips)
    return []
