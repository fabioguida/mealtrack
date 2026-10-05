import pytest

from app.calc.targets import (
    ACTIVITY_FACTORS,
    bmr_mifflin,
    daily_targets,
    kcal_target,
    protein_target,
    tdee,
)


def test_mifflin_st_jeor():
    assert bmr_mifflin("M", 85, 180, 45) == pytest.approx(1755.0)
    assert bmr_mifflin("F", 85, 180, 45) == pytest.approx(1589.0)
    assert bmr_mifflin("m", 85, 180, 45) == pytest.approx(1755.0)


def test_tdee_and_target_are_parameterised():
    t = tdee(1755.0, 1.375)
    assert t == pytest.approx(2413.125)
    assert round(t, 1) == 2413.1
    assert kcal_target(t, 500) == pytest.approx(1913.125)
    assert kcal_target(t, 300) == pytest.approx(2113.125)


def test_protein_target():
    assert protein_target(85, 1.5) == pytest.approx(127.5)
    assert protein_target(85, 1.2) == pytest.approx(102.0)


def test_daily_targets():
    t = daily_targets("M", 45, 180, 85, "leggero", 500, 1.5)
    assert t.bmr == pytest.approx(1755.0)
    assert t.tdee == pytest.approx(2413.125)
    assert t.kcal == pytest.approx(1913.125)
    assert t.protein_g == pytest.approx(127.5)
    # Fat 30 % of kcal; carbs take the rest; the three add up to the kcal target.
    assert t.fat_g == pytest.approx(0.30 * 1913.125 / 9)
    assert 4 * t.protein_g + 9 * t.fat_g + 4 * t.carbs_g == pytest.approx(1913.125)


def test_activity_factors_cover_the_standard_range():
    assert ACTIVITY_FACTORS["sedentario"] == 1.2
    assert ACTIVITY_FACTORS["molto_attivo"] == 1.9
    with pytest.raises(KeyError):
        daily_targets("M", 45, 180, 85, "pigro", 500, 1.5)
