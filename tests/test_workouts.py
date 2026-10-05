from datetime import date

import pytest
from sqlalchemy import func, select

from app.models import Workout
from tests.conftest import make_food


def test_log_workout_uses_that_days_weight(client, db, user):
    r = client.post("/attivita", data={"day": "2026-10-05", "activity": "tennis", "duration_min": 45}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/attivita"
    w = db.scalar(select(Workout).where(Workout.user_id == user.id))
    assert w.kcal_burned == pytest.approx(7.3 * 85 * 0.75)
    page = client.get("/attivita").text
    assert "Tennis (singolo)" in page and "465 kcal" in page


def test_workout_raises_the_days_ceiling(client, db, user):
    chow = make_food(db, "Chow", 400, 10, 50, 15)
    client.post("/pasti", data={"when": "2026-10-05T13:30", "meal_type": "pranzo", "food_id": [chow.id], "grams": [525]})  # 2,100 kcal
    r = client.get("/giorno/2026-10-05")
    assert 'class="barra grande over"' in r.text
    assert "187 kcal oltre il target" in r.text  # 2100 − 1913

    client.post("/attivita", data={"day": "2026-10-05", "activity": "camminata", "duration_min": 60})  # 297.5 kcal
    r = client.get("/giorno/2026-10-05")
    assert 'class="barra grande ok"' in r.text
    assert "rimangono 111 kcal" in r.text  # 1913.125 + 297.5 − 2100
    assert 'data-test="activity"' in r.text and "298 di attività" in r.text
    assert 'data-test="day-workouts"' in r.text


def test_validation_and_delete(client, db, user):
    r = client.post("/attivita", data={"day": "2026-10-05", "activity": "scacchi", "duration_min": 0})
    assert r.status_code == 200 and "Attività non valida" in r.text and "Durata non valida" in r.text
    client.post("/attivita", data={"day": "2026-10-05", "activity": "yoga", "duration_min": 30})
    w = db.scalar(select(Workout).where(Workout.user_id == user.id))
    assert client.post(f"/attivita/{w.id}/elimina", follow_redirects=False).status_code == 303
    assert db.scalar(select(func.count()).select_from(Workout)) == 0
    assert client.post("/attivita/999/elimina", follow_redirects=False).status_code == 404


def test_weekly_trend_on_balance_page(client, db, user):
    chow = make_food(db, "Chow", 400, 10, 50, 15)
    # 478 g ≈ 1913 kcal on seven consecutive days → in linea.
    for d in range(1, 8):
        client.post("/pasti", data={"when": f"2026-10-0{d}T13:30", "meal_type": "pranzo", "food_id": [chow.id], "grams": [478]})
    r = client.get("/giorno/2026-10-07")
    assert 'class="settimana in_linea"' in r.text
    assert "7 giorni registrati" in r.text
    r = client.get("/giorno/2026-10-02")
    assert "almeno tre giorni" in r.text  # only two logged days in that window
