import pytest
from sqlalchemy import func, select

from app.models import Food, Meal, MealItem, User
from tests.conftest import make_food


def _post_meal(client, items, when="2026-10-05T13:30", meal_type="pranzo", url="/pasti"):
    data = {"when": when, "meal_type": meal_type}
    if items:
        data["food_id"] = [f.id for f, _ in items]
        data["grams"] = [g for _, g in items]
    return client.post(url, data=data, follow_redirects=False)


def test_new_meal_page(client):
    r = client.get("/pasti/nuovo")
    assert r.status_code == 200
    assert "Nuovo pasto" in r.text
    assert "/static/js/htmx.min.js" in r.text


def test_search_partial(client, pasta, oil):
    r = client.get("/alimenti/cerca", params={"q": "pasta"})
    assert r.status_code == 200
    assert "Pasta, cooked" in r.text
    assert "Oil, olive" not in r.text

    r = client.get("/alimenti/cerca", params={"q": "zzzz"})
    assert 'data-test="no-results"' in r.text

    # Fewer than two characters: nothing is searched.
    r = client.get("/alimenti/cerca", params={"q": "p"})
    assert "Pasta" not in r.text and "no-results" not in r.text


def test_search_is_case_insensitive_and_matches_italian_alias(client, db, pasta):
    pasta.name_it = "Pasta cotta"
    db.commit()
    assert "Pasta cotta" in client.get("/alimenti/cerca", params={"q": "COTTA"}).text


def test_row_and_totals_partials(client, pasta, oil):
    r = client.get("/pasti/riga", params={"food_id": pasta.id})
    assert r.status_code == 200
    assert f'name="food_id" value="{pasta.id}"' in r.text

    r = client.post(
        "/pasti/totali",
        data={"food_id": [pasta.id, oil.id], "grams": [140, 10]},
    )
    assert 'data-test="kcal">607.8<' in r.text
    assert 'data-test="protein">18.2 g<' in r.text


def test_create_meal_stores_computed_values(client, db, pasta, oil):
    r = _post_meal(client, [(pasta, 140), (oil, 10)])
    assert r.status_code == 303
    meal_id = int(r.headers["location"].rsplit("/", 1)[1])

    assert db.scalar(select(func.count()).select_from(Meal)) == 1
    items = db.scalars(select(MealItem).where(MealItem.meal_id == meal_id)).all()
    assert len(items) == 2
    by_food = {i.food_id: i for i in items}
    assert by_food[pasta.id].kcal == pytest.approx(519.4)
    assert by_food[pasta.id].carbs_g == pytest.approx(104.58)
    assert by_food[oil.id].fat_g == pytest.approx(10)

    page = client.get(f"/pasti/{meal_id}")
    assert page.status_code == 200
    assert "Pranzo" in page.text and "lun 5 ott 2026, 13:30" in page.text
    assert 'data-test="kcal">607.8<' in page.text


def test_edit_meal_updates_values(client, db, pasta, oil):
    meal_id = int(_post_meal(client, [(pasta, 140)]).headers["location"].rsplit("/", 1)[1])

    r = client.get(f"/pasti/{meal_id}/modifica")
    assert r.status_code == 200 and "Modifica pasto" in r.text

    r = _post_meal(client, [(pasta, 200)], meal_type="cena", url=f"/pasti/{meal_id}")
    assert r.status_code == 303
    db.expire_all()
    meal = db.get(Meal, meal_id)
    assert meal.meal_type == "cena"
    assert len(meal.items) == 1
    assert meal.items[0].grams == 200
    assert meal.items[0].kcal == pytest.approx(742)


def test_delete_meal(client, db, pasta):
    meal_id = int(_post_meal(client, [(pasta, 140)]).headers["location"].rsplit("/", 1)[1])
    r = client.post(f"/pasti/{meal_id}/elimina", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/pasti"
    assert db.get(Meal, meal_id) is None
    assert db.scalar(select(func.count()).select_from(MealItem)) == 0
    assert client.get(f"/pasti/{meal_id}").status_code == 404


def test_meal_without_items_is_rejected(client):
    r = _post_meal(client, [])
    assert r.status_code == 422
    assert "Aggiungi almeno un alimento." in r.text


def test_non_positive_grams_rejected(client, pasta):
    r = _post_meal(client, [(pasta, 0)])
    assert r.status_code == 422
    assert "Grammi non validi" in r.text


def test_meal_list(client, pasta):
    assert 'data-test="empty"' in client.get("/pasti").text
    _post_meal(client, [(pasta, 100)])
    r = client.get("/pasti")
    assert 'data-test="meals"' in r.text and "371 kcal" in r.text


def test_custom_food_visible_only_to_owner(client, db, user):
    other = User(email="other@example.com")
    db.add(other)
    db.commit()
    mine = make_food(db, "Pasta e ceci della nonna", 150, 6, 22, 4, owner=user)
    theirs = make_food(db, "Pasta al pesto di Luca", 200, 7, 25, 8, owner=other)

    r = client.get("/alimenti/cerca", params={"q": "pasta"})
    assert "della nonna" in r.text
    assert "di Luca" not in r.text

    # Nor can another user's food be put in a meal.
    r = _post_meal(client, [(theirs, 100)])
    assert r.status_code == 422 and "Alimento non trovato." in r.text
    assert _post_meal(client, [(mine, 100)]).status_code == 303


def test_create_custom_food(client, db, user):
    assert client.get("/alimenti/nuovo").status_code == 200
    r = client.post(
        "/alimenti",
        data={"name": "Orata al forno", "kcal": 130, "protein_g": 20, "carbs_g": 0, "fat_g": 5},
        follow_redirects=False,
    )
    assert r.status_code == 303 and r.headers["location"] == "/pasti/nuovo"
    food = db.scalar(select(Food).where(Food.name == "Orata al forno"))
    assert food.source == "custom" and food.owner_user_id == user.id

    r = client.post(
        "/alimenti",
        data={"name": " ", "kcal": -1, "protein_g": 0, "carbs_g": 0, "fat_g": 0},
    )
    assert r.status_code == 422
    assert "Il nome è obbligatorio." in r.text and "negativi" in r.text
