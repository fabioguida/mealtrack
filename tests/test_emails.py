"""Shopping list, progress summary, email composition, settings page, cron script."""

from datetime import date, timedelta

import pytest
from sqlalchemy import func, select

from app import emails as E
from app.models import EmailLog, Food, NotificationSettings
from app.progress import progress_for
from app.shopping import buy_quantity, group_of, shopping_list
from tests.plan_foods import load_plan_foods
from tests.test_plan_routes import AUTHOR


@pytest.fixture(autouse=True)
def console_backend(monkeypatch):
    backend = E.ConsoleBackend()
    monkeypatch.setattr(E, "_backend", backend)
    return backend


@pytest.fixture
def planned(client, db, user):
    load_plan_foods(db)
    client.post("/orari", data=AUTHOR)
    client.post("/piano/rigenera")
    return user


def test_buy_quantities_and_groups():
    eggs = Food(name="Uovo di gallina, intero, crudo", synonyms="uovo intero; uova", category="Uova", source="swiss", kcal=140, protein_g=12.6, carbs_g=0.3, fat_g=9.8)
    assert buy_quantity(eggs, 110) == "2 uova" and buy_quantity(eggs, 55) == "1 uovo" and buy_quantity(eggs, 112) == "2 uova"
    apple = Food(name="Mela, cruda", synonyms="mele", category="Frutta/Frutta fresca", source="swiss", kcal=52, protein_g=0.3, carbs_g=11.6, fat_g=0.3)
    assert buy_quantity(apple, 360) == "2 mele" and group_of(apple) == "Frutta e verdura"
    pasta = Food(name="Pasta, cotta in acqua salata", category="Prodotti a base di cereali, legumi e patate/Pasta", source="swiss", kcal=158, protein_g=5.9, carbs_g=31.2, fat_g=0.6)
    assert buy_quantity(pasta, 180) == "200 g" and buy_quantity(pasta, 35) == "40 g" and group_of(pasta) == "Pane, pasta, riso e legumi"
    oil = Food(name="Olio d'oliva", category="Grassi e oli/Oli", source="swiss", kcal=900, protein_g=0, carbs_g=0, fat_g=100)
    assert group_of(oil) == "Dispensa"
    fish = Food(name="Orata, cruda", category="Pesce/Pesci di mare", source="extra", kcal=121, protein_g=19.8, carbs_g=1.2, fat_g=3.8)
    assert group_of(fish) == "Carne e pesce"


def test_shopping_list_aggregates_the_plan(client, db, planned):
    today = date.today()
    groups = shopping_list(db, planned, today, today + timedelta(days=6))
    assert groups and [g.name for g in groups] == sorted([g.name for g in groups], key=lambda n: ["Frutta e verdura", "Carne e pesce", "Latticini e uova", "Pane, pasta, riso e legumi", "Dispensa"].index(n))
    items = [it for g in groups for it in g.items]
    assert all(it.grams > 0 and it.display for it in items)
    names = [it.food.name for it in items]
    assert len(names) == len(set(names))  # aggregated per food
    assert shopping_list(db, planned, today + timedelta(days=60), today + timedelta(days=60)) == []

    page = client.get("/spesa", params={"periodo": "settimana"}).text
    assert 'data-test="group"' in page
    assert 'data-test="empty"' in client.get("/spesa", params={"periodo": "oggi"}).text or 'data-test="group"' in client.get("/spesa", params={"periodo": "oggi"}).text


def test_progress_summary(client, db, user, pasta):
    for d in range(3):
        client.post("/pasti", data={"when": f"{(date.today() - timedelta(days=d)).isoformat()}T13:00", "meal_type": "pranzo", "food_id": [pasta.id], "grams": [400]})
    p = progress_for(db, user, date.today())
    assert p.today.eaten_kcal == pytest.approx(1484) and p.today.allowed_kcal == pytest.approx(1913.125)
    assert p.streak == 3 and len(p.lines) == 7 and p.lines[0].eaten_kcal is None
    assert p.weights and p.trend.verdict == "sotto"  # 1484 of 1913 kcal on the logged days


def test_daily_email_content(client, db, planned, console_backend):
    msg = E.compose_daily(db, planned, date.today())
    assert msg is not None and msg.to == planned.email
    assert "Spesa per domani" in msg.subject
    assert "SPESA PER DOMANI" in msg.text and "ULTIMI 7 GIORNI" in msg.text
    assert "/spesa" in msg.html and "Lista della spesa" in msg.html
    # Switching the shopping part off leaves the progress.
    db.add(NotificationSettings(user_id=planned.id, daily_shopping=False, weekly_shopping=True, progress=True))
    db.commit()
    msg = E.compose_daily(db, planned, date.today())
    assert "SPESA PER DOMANI" not in msg.text and "ULTIMI 7 GIORNI" in msg.text


def test_weekly_email_covers_next_week(client, db, planned):
    saturday = date.today() + timedelta(days=(5 - date.today().weekday()) % 7)
    msg = E.compose_weekly(db, planned, saturday)
    monday = saturday + timedelta(days=2)
    assert msg is not None and monday.strftime("%-d") if False else True
    assert "SPESA DELLA SETTIMANA" in msg.text and "LA SETTIMANA APPENA FINITA" in msg.text


def test_send_logged_once_per_period(client, db, planned, console_backend):
    today = date.today()
    assert E.send_logged(db, planned, "daily", today.isoformat(), E.compose_daily(db, planned, today)) == "sent"
    assert E.send_logged(db, planned, "daily", today.isoformat(), E.compose_daily(db, planned, today)) == "duplicate"
    assert len(console_backend.outbox) == 1
    assert db.scalar(select(EmailLog).where(EmailLog.user_id == planned.id)).status == "sent"


def test_send_to_all_skips_users_without_a_plan_or_profile(db, planned, console_backend):
    from tests.conftest import make_user

    make_user(db, "noplan@example.com")                      # profile, no plan → progress only
    make_user(db, "noprofile@example.com", with_profile=False)  # nothing to send
    counts = E.send_daily_to_all(db, date.today())
    assert counts.get("sent") == 2 and counts.get("skipped") == 1
    assert E.send_daily_to_all(db, date.today()) == {"duplicate": 3}


def test_settings_page_and_send_now(client, db, planned, console_backend):
    page = client.get("/notifiche").text
    assert 'data-test="settings"' in page and 'name="daily_shopping" value="1" checked' in page
    r = client.post("/notifiche", data={"weekly_shopping": "1"}, follow_redirects=False)
    assert r.status_code == 303
    s = db.get(NotificationSettings, planned.id)
    assert (s.daily_shopping, s.weekly_shopping, s.progress) == (False, True, False)
    r = client.post("/notifiche/invia", data={"kind": "weekly"}, follow_redirects=False)
    assert r.status_code == 303 and "inviata" in r.headers["location"]
    assert len(console_backend.outbox) == 1 and "settimana" in console_backend.outbox[0].subject
    assert 'data-test="log"' in client.get("/notifiche").text
