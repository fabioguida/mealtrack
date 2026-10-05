"""Composite dishes ("Piatti"): recipes of basic foods with typical grams.

They are a shortcut in the food search: one tap inserts every ingredient as an
editable row. The list lives in data/recipes_it.json and grows on request.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app.config import PROJECT_ROOT
from app.models import Food
from app.textsearch import query_words, search_key

RECIPE_FILE = PROJECT_ROOT / "data" / "recipes_it.json"
SEARCH_LIMIT = 6


@dataclass(frozen=True)
class Recipe:
    key: str
    name: str
    synonyms: str
    ingredients: tuple[tuple[str, str, float], ...]  # (source, id, grams)

    @property
    def search_key(self) -> str:
        return search_key(self.name, self.synonyms)


@lru_cache(maxsize=1)
def load_recipes(path: Path = RECIPE_FILE) -> tuple[Recipe, ...]:
    data = json.loads(path.read_text(encoding="utf-8"))["recipes"]
    return tuple(
        Recipe(
            key=r["key"],
            name=r["name"],
            synonyms=r.get("synonyms", ""),
            ingredients=tuple((i["source"], str(i["id"]), float(i["grams"])) for i in r["ingredients"]),
        )
        for r in data
    )


def recipe_by_key(key: str) -> Recipe | None:
    return next((r for r in load_recipes() if r.key == key), None)


def search_recipes(q: str, limit: int = SEARCH_LIMIT) -> list[Recipe]:
    """Every query word must start a word of the recipe's name or synonyms."""
    words = query_words(q)
    if not words or len("".join(words)) < 2:
        return []
    hits = [r for r in load_recipes() if all(f" {w}" in r.search_key for w in words)]
    # Matches on the name itself before matches through synonyms, shorter names first.
    hits.sort(key=lambda r: (not all(f" {w}" in search_key(r.name) for w in words), len(r.name)))
    return hits[:limit]


def resolve(db: Session, recipe: Recipe) -> list[tuple[Food, float]] | None:
    """The recipe's foods from the table, or None if any is missing."""
    refs = [(s, i) for s, i, _ in recipe.ingredients]
    foods = {
        (f.source, f.source_id): f
        for f in db.scalars(select(Food).where(tuple_(Food.source, Food.source_id).in_(refs)))
    }
    out = []
    for source, source_id, grams in recipe.ingredients:
        food = foods.get((source, source_id))
        if food is None:
            return None
        out.append((food, grams))
    return out
