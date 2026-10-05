"""Judge a day's totals against the targets, for the four balance bars."""

from dataclasses import dataclass

from app.calc.nutrition import Totals
from app.calc.targets import Targets


@dataclass(frozen=True)
class Bar:
    value: float
    target: float

    @property
    def fraction(self) -> float:
        return self.value / self.target if self.target > 0 else 0.0

    @property
    def percent(self) -> int:
        """Fill width for the bar, capped at 100."""
        return min(100, round(100 * self.fraction))

    @property
    def over(self) -> bool:
        return self.value > self.target

    @property
    def remaining(self) -> float:
        return self.target - self.value


@dataclass(frozen=True)
class DayBalance:
    kcal: Bar
    protein: Bar
    carbs: Bar
    fat: Bar


def assess(totals: Totals, targets: Targets, extra_kcal: float = 0.0) -> DayBalance:
    """`extra_kcal` is what logged activity adds to the day's ceiling (phase 5)."""
    return DayBalance(
        kcal=Bar(totals.kcal, targets.kcal + extra_kcal),
        protein=Bar(totals.protein_g, targets.protein_g),
        carbs=Bar(totals.carbs_g, targets.carbs_g),
        fat=Bar(totals.fat_g, targets.fat_g),
    )
