from dataclasses import dataclass

import pytest

from app.calc.nutrition import Totals, item_values, meal_totals


@dataclass
class Stub:
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


PASTA = Stub(371, 13.0, 74.7, 1.5)
OIL = Stub(884, 0, 0, 100)


def test_item_values_scales_per_100g():
    v = item_values(PASTA, 140)
    assert v.kcal == pytest.approx(519.4)
    assert v.protein_g == pytest.approx(18.2)
    assert v.carbs_g == pytest.approx(104.58)
    assert v.fat_g == pytest.approx(2.1)


def test_zero_grams_is_zero():
    assert item_values(PASTA, 0) == Totals()


def test_totals_are_the_sum_of_items():
    total = meal_totals([(PASTA, 140), (OIL, 10)])
    assert total.kcal == pytest.approx(519.4 + 88.4)
    assert total.protein_g == pytest.approx(18.2)
    assert total.carbs_g == pytest.approx(104.58)
    assert total.fat_g == pytest.approx(2.1 + 10)


def test_engine_does_not_round():
    # 1 g of a 371 kcal food is 3.71 kcal; rounding is for presentation only.
    assert item_values(PASTA, 1).kcal == pytest.approx(3.71)
    assert meal_totals([]) == Totals()
