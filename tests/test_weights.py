from datetime import date, timedelta

from sqlalchemy import func, select

from app.models import Weight
from app.services import current_weight, targets_for


def test_log_and_list_weights(client, db, user):
    today = date.today()
    assert 'data-test="empty"' not in client.get("/peso").text  # the profile weigh-in exists
    r = client.post("/peso", data={"day": today.isoformat(), "kg": 84.2}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/peso"
    page = client.get("/peso").text
    assert "84.2 kg" in page
    assert 'data-test="chart"' not in page  # one point in the last 90 days: no chart yet
    client.post("/peso", data={"day": (today - timedelta(days=10)).isoformat(), "kg": 85.0})
    page = client.get("/peso").text
    assert 'data-test="chart"' in page and "<polyline" in page


def test_same_day_replaces(client, db, user):
    today = date.today().isoformat()
    client.post("/peso", data={"day": today, "kg": 84.0})
    client.post("/peso", data={"day": today, "kg": 83.5})
    rows = db.scalars(select(Weight).where(Weight.user_id == user.id, Weight.date == date.today())).all()
    assert len(rows) == 1 and rows[0].kg == 83.5


def test_weight_applies_from_its_date_onward(client, db, user):
    # Profile weigh-in: 85 kg on 2026-01-01. New weigh-in: 80 kg on 2026-03-01.
    client.post("/peso", data={"day": "2026-03-01", "kg": 80})
    assert current_weight(db, user, date(2026, 2, 1)) == 85
    assert current_weight(db, user, date(2026, 3, 1)) == 80
    assert current_weight(db, user, date(2026, 6, 1)) == 80
    # Before the first weigh-in, the earliest one is used rather than nothing.
    assert current_weight(db, user, date(2025, 1, 1)) == 85
    assert targets_for(db, user, date(2026, 2, 1)).kcal > targets_for(db, user, date(2026, 3, 1)).kcal
    assert "1913 kcal" in client.get("/giorno/2026-02-01").text
    assert "1844 kcal" in client.get("/giorno/2026-03-01").text  # 1705 × 1.375 − 500


def test_validation_and_delete(client, db, user):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    r = client.post("/peso", data={"day": tomorrow, "kg": 20})
    assert r.status_code == 200 and "nel futuro" in r.text and "Peso non valido" in r.text
    row = db.scalar(select(Weight).where(Weight.user_id == user.id))
    r = client.post(f"/peso/{row.id}/elimina", follow_redirects=False)
    assert r.status_code == 303
    assert db.scalar(select(func.count()).select_from(Weight)) == 0
    assert client.post("/peso/999/elimina", follow_redirects=False).status_code == 404
