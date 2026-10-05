from datetime import date

import pytest
from sqlalchemy import func, select

from app.models import EatingSchedule, FoodPreference, Meal, MealPlan
from app.plan_service import schedule_for
from tests.plan_foods import load_plan_foods

AUTHOR = {}
for dow in range(7):
    AUTHOR[f"eat_{dow}_colazione"] = "1"; AUTHOR[f"time_{dow}_colazione"] = "07:30"; AUTHOR[f"share_{dow}_colazione"] = "30"
    AUTHOR[f"eat_{dow}_pranzo"] = "1"; AUTHOR[f"time_{dow}_pranzo"] = "13:30"
    AUTHOR[f"share_{dow}_pranzo"] = "45" if dow <= 3 else "25" if dow <= 5 else "70"
    if dow <= 3:
        AUTHOR[f"eat_{dow}_spezzafame"] = "1"; AUTHOR[f"time_{dow}_spezzafame"] = "15:30"; AUTHOR[f"share_{dow}_spezzafame"] = "25"


@pytest.fixture
def plan_foods(db):
    return load_plan_foods(db)


def test_default_schedule_and_saving(client, db, user):
    default = schedule_for(db, user)
    assert [r.meal_type for r in default[0]] == ["colazione", "pranzo", "spezzafame", "cena"]
    assert db.scalar(select(func.count()).select_from(EatingSchedule)) == 0

    r = client.post("/orari", data=AUTHOR, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/piano"
    saved = schedule_for(db, user)
    assert [r.meal_type for r in saved[0]] == ["colazione", "pranzo", "spezzafame"]
    assert [r.meal_type for r in saved[4]] == ["colazione", "pranzo"]
    assert saved[6][1].share == 0.70 and saved[0][0].time == "07:30"
    page = client.get("/orari").text
    assert 'name="eat_0_spezzafame" value="1" checked' in page and 'name="eat_4_spezzafame" value="1">' in page


def test_schedule_validation(client):
    bad = {**AUTHOR, "share_0_pranzo": "80", "time_1_colazione": "7h30"}
    r = client.post("/orari", data=bad)
    assert r.status_code == 422
    assert "Lunedì: le quote superano il 100 %." in r.text and "Martedì, colazione: orario non valido." in r.text


def test_preferences(client, db, user, plan_foods):
    r = client.post("/preferenze", data={"cat_carne": "avoid", "cat_pesce": "like", "cat_pasta": ""}, follow_redirects=False)
    assert r.status_code == 303
    page = client.get("/preferenze").text
    assert 'name="cat_carne" value="avoid" checked' in page and 'name="cat_pesce" value="like" checked' in page

    clams = next(f for f in plan_foods if "clam" in f.name)
    assert client.post(f"/preferenze/alimento/{clams.id}/avoid", follow_redirects=False).status_code == 303
    assert "evito" in client.get("/preferenze").text
    r = client.get("/alimenti/cerca", params={"q": "clam", "mode": "pref"})
    assert f"/preferenze/alimento/{clams.id}/avoid" in r.text
    pref = db.scalar(select(FoodPreference).where(FoodPreference.food_id == clams.id))
    assert client.post(f"/preferenze/{pref.id}/elimina", follow_redirects=False).status_code == 303
    assert client.post("/preferenze/alimento/999999/avoid", follow_redirects=False).status_code == 404


def test_generate_plan_and_confirm_a_meal(client, db, user, plan_foods):
    client.post("/orari", data=AUTHOR)
    assert 'data-test="no-plan"' in client.get("/piano").text

    r = client.post("/piano/rigenera", follow_redirects=False)
    assert r.status_code == 303
    plan = db.scalar(select(MealPlan).where(MealPlan.user_id == user.id))
    assert plan.weeks == 2 and plan.start_date == date.today()
    assert round(plan.kcal_target) == 1913 and plan.protein_target_g == 127.5

    page = client.get("/piano").text
    assert page.count('data-test="plan-day"') == 14
    assert 'data-test="stale"' not in page and 'data-test="skipped"' not in page

    # Today's balance suggests the planned meals; confirming one logs it.
    today = date.today()
    home = client.get("/").text
    assert 'data-test="suggestions"' in home
    planned = [i for i in plan.items if i.date == today and i.meal_type == "colazione"]
    assert planned
    r = client.post("/piano/conferma", data={"giorno": today.isoformat(), "pasto": "colazione"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("/modifica")
    meal = db.scalar(select(Meal).where(Meal.user_id == user.id))
    assert meal.input_method == "plan" and meal.meal_type == "colazione"
    assert meal.datetime.hour == 7 and meal.datetime.minute == 30
    assert sum(i.kcal for i in meal.items) == pytest.approx(sum(i.kcal for i in planned))
    assert sorted((i.food_id, i.grams) for i in meal.items) == sorted((i.food_id, i.grams) for i in planned)
    # Once logged, that meal type is no longer suggested.
    home = client.get("/").text
    assert "Colazione:" not in home.split('data-test="suggestions"')[1].split("</ul>")[0] if 'data-test="suggestions"' in home else True

    # Regenerating replaces the plan rather than piling up.
    client.post("/piano/rigenera")
    assert db.scalar(select(func.count()).select_from(MealPlan)) == 1

    assert client.post("/piano/conferma", data={"giorno": "2020-01-01", "pasto": "cena"}, follow_redirects=False).status_code == 404


def test_stale_plan_hint(client, db, user, plan_foods):
    client.post("/orari", data=AUTHOR)
    client.post("/piano/rigenera")
    assert 'data-test="stale"' not in client.get("/piano").text
    # A big weight change moves the target by more than 5 %.
    client.post("/peso", data={"day": date.today().isoformat(), "kg": 70})
    assert 'data-test="stale"' in client.get("/piano").text


def test_plan_needs_a_profile(db):
    from app.main import app
    from tests.conftest import login_client, make_user

    u = make_user(db, "new@example.com", with_profile=False)
    c = login_client(db, u)
    try:
        r = c.post("/piano/rigenera", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/profilo"
    finally:
        app.dependency_overrides.clear()
