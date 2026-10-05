"""The one calculation engine: a list of (food, grams) → kcal and macros.

Every way of entering a meal (manual, preset, photo) ends up here. Values are
not rounded; rounding is a presentation matter.
"""

from dataclasses import dataclass
from typing import Protocol


class FoodLike(Protocol):
    """Anything with per-100 g nutrient values (a Food row or a test stub)."""

    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


@dataclass(frozen=True)
class Totals:
    kcal: float = 0.0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0

    def __add__(self, other: "Totals") -> "Totals":
        return Totals(
            self.kcal + other.kcal,
            self.protein_g + other.protein_g,
            self.carbs_g + other.carbs_g,
            self.fat_g + other.fat_g,
        )


def item_values(food: FoodLike, grams: float) -> Totals:
    factor = grams / 100.0
    return Totals(
        kcal=food.kcal * factor,
        protein_g=food.protein_g * factor,
        carbs_g=food.carbs_g * factor,
        fat_g=food.fat_g * factor,
    )


def meal_totals(items: list[tuple[FoodLike, float]]) -> Totals:
    total = Totals()
    for food, grams in items:
        total = total + item_values(food, grams)
    return total
