from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models import Food
from scripts.import_usda import import_usda

FIXTURE = Path(__file__).parent / "fixtures" / "usda"


def test_import_fixture(db):
    report = import_usda(db, [FIXTURE])

    # 20 rows in food.csv: 1 branded (ignored), 1 without energy (skipped) → 18.
    assert report.imported == 18
    assert report.updated == 0
    assert report.skipped_no_energy == 1
    assert db.scalar(select(func.count()).select_from(Food)) == 18

    pasta = db.scalar(select(Food).where(Food.usda_fdc_id == 170148))
    assert pasta.name == "Pasta, cooked, enriched, without added salt"
    assert pasta.source == "usda"
    assert pasta.kcal == pytest.approx(158)
    assert pasta.protein_g == pytest.approx(5.8)
    assert pasta.carbs_g == pytest.approx(30.9)
    assert pasta.fat_g == pytest.approx(0.93)

    # Foundation food without 1008 falls back to Atwater (2047).
    tomato = db.scalar(select(Food).where(Food.usda_fdc_id == 2346384))
    assert tomato.kcal == pytest.approx(27)

    assert db.scalar(select(Food).where(Food.usda_fdc_id == 2000001)) is None
    assert db.scalar(select(Food).where(Food.usda_fdc_id == 2346386)) is None


def test_import_is_idempotent(db):
    import_usda(db, [FIXTURE])
    report = import_usda(db, [FIXTURE])

    assert report.imported == 0
    assert report.updated == 18
    assert db.scalar(select(func.count()).select_from(Food)) == 18
