"""Accent-insensitive, word-prefix search keys for foods."""

import re
import unicodedata

_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """'Caffè, nero (non zuccherato)' → 'caffe nero non zuccherato'."""
    folded = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    return " ".join(_NON_WORD.sub(" ", folded).split())


def search_key(*parts: str | None) -> str:
    """Every word preceded by a space, so `LIKE '% mel%'` matches word starts only:
    'mela' finds 'Mela, cruda' and 'Melanzana', but 'orata' does not find 'edulcorata'."""
    words = normalize(" ".join(p for p in parts if p))
    return f" {words} " if words else " "


def query_words(q: str) -> list[str]:
    return normalize(q).split()
