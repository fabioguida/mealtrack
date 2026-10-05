"""Meal photos with a fake analyzer: upload, candidates, attachment, privacy."""

import io

import pytest
from PIL import Image
from sqlalchemy import select

from app import config
from app.main import app
from app.models import Meal
from app.photos.analyzer import Candidate, FakeAnalyzer, clean_label
from app.routers.photos import analyzer_dep
from tests.conftest import login_client, make_user


def png_bytes(size=(64, 48), color=(200, 40, 40)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, "PNG")
    return out.getvalue()


@pytest.fixture
def photo_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PHOTO_DIR", tmp_path / "photos")
    return tmp_path / "photos"


@pytest.fixture
def fake(pasta):
    cands = [Candidate("food", str(pasta.id), pasta.name, 0.31), Candidate("recipe", "pasta-pomodoro", "Pasta al pomodoro", 0.28)]
    app.dependency_overrides[analyzer_dep] = lambda: FakeAnalyzer(cands)
    yield cands
    app.dependency_overrides.pop(analyzer_dep, None)


def test_clean_label():
    assert clean_label("Pollo, petto senza pelle, crudo") == "pollo, petto senza pelle"
    assert clean_label("Pasta, cotta in acqua salata (sale non iodato)") == "pasta, cotta in acqua salata"
    assert clean_label("Mela, cruda") == "mela, cruda"


def test_upload_gives_candidates_and_stores_the_photo(client, user, pasta, fake, photo_dir):
    r = client.post("/foto/analizza", files={"foto": ("piatto.png", png_bytes(), "image/png")})
    assert r.status_code == 200
    assert r.text.count('data-test="candidate"') == 2
    assert f'hx-get="/pasti/riga?food_id={pasta.id}"' in r.text
    assert 'hx-get="/pasti/righe?piatto=pasta-pomodoro"' in r.text
    assert 'id="photo_url"' in r.text and 'hx-swap-oob="true"' in r.text
    url = r.text.split('name="photo_url" id="photo_url" value="')[1].split('"')[0]
    assert url.startswith(f"/foto/{user.id}/") and url.endswith(".jpg")
    stored = list((photo_dir / str(user.id)).glob("*.jpg"))
    assert len(stored) == 1
    assert Image.open(stored[0]).format == "JPEG"

    # The photo is served to its owner only.
    assert client.get(url).status_code == 200
    assert client.get(url).headers["content-type"] == "image/jpeg"
    assert client.get(f"/foto/{user.id}/nope.jpg").status_code == 404


def test_photo_is_resized(client, user, fake, photo_dir, monkeypatch):
    monkeypatch.setattr(config, "PHOTO_MAX_PX", 100)
    client.post("/foto/analizza", files={"foto": ("big.png", png_bytes((800, 400)), "image/png")})
    stored = next((photo_dir / str(user.id)).glob("*.jpg"))
    assert Image.open(stored).size == (100, 50)


def test_not_an_image(client, user, fake, photo_dir):
    r = client.post("/foto/analizza", files={"foto": ("x.txt", b"not an image", "text/plain")})
    assert r.status_code == 422


def test_meal_keeps_the_photo_and_shows_it(client, db, user, pasta, fake, photo_dir):
    r = client.post("/foto/analizza", files={"foto": ("piatto.png", png_bytes(), "image/png")})
    url = r.text.split('name="photo_url" id="photo_url" value="')[1].split('"')[0]
    r = client.post("/pasti", data={"when": "2026-10-05T13:30", "meal_type": "pranzo", "food_id": [pasta.id], "grams": [140], "photo_url": url}, follow_redirects=False)
    assert r.status_code == 303
    meal = db.scalar(select(Meal).where(Meal.user_id == user.id))
    assert meal.photo_url == url and meal.input_method == "photo"
    assert f'src="{url}"' in client.get(f"/pasti/{meal.id}").text
    assert f'<img class="foto" src="{url}"' in client.get("/giorno/2026-10-05").text
    # Editing keeps it; a foreign or forged URL is dropped.
    client.post(f"/pasti/{meal.id}", data={"when": "2026-10-05T13:30", "meal_type": "pranzo", "food_id": [pasta.id], "grams": [150], "photo_url": url})
    db.expire_all()
    assert db.get(Meal, meal.id).photo_url == url
    client.post(f"/pasti/{meal.id}", data={"when": "2026-10-05T13:30", "meal_type": "pranzo", "food_id": [pasta.id], "grams": [150], "photo_url": "/foto/999/x.jpg"})
    db.expire_all()
    assert db.get(Meal, meal.id).photo_url is None


def test_photos_are_private(db, pasta, fake, photo_dir):
    a = make_user(db, "a@example.com")
    b = make_user(db, "b@example.com")
    ca, cb = login_client(db, a), login_client(db, b)
    try:
        r = ca.post("/foto/analizza", files={"foto": ("piatto.png", png_bytes(), "image/png")})
        url = r.text.split('name="photo_url" id="photo_url" value="')[1].split('"')[0]
        assert ca.get(url).status_code == 200
        assert cb.get(url).status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_without_analyzer_the_photo_is_still_attached(client, user, photo_dir):
    app.dependency_overrides[analyzer_dep] = lambda: None
    try:
        r = client.post("/foto/analizza", files={"foto": ("piatto.png", png_bytes(), "image/png")})
        assert r.status_code == 200 and 'data-test="photo-error"' in r.text and 'id="photo_url"' in r.text
    finally:
        app.dependency_overrides.pop(analyzer_dep, None)


def test_form_shows_the_camera_button(client):
    assert 'hx-post="/foto/analizza"' in client.get("/pasti/nuovo").text
