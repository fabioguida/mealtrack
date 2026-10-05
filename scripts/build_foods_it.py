"""Build data/foods_it.csv (fdc_id, name_it) from the reviewed Italian dictionary.

Usage: python scripts/build_foods_it.py

Inputs, all under data/foods_it/:
- names.csv        full-name overrides, columns fdc_id,name_it (wins over the dictionary)
- tokens_*.tsv     attribute dictionary, one `english<TAB>italian` per line;
                   `=` as the Italian keeps the English (brand names); `#` starts a comment
- ../usda_names.csv the English names exported from the imported foods (fdc_id,name)

USDA names are comma-separated attributes ("Pasta, cooked, enriched, without
added salt"). Each attribute is looked up case-insensitively; parentheses are
kept together before the lookup. Untranslated attributes stay in English and
are listed in data/foods_it/untranslated.tsv with their frequency.
"""

import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DICT_DIR = DATA / "foods_it"


def split_attrs(name: str) -> list[str]:
    """Split on commas that are not inside parentheses."""
    parts, depth, cur = [], 0, []
    for ch in name:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur).strip())
    return [p for p in parts if p]


def load_dictionary() -> dict[str, str]:
    table: dict[str, str] = {}
    for path in sorted(DICT_DIR.glob("tokens_*.tsv")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.startswith("#"):
                continue
            if "\t" not in line:
                sys.exit(f"{path.name}: missing tab in line: {line!r}")
            en, it = line.split("\t", 1)
            en, it = en.strip(), it.strip()
            table[en.lower()] = en if it == "=" else it
    return table


def load_pairs() -> dict[tuple[str, str], str]:
    """pairs.tsv: `head<TAB>attribute<TAB>italian` for attributes whose meaning
    depends on the food's head word (e.g. Beans, kidney → rossi)."""
    path = DICT_DIR / "pairs.tsv"
    table: dict[tuple[str, str], str] = {}
    if not path.is_file():
        return table
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        head, attr, it = (s.strip() for s in line.split("\t", 2))
        table[(head.lower(), attr.lower())] = it
    return table


def load_overrides() -> dict[int, str]:
    path = DICT_DIR / "names.csv"
    if not path.is_file():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {int(r["fdc_id"]): r["name_it"].strip() for r in csv.DictReader(f) if r["name_it"].strip()}


def translate(
    name: str, table: dict[str, str], pairs: dict[tuple[str, str], str], missing: Counter
) -> str:
    out = []
    attrs = split_attrs(name)
    head = attrs[0].lower() if attrs else ""
    for i, attr in enumerate(attrs):
        it = pairs.get((head, attr.lower())) if i > 0 else None
        if it is None:
            it = table.get(attr.lower())
        if it is None:
            # Retry with inner spacing normalised, e.g. double spaces in the source.
            it = table.get(re.sub(r"\s+", " ", attr).lower())
        if it is None:
            missing[attr] += 1
            it = attr
        elif i > 0 and attr[:1].islower() and it[:2].isupper() is False:
            # Dictionary heads are capitalised ("Spinaci"); mid-name they are not.
            it = it[:1].lower() + it[1:]
        out.append(it)
    text = ", ".join(out)
    return text[:1].upper() + text[1:]


def main() -> None:
    table = load_dictionary()
    pairs = load_pairs()
    overrides = load_overrides()
    missing: Counter = Counter()
    rows_out, n_override = [], 0
    with open(DATA / "usda_names.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            fdc_id = int(r["fdc_id"])
            if fdc_id in overrides:
                rows_out.append((fdc_id, overrides[fdc_id]))
                n_override += 1
            else:
                rows_out.append((fdc_id, translate(r["name"], table, pairs, missing)))

    with open(DATA / "foods_it.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fdc_id", "name_it"])
        w.writerows(rows_out)
    with open(DICT_DIR / "untranslated.tsv", "w", encoding="utf-8") as f:
        for attr, n in missing.most_common():
            f.write(f"{n}\t{attr}\n")

    n_names_missing = sum(missing.values())
    print(
        f"Nomi: {len(rows_out)}, da override: {n_override}, voci dizionario: {len(table)}, "
        f"attributi non tradotti: {len(missing)} distinti / {n_names_missing} occorrenze"
    )


if __name__ == "__main__":
    main()
