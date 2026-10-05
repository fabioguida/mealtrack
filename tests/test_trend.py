import pytest

from app.calc.trend import weekly_trend


def test_average_on_target_is_in_linea():
    eaten = [1800, 2000, 1900, 2200, 1700, 1900, 1800]
    t = weekly_trend([(e, 1900) for e in eaten])
    assert t.logged_days == 7
    assert t.eaten_avg == pytest.approx(1900)
    assert t.verdict == "in_linea" and "In linea" in t.text


def test_unlogged_days_are_skipped_not_zero():
    t = weekly_trend([(None, 1900), (1900, 1900), (None, 1900), (1950, 1900), (1850, 1900), (None, 1900), (None, 1900)])
    assert t.logged_days == 3 and t.verdict == "in_linea"


def test_too_few_days():
    t = weekly_trend([(1900, 1900), (1900, 1900)] + [(None, 1900)] * 5)
    assert t.verdict == "pochi_dati" and "almeno tre giorni" in t.text


def test_over_and_under():
    over = weekly_trend([(2200, 1900)] * 7)
    assert over.verdict == "sopra" and "circa 300 kcal" in over.text
    under = weekly_trend([(1500, 1900)] * 7)
    assert under.verdict == "sotto" and "circa 400 kcal" in under.text


def test_activity_raises_the_allowed_side():
    # 2200 eaten against 1900 + 300 of activity each day is on target.
    assert weekly_trend([(2200, 2200)] * 7).verdict == "in_linea"
