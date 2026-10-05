"""Import USDA FoodData Central foods into the `foods` table.

Usage: python scripts/import_usda.py <dir> [<dir> ...]

Each directory is an unzipped FoodData Central CSV download (SR Legacy or
Foundation Foods) containing `food.csv` and `food_nutrient.csv`. Only rows
with data_type `sr_legacy_food` or `foundation_food` are imported; Branded
foods are skipped. Re-running updates rows by `usda_fdc_id` (idempotent).

Nutrient ids: 1008 energy kcal, 1003 protein, 1004 total fat,
1005 carbohydrate by difference. Foods without 1008 fall back to 2047
(Atwater general factors); without either they are skipped and counted.
"""

import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import engine
from app.models import Food

DATA_TYPES = {"sr_legacy_food", "foundation_food"}
N_KCAL, N_PROTEIN, N_FAT, N_CARBS, N_ATWATER = 1008, 1003, 1004, 1005, 2047


@dataclass
class ImportReport:
    imported: int = 0
    updated: int = 0
    skipped_no_energy: int = 0


def read_usda_dir(directory: Path) -> dict[int, dict]:
    """Return {fdc_id: {name, kcal, protein_g, carbs_g, fat_g}} for one download."""
    foods: dict[int, str] = {}
    with open(directory / "food.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["data_type"] in DATA_TYPES:
                foods[int(row["fdc_id"])] = row["description"]

    nutrients: dict[int, dict[int, float]] = defaultdict(dict)
    with open(directory / "food_nutrient.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fdc_id = int(row["fdc_id"])
            if fdc_id not in foods:
                continue
            nutrient_id = int(row["nutrient_id"])
            if nutrient_id in (N_KCAL, N_PROTEIN, N_FAT, N_CARBS, N_ATWATER):
                nutrients[fdc_id][nutrient_id] = float(row["amount"] or 0)

    result = {}
    for fdc_id, name in foods.items():
        n = nutrients.get(fdc_id, {})
        kcal = n.get(N_KCAL, n.get(N_ATWATER))
        if kcal is None:
            result[fdc_id] = None  # marks "skipped: no energy value"
            continue
        result[fdc_id] = {
            "name": name,
            "kcal": kcal,
            "protein_g": n.get(N_PROTEIN, 0.0),
            "carbs_g": n.get(N_CARBS, 0.0),
            "fat_g": n.get(N_FAT, 0.0),
        }
    return result


def import_usda(db: Session, directories: list[Path]) -> ImportReport:
    report = ImportReport()
    existing = {
        f.usda_fdc_id: f
        for f in db.scalars(select(Food).where(Food.source == "usda"))
    }
    for directory in directories:
        for fdc_id, values in read_usda_dir(directory).items():
            if values is None:
                report.skipped_no_energy += 1
                continue
            food = existing.get(fdc_id)
            if food is None:
                food = Food(source="usda", usda_fdc_id=fdc_id, **values)
                db.add(food)
                existing[fdc_id] = food
                report.imported += 1
            else:
                for key, value in values.items():
                    setattr(food, key, value)
                report.updated += 1
    db.commit()
    return report


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    dirs = [Path(a) for a in sys.argv[1:]]
    with Session(engine) as session:
        r = import_usda(session, dirs)
    print(
        f"Alimenti importati: {r.imported}, aggiornati: {r.updated}, "
        f"saltati senza energia: {r.skipped_no_energy}"
    )
