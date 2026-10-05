# Italian names for the USDA foods

`data/foods_it.csv` (fdc_id, name_it) gives every imported USDA food an Italian name.
It is built, not typed: `python scripts/build_foods_it.py` regenerates it from the files here.

USDA names are comma-separated attributes, e.g. `Pasta, cooked, enriched, without added salt`.
The builder splits each name (keeping parentheses together), looks every attribute up in the
dictionary, joins the Italian attributes with ", " and capitalises the first letter.

| File | Role |
| --- | --- |
| `../usda_names.csv` | the English names, exported from the imported `foods` table |
| `tokens_en.tsv` | the 5,118 distinct attributes with their frequency, for reference |
| `tokens_01.tsv` … `tokens_07.tsv` | the dictionary: `english<TAB>italian`, `=` keeps the English (brand names) |
| `pairs.tsv` | `head<TAB>attribute<TAB>italian`, for attributes whose meaning depends on the head word (`Beans, kidney`) |
| `names.csv` | optional full-name overrides, `fdc_id,name_it`; wins over the dictionary |
| `untranslated.tsv` | written by the builder: attributes with no dictionary entry (should be empty) |

Known roughness, accepted for now: adjectives do not agree in gender and number with the head
word ("Cipolle, surgelato"), and US meat cuts are rendered with the nearest Italian cut name
(chuck → reale, round → coscia, top round → fesa, bottom round → sottofesa, eye of round →
girello, top sirloin → scamone, rib eye → entrecôte, top loin → controfiletto).

To correct a translation: edit the dictionary line (or add a `names.csv` row for one food),
rebuild, then re-run `scripts/import_usda.py` on the USDA download to update `foods.name_it`.
