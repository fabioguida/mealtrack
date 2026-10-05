from app.main import app
from app.services import usual_grams
from tests.conftest import login_client, make_user


def _meal(client, food, grams, when):
    r = client.post("/pasti", data={"when": when, "meal_type": "pranzo", "food_id": [food.id], "grams": [grams]}, follow_redirects=False)
    assert r.status_code == 303


def test_usual_portion_is_the_median_of_recent_meals(client, db, user, pasta):
    assert usual_grams(db, user, pasta.id) is None
    row = client.get("/pasti/riga", params={"food_id": pasta.id}).text
    assert 'value="100"' in row and 'data-test="usual"' not in row

    for grams, day in [(120, "01"), (140, "02"), (160, "03")]:
        _meal(client, pasta, grams, f"2026-10-{day}T13:00")
    assert usual_grams(db, user, pasta.id) == 140
    row = client.get("/pasti/riga", params={"food_id": pasta.id}).text
    assert 'value="140"' in row and "di solito 140 g" in row

    # Only the last five count: six more at 200 g push the old ones out.
    for day in range(4, 10):
        _meal(client, pasta, 200, f"2026-10-0{day}T13:00" if day < 10 else f"2026-10-{day}T13:00")
    assert usual_grams(db, user, pasta.id) == 200

    # An even sample takes the mean of the two middle values.
    _meal(client, pasta, 100, "2026-10-10T13:00")
    _meal(client, pasta, 100, "2026-10-11T13:00")
    _meal(client, pasta, 100, "2026-10-12T13:00")
    _meal(client, pasta, 100, "2026-10-13T13:00")
    # last five: 100,100,100,100,200 → median 100
    assert usual_grams(db, user, pasta.id) == 100


def test_library_is_per_user(db, pasta):
    a = make_user(db, "a@example.com")
    b = make_user(db, "b@example.com")
    ca, cb = login_client(db, a), login_client(db, b)
    try:
        _meal(ca, pasta, 140, "2026-10-01T13:00")
        assert usual_grams(db, a, pasta.id) == 140
        assert usual_grams(db, b, pasta.id) is None
        assert "di solito" not in cb.get("/pasti/riga", params={"food_id": pasta.id}).text
    finally:
        app.dependency_overrides.clear()
