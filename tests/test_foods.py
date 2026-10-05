"""The food table: import of the Swiss + Italian extras, and the search."""

import pytest
from sqlalchemy import func, select

from app.models import Food
from app.textsearch import normalize, query_words, search_key
from scripts.import_foods import FILES, import_foods


def test_normalize_and_search_key():
    assert normalize("Caffè, nero (non zuccherato)") == "caffe nero non zuccherato"
    assert search_key("Mela, cruda", None) == " mela cruda "
    assert search_key("Orata, cruda", "orata d'allevamento") == " orata cruda orata d allevamento "
    assert query_words("  Petto  POLLO ") == ["petto", "pollo"]


@pytest.fixture
def foods(db):
    report = import_foods(db, FILES)
    return report


def test_import_counts_and_idempotence(db, foods):
    assert foods.imported == 1216 + 37 and foods.updated == 0
    assert db.scalar(select(func.count()).select_from(Food)) == 1253
    mela = db.scalar(select(Food).where(Food.source == "swiss", Food.source_id == "378"))
    assert mela.name == "Mela, cruda" and mela.kcal == 52 and mela.category == "Frutta/Frutta fresca"
    orata = db.scalar(select(Food).where(Food.source == "extra", Food.source_id == "E001"))
    assert orata.name == "Orata, cruda" and orata.protein_g == 19.8

    again = import_foods(db, FILES)
    assert again.imported == 0 and again.updated == 1253
    assert db.scalar(select(func.count()).select_from(Food)) == 1253


def _names(client, q):
    r = client.get("/alimenti/cerca", params={"q": q})
    assert r.status_code == 200
    return [line.split("</span>")[0] for line in r.text.split('<span class="nome">')[1:]]


def test_search_everyday_foods(client, foods):
    assert _names(client, "mela")[0] == "Mela, cruda"
    assert "Melanzana, cruda" in _names(client, "mela")  # word prefix still matches
    assert _names(client, "pesca")[:2] == ["Pesca noce, cruda", "Pesca, gialla, cruda"]
    names = _names(client, "petto pollo")  # any order
    assert "Pollo, petto senza pelle, crudo" in names[:3]
    assert _names(client, "pollo petto") == names


def test_search_is_word_prefix_and_accent_insensitive(client, foods):
    assert all(n.startswith("Orata") for n in _names(client, "orata"))  # not "cola edulcorata"
    assert _names(client, "caffe") == _names(client, "caffè")
    assert "Caffè, nero, non zuccherato" in _names(client, "caffe nero")
    assert _names(client, "p") == []  # too short


def test_basic_foods_before_prepared_dishes(client, foods):
    names = _names(client, "uovo")
    assert names.index("Uovo di gallina, intero, crudo") < names.index("Uovo strapazzato, preparato")
    assert "Lattuga romana, cruda" in _names(client, "lattuga")[:3]


def test_custom_foods_first_and_searchable_by_accent_free_words(client, db, user, foods):
    r = client.post("/alimenti", data={"name": "Pasta e ceci della nonna", "kcal": 150, "protein_g": 6, "carbs_g": 22, "fat_g": 4}, follow_redirects=False)
    assert r.status_code == 303
    assert _names(client, "ceci nonna") == ["Pasta e ceci della nonna"]
    assert _names(client, "ceci")[0] == "Pasta e ceci della nonna"
