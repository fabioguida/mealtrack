"""Two users never see each other's data."""

from app.main import app
from tests.conftest import login_client, make_food, make_user


def _meal(client, food, grams=100, when="2026-10-05T13:30"):
    r = client.post(
        "/pasti",
        data={"when": when, "meal_type": "pranzo", "food_id": [food.id], "grams": [grams]},
        follow_redirects=False,
    )
    assert r.status_code == 303
    return int(r.headers["location"].rsplit("/", 1)[1])


def test_users_are_isolated(db, pasta):
    a = make_user(db, "a@example.com")
    b = make_user(db, "b@example.com", weight=95)
    ca, cb = login_client(db, a), login_client(db, b)
    try:
        mine = make_food(db, "Pasta e ceci della nonna", 150, 6, 22, 4, owner=a)
        theirs = make_food(db, "Pasta al pesto di Luca", 200, 7, 25, 8, owner=b)

        meal_a = _meal(ca, pasta, 100)
        meal_b = _meal(cb, pasta, 200)

        # Balance and lists show only one's own meals.
        assert 'data-test="kcal">371<' in ca.get("/giorno/2026-10-05").text
        assert 'data-test="kcal">742<' in cb.get("/giorno/2026-10-05").text
        assert f"/pasti/{meal_b}" not in ca.get("/pasti").text
        assert f"/pasti/{meal_a}" not in cb.get("/pasti").text

        # Another user's meal does not exist, as far as you can tell (404, not 403).
        assert ca.get(f"/pasti/{meal_b}").status_code == 404
        assert ca.get(f"/pasti/{meal_b}/modifica").status_code == 404
        assert ca.post(f"/pasti/{meal_b}/elimina", follow_redirects=False).status_code == 404
        assert cb.get(f"/pasti/{meal_b}").status_code == 200

        # Custom foods: searchable and usable only by their owner.
        r = ca.get("/alimenti/cerca", params={"q": "pasta"})
        assert "della nonna" in r.text and "di Luca" not in r.text
        r = ca.post("/pasti", data={"when": "2026-10-05T20:00", "meal_type": "cena", "food_id": [theirs.id], "grams": [100]})
        assert r.status_code == 422 and "Alimento non trovato." in r.text
        assert ca.get("/pasti/riga", params={"food_id": theirs.id}).status_code == 404
        assert ca.get("/pasti/riga", params={"food_id": mine.id}).status_code == 200

        # Profiles are separate: a heavier B has a higher target.
        assert 'value="85"' in ca.get("/profilo").text and "1913 kcal" in ca.get("/profilo").text
        assert 'value="95"' in cb.get("/profilo").text and "2051 kcal" in cb.get("/profilo").text
    finally:
        app.dependency_overrides.clear()
