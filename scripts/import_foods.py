"""Load the generic foods into the `foods` table.

Usage: python scripts/import_foods.py

Reads data/foods_swiss_it.csv (Banca dati svizzera dei valori nutritivi,
Italian edition, generic foods, extracted by scripts/extract_swiss.py) and
data/foods_extra_it.csv (Italian staples the Swiss list lacks). Idempotent:
rows are matched on (source, source_id) and updated in place. Users' custom
foods are never touched.
"""

import csv
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import Food
from app.textsearch import search_key

DATA = Path(__file__).resolve().parent.parent / "data"
FILES = {"swiss": DATA / "foods_swiss_it.csv", "extra": DATA / "foods_extra_it.csv"}


@dataclass
class ImportReport:
    imported: int = 0
    updated: int = 0


def read_rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def import_foods(db: Session, files: dict[str, Path] = FILES) -> ImportReport:
    report = ImportReport()
    existing = {
        (f.source, f.source_id): f
        for f in db.scalars(select(Food).where(Food.source.in_(list(files))))
    }
    for source, path in files.items():
        for r in read_rows(path):
            values = dict(
                name=r["name"].strip(),
                synonyms=(r.get("synonyms") or "").strip() or None,
                category=(r.get("category") or "").strip() or None,
                kcal=float(r["kcal"]),
                protein_g=float(r["protein_g"]),
                carbs_g=float(r["carbs_g"]),
                fat_g=float(r["fat_g"]),
            )
            values["search_key"] = search_key(values["name"], values["synonyms"])
            food = existing.get((source, str(r["id"])))
            if food is None:
                food = Food(source=source, source_id=str(r["id"]), **values)
                db.add(food)
                existing[(source, str(r["id"]))] = food
                report.imported += 1
            else:
                for k, v in values.items():
                    setattr(food, k, v)
                report.updated += 1
    db.commit()
    return report


if __name__ == "__main__":
    with Session(engine) as session:
        rep = import_foods(session)
    print(f"Alimenti importati: {rep.imported}, aggiornati: {rep.updated}")
