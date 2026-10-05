import pytest

from app.calc.activity import MET_TABLE, kcal_burned, kcal_for


def test_met_formula():
    assert kcal_burned(3.5, 85, 60) == pytest.approx(297.5)
    assert kcal_burned(3.5, 85, 0) == 0
    assert kcal_for("camminata", 85, 60) == pytest.approx(297.5)
    assert kcal_for("tennis", 85, 45) == pytest.approx(7.3 * 85 * 0.75)


def test_unknown_activity_raises():
    with pytest.raises(KeyError):
        kcal_for("scacchi", 85, 60)


def test_table_has_a_compendium_code_per_row():
    assert {"camminata", "corsa", "palestra", "tennis"} <= MET_TABLE.keys()
    for a in MET_TABLE.values():
        assert a.compendium_code.isdigit() and 1.0 < a.met < 15
