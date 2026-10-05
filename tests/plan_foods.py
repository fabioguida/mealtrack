"""Load into the test database only the foods that data/template_dishes.json
references, taken from the real CSVs in data/, so the planner tests run on the
same numbers as the app."""

import csv
import json
from pathlib import Path

from app.models import Food
from app.textsearch import search_key

DATA = Path(__file__).resolve().parent.parent / "data"
FILES = {"swiss": DATA / "foods_swiss_it.csv", "extra": DATA / "foods_extra_it.csv"}


def load_plan_foods(db):
    dishes = json.loads((DATA / "template_dishes.json").read_text(encoding="utf-8"))["dishes"]
    wanted = {(i["source"], str(i["id"])) for d in dishes for i in d["ingredients"]}
    rows = []
    for source, path in FILES.items():
        with open(path, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if (source, str(r["id"])) in wanted:
                    rows.append(Food(
                        source=source, source_id=str(r["id"]), name=r["name"],
                        synonyms=r.get("synonyms") or None, category=r.get("category") or None,
                        search_key=search_key(r["name"], r.get("synonyms")),
                        kcal=float(r["kcal"]), protein_g=float(r["protein_g"]),
                        carbs_g=float(r["carbs_g"]), fat_g=float(r["fat_g"]),
                    ))
    assert len(rows) == len(wanted), f"missing foods: {wanted - {(r.source, r.source_id) for r in rows}}"
    db.add_all(rows)
    db.commit()
    return rows
