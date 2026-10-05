"""The fun layer of the site: mascot and line on Oggi, streak, milestones,
confetti, cards from the plan, the empty plate, the weight summary."""

from datetime import date, timedelta

from app.models import Weight
from app.mood import mood_for
from tests.plan_foods import load_plan_foods
from tests.test_plan_routes import AUTHOR


def _log(client, day, grams, pasta):
    client.post("/pasti", data={"when": f"{day.isoformat()}T13:00", "meal_type": "pranzo", "food_id": [pasta.id], "grams": [grams]})


def test_oggi_shows_mascot_line_and_fun_empty_state(client, db, user, pasta):
    page = client.get("/").text
    assert 'data-test="mood"' in page and 'data-mascot="sleepy"' in page and "face-sleepy.png" in page
    assert 'data-test="empty"' in page and "Nessun pasto registrato oggi." in page and "plate.png" in page
    assert 'data-test="streak"' not in page  # one day is not a streak
    _log(client, date.today(), 500, pasta)   # 1855 of 1913 kcal: on target, within ±5 %
    page = client.get("/").text
    assert 'data-mascot="happy"' in page and "✓ centrato" in page and "barra grande centrata" in page
    _log(client, date.today(), 300, pasta)   # over
    page = client.get("/").text
    assert 'data-mascot="sweaty"' in page and "kcal oltre il target" in page and "centrata" not in page


def test_other_days_have_no_mood_but_a_kind_empty_line(client, db, user):
    yesterday = date.today() - timedelta(days=1)
    page = client.get(f"/giorno/{yesterday.isoformat()}").text
    assert 'data-test="mood"' not in page and 'data-test="empty"' in page and "Nessun pasto registrato." in page


def test_streak_milestone_and_confetti(client, db, user, pasta):
    today = date.today()
    for d in range(3):
        _log(client, today - timedelta(days=d), 500, pasta)
    m = mood_for(db, user, today)
    assert m.streak == 3 and m.show_streak and m.celebrate and m.mascot == "party"
    page = client.get("/").text
    assert 'data-test="streak"' in page and "<b>3</b> giorni di fila" in page
    assert 'data-test="milestone"' in page and "Tre giorni di fila" in page
    assert f'data-celebrate="{today.isoformat()}"' in page and "coriandoli" in page
    assert 'data-test="mood"' in client.get(f"/giorno/{today.isoformat()}").text  # the day route is today too


def test_plan_suggestions_are_cards(client, db, user):
    load_plan_foods(db)
    client.post("/orari", data=AUTHOR)
    client.post("/piano/rigenera")
    page = client.get("/").text
    assert 'class="carte" data-test="suggestions"' in page and 'class="carta"' in page and "Conferma" in page


def test_weight_summary_and_chart_labels(client, db, user):
    today = date.today()
    page = client.get("/peso").text
    assert 'data-test="weight-summary"' in page and 'data-mascot="sleepy"' in page  # the only weigh-in is months old
    db.add(Weight(user_id=user.id, date=today - timedelta(days=3), kg=84.0))
    db.add(Weight(user_id=user.id, date=today, kg=83.4))
    db.commit()
    page = client.get("/peso").text
    assert 'data-mascot="happy"' in page and 'data-test="weight-delta">-1.6<' in page and ("1.6 kg in meno" in page or "Meno 1.6 kg" in page)
    assert 'class="valore-punto"' in page and page.count('class="valore-punto"') == 2


def test_weight_up_and_none(client, db, user):
    from app.routers.weights import weight_summary

    today = date.today()
    assert weight_summary([], today, user)["mascot"] == "sleepy"
    rows = [Weight(user_id=user.id, date=today, kg=86.0), Weight(user_id=user.id, date=today - timedelta(days=10), kg=85.0)]
    s = weight_summary(rows, today, user)
    assert s["mascot"] == "sweaty" and "1.0" in s["line"]
    rows = [Weight(user_id=user.id, date=today - timedelta(days=9), kg=84.0), Weight(user_id=user.id, date=today - timedelta(days=10), kg=85.0)]
    s = weight_summary(rows, today, user)
    assert s["mascot"] == "sleepy" and "9 giorni" in s["line"]
    rows = [Weight(user_id=user.id, date=today, kg=79.9), Weight(user_id=user.id, date=today - timedelta(days=10), kg=85.0)]
    assert weight_summary(rows, today, user)["mascot"] == "party"
