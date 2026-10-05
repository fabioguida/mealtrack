"""The hand-on-the-plate portion estimate: geometry, grams, the household measures, the flow."""

import io

import numpy as np
import pytest
from PIL import Image

from app import config
from app.main import app
from app.measures import measures_for
from app.photos import portion as P
from app.routers.photos import estimator_dep


def synthetic_plate(food_rx=120, food_ry=90, plate_r=250, size=(800, 600)):
    import cv2

    img = np.full((size[1], size[0], 3), (120, 110, 100), np.uint8)   # table
    cv2.circle(img, (size[0] // 2, size[1] // 2), plate_r, (245, 245, 240), -1)
    cv2.ellipse(img, (size[0] // 2 - 70, size[1] // 2), (food_rx, food_ry), 0, 0, 360, (200, 60, 40), -1)
    return img


def test_hand_breadth_from_sex_and_height():
    assert P.hand_breadth_cm("M", 176) == pytest.approx(8.7, abs=0.1)
    assert P.hand_breadth_cm("F", 163) == pytest.approx(7.7, abs=0.1)
    assert P.hand_breadth_cm("m", 180) > P.hand_breadth_cm("f", 180)


def test_plate_and_food_area_on_a_synthetic_plate():
    img = synthetic_plate()
    plate, found = P.plate_mask(img)
    assert found
    assert plate.sum() == pytest.approx(np.pi * 250 ** 2, rel=0.02)
    food = P.food_mask(img, plate, None)
    assert food.sum() == pytest.approx(np.pi * 120 * 90, rel=0.03)
    # Without a plate-like region the whole image is used and the flag says so.
    _, found = P.plate_mask(np.zeros((100, 100, 3), np.uint8))
    assert not found


def test_hand_region_is_excluded_from_the_food():
    img = synthetic_plate()
    plate, _ = P.plate_mask(img)
    whole = P.food_mask(img, plate, None).sum()
    hull = np.array([[300, 220], [380, 220], [380, 380], [300, 380]])  # covers part of the food
    cut = P.food_mask(img, plate, hull).sum()
    assert cut < whole


def test_grams_from_area_and_density_keys():
    g = P.grams_from_area(180.0)
    assert g["pasta"] == (125, 180, 235)
    assert g["insalata"][1] == 35 and g["pizza"][1] == 100
    assert P.density_key("Pasta, cotta in acqua salata", "Prodotti a base di cereali, legumi e patate/Pasta") == "pasta"
    assert P.density_key("Lattuga romana, cruda", "Verdure/Verdure fresche") == "insalata"
    assert P.density_key("Pollo, petto senza pelle, crudo", "Carne e frattaglie/Pollame") == "carne"
    assert P.density_key("Zucchina, stufata", "Verdure/Verdure cotte (incl. conserve)") == "verdure cotte"
    assert P.density_key("Pizza margherita", None) == "pizza"
    assert P.density_key("Cosa strana", None) == "default"


def test_estimate_with_an_injected_hand(monkeypatch):
    img = synthetic_plate()
    hull = np.array([[560, 200], [700, 200], [700, 420], [560, 420]])
    # A 26 cm plate spanning 500 px → 0.052 cm/px, as a hand of that scale would give.
    monkeypatch.setattr(P, "detect_hand", lambda rgb, breadth_cm: P.HandScale(26 / 500, 170.0, hull))
    est = P.estimate_portion(img, "M", 180)
    assert est is not None and est.plate_found
    assert est.area_cm2 == pytest.approx(np.pi * 120 * 90 * (26 / 500) ** 2, rel=0.03)
    lo, mid, hi = est.for_type("pasta")
    assert lo < mid < hi and mid == pytest.approx(est.area_cm2 * 1.0, abs=5)
    monkeypatch.setattr(P, "detect_hand", lambda rgb, breadth_cm: None)
    assert P.estimate_portion(img, "M", 180) is None


def test_household_measures():
    assert measures_for("Pasta, cotta in acqua salata (sale non iodato)", "spaghetti; penne; pasta cotta", None)[1] == ("piatto medio", 180)
    assert measures_for("Olio d'oliva", None, "Grassi e oli/Oli") == [("cucchiaino", 5), ("cucchiaio", 10)]
    assert measures_for("Uovo di gallina, intero, crudo", "uovo intero; uova", "Uova")[0] == ("1 uovo", 55)
    assert measures_for("Mela, cruda", "mele", "Frutta/Frutta fresca")[1] == ("media", 180)
    assert measures_for("Agar Agar", None, "Diversi") == []


def test_measure_chips_in_item_rows(client, db, pasta, oil):
    from tests.conftest import make_food

    olio = make_food(db, "Olio d'oliva", 900, 0, 0, 100, source_id="591")
    row = client.get("/pasti/riga", params={"food_id": olio.id}).text
    assert 'data-test="measures"' in row and 'data-grams="10"' in row and "cucchiaio 10 g" in row
    # English fixture names have no Italian measure: no chips, no error.
    assert 'data-test="measures"' not in client.get("/pasti/riga", params={"food_id": oil.id}).text


def png(size=(64, 48)):
    out = io.BytesIO()
    Image.new("RGB", size, (200, 40, 40)).save(out, "PNG")
    return out.getvalue()


@pytest.fixture
def photo_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PHOTO_DIR", tmp_path / "photos")
    return tmp_path / "photos"


def test_upload_shows_the_estimate_chips(client, user, photo_dir):
    est = P.PortionEstimate(0.05, 180.0, True, P.grams_from_area(180.0))
    app.dependency_overrides[estimator_dep] = lambda: (lambda rgb, sex, h: est)
    try:
        r = client.post("/foto/analizza", files={"foto": ("piatto.png", png(), "image/png")})
        assert r.status_code == 200
        assert 'data-test="estimate"' in r.text
        assert "Pasta o riso: 180 g" in r.text and "(125–235)" in r.text
        assert r.text.count('data-test="estimate-chip"') == 7
        assert 'id="photo_url"' in r.text
    finally:
        app.dependency_overrides.pop(estimator_dep, None)


def test_upload_without_a_hand_shows_the_howto(client, user, photo_dir):
    app.dependency_overrides[estimator_dep] = lambda: (lambda rgb, sex, h: None)
    try:
        r = client.post("/foto/analizza", files={"foto": ("piatto.png", png(), "image/png")})
        assert 'data-test="no-hand"' in r.text and 'data-test="howto"' in r.text
    finally:
        app.dependency_overrides.pop(estimator_dep, None)


def test_estimate_needs_a_profile(db, photo_dir):
    from tests.conftest import login_client, make_user

    u = make_user(db, "np@example.com", with_profile=False)
    c = login_client(db, u)
    app.dependency_overrides[estimator_dep] = lambda: (lambda rgb, sex, h: None)
    try:
        r = c.post("/foto/analizza", files={"foto": ("piatto.png", png(), "image/png")})
        assert r.status_code == 200 and "Compila il profilo" in r.text
    finally:
        app.dependency_overrides.clear()


def test_form_has_the_howto(client):
    assert 'data-test="howto"' in client.get("/pasti/nuovo").text
