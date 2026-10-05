"""Extract the generic foods of the Swiss Food Composition Database (Italian
edition) into data/foods_swiss_it.csv.

Usage: python scripts/extract_swiss.py <Banca_dati_svizzera_dei_valori_nutritivi.xlsx>

Source: Ufficio federale della sicurezza alimentare e di veterinaria (USAV),
Banca dati svizzera dei valori nutritivi, https://naehrwertdaten.ch/it/ —
free use, including in nutrition diary apps, with acknowledgement of the
source. Only the "Alimenti generici" sheet is taken; branded foods are not.
Values are per 100 g of edible portion. Carbohydrates are the "available"
ones (sugars + starch), the right basis for kcal accounting.
"""

import csv
import sys
from pathlib import Path

import openpyxl

OUT = Path(__file__).resolve().parent.parent / "data" / "foods_swiss_it.csv"
COLS = {"id": "ID", "name": "Nome", "synonyms": "Sinonimi", "category": "Categoria",
        "kcal": "Energia, kilocalorie (kcal)", "fat_g": "Lipidi, totali (g)",
        "carbs_g": "Glucidi, disponibili (g)", "protein_g": "Proteine (g)"}


def num(v) -> float:
    """'tr.' (traces) and blanks count as 0; '<0.5' style values as their bound."""
    if v is None:
        return 0.0
    s = str(v).strip().replace(",", ".")
    if s in ("", "tr.", "n.d.", "-"):
        return 0.0
    return float(s.lstrip("<"))


def main(xlsx: Path) -> None:
    ws = openpyxl.load_workbook(xlsx, read_only=True)["Alimenti generici"]
    rows = ws.iter_rows(values_only=True)
    next(rows); next(rows)
    header = [str(h).strip() if h else "" for h in next(rows)]
    idx = {k: header.index(v) for k, v in COLS.items()}
    out = []
    for r in rows:
        if not r[idx["id"]]:
            continue
        out.append({
            "id": int(r[idx["id"]]),
            "name": " ".join(str(r[idx["name"]]).split()),
            "synonyms": " ".join(str(r[idx["synonyms"]] or "").split()),
            "category": str(r[idx["category"]] or "").strip(),
            "kcal": num(r[idx["kcal"]]),
            "protein_g": num(r[idx["protein_g"]]),
            "carbs_g": num(r[idx["carbs_g"]]),
            "fat_g": num(r[idx["fat_g"]]),
        })
    out.sort(key=lambda d: d["id"])
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(COLS))
        w.writeheader()
        w.writerows(out)
    print(f"{len(out)} alimenti generici scritti in {OUT.name}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
