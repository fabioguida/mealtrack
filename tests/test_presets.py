from datetime import date

import pytest
from sqlalchemy import func, select

from app.main import app
from app.models import Meal, MealPreset
from tests.conftest import login_client, make_user


def _meal(client, items, when="2026-10-05T07:30", meal_type="colazione"):
    r = client.post(
        "/pasti",
        data={"when": when, "meal_type": meal_type, "food_id": [f.id for f, _ in items], "grams": [g for _, g in items]},
        follow_redirects=False,
    )
    assert r.status_code == 303
    return int(r.headers["location"].rsplit("/", 1)[1])


def test_create_preset_from_meal_and_use_it(client, db, user, pasta, oil):
    meal_id = _meal(client, [(pasta, 140), (oil, 10)])
    r = client.post(f"/pasti/{meal_id}/salva-preset", data={"name": "Pasta della domenica"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/preset"
    preset = db.scalar(select(MealPreset).where(MealPreset.user_id == user.id))
    assert preset.name == "Pasta della domenica"
    assert sorted((i.food_id, i.grams) for i in preset.items) == sorted([(pasta.id, 140), (oil.id, 10)])

    page = client.get("/preset").text
    assert 'data-test="presets"' in page and "Pasta della domenica" in page and "608 kcal" in page

    # One tap: a meal for today with the same totals, opened for correction.
    r = client.post(f"/pasti/da-preset/{preset.id}", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("/modifica")
    new_id = int(r.headers["location"].split("/")[2])
    meal = db.get(Meal, new_id)
    assert meal.input_method == "preset" and meal.datetime.date() == date.today()
    assert sum(i.kcal for i in meal.items) == pytest.approx(607.8)

    # On another day, from the balance page's quick buttons.
    r = client.post(f"/pasti/da-preset/{preset.id}", params={"giorno": "2026-10-02"}, follow_redirects=False)
    assert db.get(Meal, int(r.headers["location"].split("/")[2])).datetime.date() == date(2026, 10, 2)
    assert 'data-test="quick-presets"' in client.get("/giorno/2026-10-02").text


def test_preset_form_create_edit_delete(client, db, user, pasta, oil):
    r = client.post("/preset", data={"name": "Pasta e olio", "food_id": [pasta.id, oil.id], "grams": [120, 5]}, follow_redirects=False)
    assert r.status_code == 303
    preset = db.scalar(select(MealPreset).where(MealPreset.user_id == user.id))
    assert len(preset.items) == 2

    assert "Modifica preset" in client.get(f"/preset/{preset.id}/modifica").text
    r = client.post(f"/preset/{preset.id}", data={"name": "Solo pasta", "food_id": [pasta.id], "grams": [150]}, follow_redirects=False)
    assert r.status_code == 303
    db.expire_all()
    preset = db.get(MealPreset, preset.id)
    assert preset.name == "Solo pasta" and [(i.food_id, i.grams) for i in preset.items] == [(pasta.id, 150)]

    r = client.post("/preset", data={"name": " ", "food_id": [], "grams": []})
    assert r.status_code == 422 and "Dai un nome" in r.text and "almeno un alimento" in r.text

    assert client.post(f"/preset/{preset.id}/elimina", follow_redirects=False).status_code == 303
    assert db.scalar(select(func.count()).select_from(MealPreset)) == 0


def test_presets_are_private(db, pasta):
    a = make_user(db, "a@example.com")
    b = make_user(db, "b@example.com")
    ca, cb = login_client(db, a), login_client(db, b)
    try:
        ca.post("/preset", data={"name": "Mio", "food_id": [pasta.id], "grams": [100]})
        preset = db.scalar(select(MealPreset).where(MealPreset.user_id == a.id))
        assert "Mio" not in cb.get("/preset").text
        assert cb.get(f"/preset/{preset.id}/modifica").status_code == 404
        assert cb.post(f"/pasti/da-preset/{preset.id}", follow_redirects=False).status_code == 404
        assert cb.post(f"/preset/{preset.id}/elimina", follow_redirects=False).status_code == 404
        assert "Mio" not in cb.get("/").text
    finally:
        app.dependency_overrides.clear()
