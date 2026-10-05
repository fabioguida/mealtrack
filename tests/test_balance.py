from datetime import date, timedelta

import pytest

from app.calc.balance import assess
from app.calc.nutrition import Totals
from app.calc.targets import Targets
from tests.conftest import make_food

TARGETS = Targets(bmr=1700, tdee=2300, kcal=1900, protein_g=120, carbs_g=200, fat_g=60)


@pytest.fixture
def fixed_targets(client):
    """The `user` fixture's profile gives a 1913.125 kcal target."""
    yield


@pytest.fixture
def chow(db):
    # 400 kcal per 100 g: grams / 4 = kcal, which keeps the test numbers round.
    return make_food(db, "Chow", 400, 10, 50, 15)


def _log(client, food, grams, when):
    r = client.post(
        "/pasti",
        data={"when": when, "meal_type": "pranzo", "food_id": [food.id], "grams": [grams]},
        follow_redirects=False,
    )
    assert r.status_code == 303


def test_assess_bars():
    b = assess(Totals(1600, 60, 100, 30), TARGETS)
    assert b.kcal.remaining == 300 and not b.kcal.over and b.kcal.percent == 84
    assert b.protein.remaining == 60 and b.protein.percent == 50
    over = assess(Totals(2100, 130, 0, 0), TARGETS)
    assert over.kcal.over and over.kcal.remaining == -200 and over.kcal.percent == 100
    assert over.protein.over and over.protein.percent == 100
    # Activity raises the ceiling (phase 5 feeds this).
    assert assess(Totals(2100, 0, 0, 0), TARGETS, extra_kcal=300).kcal.remaining == 100


def test_within_target_is_green_with_remaining(client, fixed_targets, chow):
    today = date.today().isoformat()
    _log(client, chow, 400, f"{today}T13:30")  # 1,600 kcal
    r = client.get("/")
    assert r.status_code == 200
    assert 'class="barra grande ok"' in r.text
    assert "rimangono 313 kcal" in r.text
    assert 'data-test="kcal">1600<' in r.text
    assert 'data-test="day-meals"' in r.text
    assert f"/giorno/{(date.today() - timedelta(days=1)).isoformat()}" in r.text


def test_over_target_is_red(client, fixed_targets, chow):
    today = date.today().isoformat()
    _log(client, chow, 525, f"{today}T13:30")  # 2,100 kcal
    r = client.get("/")
    assert 'class="barra grande over"' in r.text
    assert "187 kcal oltre il target" in r.text


def test_empty_day_and_disclaimer(client, fixed_targets):
    r = client.get("/")
    assert 'data-test="empty"' in r.text
    assert "Nessun pasto registrato oggi." in r.text
    assert "L'app mostra stime, non prescrizioni mediche." in r.text
    assert 'data-test="kcal">0<' in r.text


def test_past_day_lists_only_that_day(client, fixed_targets, chow):
    _log(client, chow, 100, "2026-10-01T08:00")
    _log(client, chow, 200, "2026-10-02T08:00")
    r = client.get("/giorno/2026-10-02")
    assert r.status_code == 200
    assert "ven 2 ott 2026" in r.text
    assert 'data-test="kcal">800<' in r.text  # only the 200 g meal
    assert "torna a oggi" in r.text
    assert "/pasti/nuovo?giorno=2026-10-02" in r.text

    assert client.get("/giorno/not-a-date").status_code == 404


def test_htmx_navigation_returns_partial(client, fixed_targets):
    r = client.get("/giorno/2026-10-02", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "<html" not in r.text
    assert 'data-test="day">ven 2 ott 2026<' in r.text


def test_new_meal_form_keeps_requested_day(client):
    r = client.get("/pasti/nuovo", params={"giorno": "2026-10-02"})
    assert 'value="2026-10-02T' in r.text
