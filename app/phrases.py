"""The human lines of the emails, from data/email_phrases_it.json, rotated by date."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from app.config import PROJECT_ROOT

PHRASES_FILE = PROJECT_ROOT / "data" / "email_phrases_it.json"


@lru_cache(maxsize=1)
def _load(path: Path = PHRASES_FILE) -> dict[str, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def phrase(situation: str, seed: str, **values) -> str:
    """One line for the situation, chosen by `seed` (date + user) so it varies
    from day to day but is stable within the day; '' if the situation is unknown."""
    lines = _load().get(situation) or []
    if not lines:
        return ""
    idx = int(hashlib.sha1(f"{situation}:{seed}".encode()).hexdigest(), 16) % len(lines)
    try:
        return lines[idx].format(**values)
    except (KeyError, IndexError):
        return lines[idx]
