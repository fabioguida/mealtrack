from datetime import date

from sqlalchemy import select

from app.models import Profile, Weight
from app.services import current_weight, targets_for
from tests.conftest import login_client, make_user

FORM = dict(sex="M", age=45, height_cm=180, weight_kg=85, activity="leggero",
            goal="dimagrire", deficit_kcal=500, protein_g_per_kg=1.5)


def test_profile_page_shows_targets(client):
    r = client.get("/profilo")
    assert r.status_code == 200
    assert 'data-test="targets"' in r.text
    assert "1913 kcal" in r.text and "128 g" in r.text


def test_saving_profile_recalculates_targets(client, db, user):
    r = client.post("/profilo", data={**FORM, "weight_kg": 80, "deficit_kcal": 300}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    t = targets_for(db, user, date.today())
    # BMR 1705 × 1.375 = 2344.375 − 300
    assert round(t.kcal) == 2044
    assert t.protein_g == 120
    assert "2044 kcal" in client.get("/").text
    # The weight became today's weigh-in.
    assert current_weight(db, user) == 80
    assert db.scalar(select(Weight).where(Weight.user_id == user.id, Weight.date == date.today())).kg == 80


def test_maintain_goal_ignores_deficit(client, db, user):
    client.post("/profilo", data={**FORM, "goal": "mantenere"}, follow_redirects=False)
    assert round(targets_for(db, user).kcal) == 2413


def test_new_user_fills_profile_first(db):
    u = make_user(db, "new@example.com", with_profile=False)
    c = login_client(db, u)
    try:
        assert targets_for(db, u) is None
        assert c.get("/", follow_redirects=False).headers["location"] == "/profilo"
        r = c.post("/profilo", data=FORM, follow_redirects=False)
        assert r.status_code == 303
        assert db.get(Profile, u.id) is not None
        assert c.get("/").status_code == 200
    finally:
        from app.main import app
        app.dependency_overrides.clear()


def test_profile_validation(client):
    r = client.post("/profilo", data={**FORM, "age": 0, "height_cm": 50, "weight_kg": 10})
    assert r.status_code == 422
    assert "Età non valida" in r.text and "Altezza non valida" in r.text and "Peso non valido" in r.text
    r = client.post("/profilo", data={**FORM, "activity": "pigro", "protein_g_per_kg": 5})
    assert r.status_code == 422 and "attività non valido" in r.text and "Proteine per kg" in r.text
