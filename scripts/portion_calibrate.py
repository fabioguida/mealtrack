"""Check the portion estimate against the kitchen scale.

Usage: python scripts/portion_calibrate.py <folder> <sex> <height_cm>

The folder holds the photos (hand flat on the plate, taken from above) and a
`pesi.csv` with columns `file,grams,tipo` where tipo is one of the density
keys (pasta, riso, carne, pesce, legumi, verdure cotte, insalata, pizza, pane,
frutta, default). Prints the estimate next to the truth and the error stats:
this is what decides whether the estimator is good enough.
"""

import csv
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from PIL import Image, ImageOps

from app.photos.portion import estimate_portion

if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    folder, sex, height = Path(sys.argv[1]), sys.argv[2], float(sys.argv[3])
    rows = list(csv.DictReader(open(folder / "pesi.csv", newline="", encoding="utf-8")))
    errors = []
    print(f"{'foto':28s} {'tipo':14s} {'vero':>6s} {'stima':>6s} {'range':>11s} {'err':>6s}")
    for r in rows:
        image = ImageOps.exif_transpose(Image.open(folder / r["file"])).convert("RGB")
        image.thumbnail((1600, 1600))
        est = estimate_portion(np.asarray(image), sex, height)
        truth = float(r["grams"])
        if est is None:
            print(f"{r['file']:28s} {r['tipo']:14s} {truth:6.0f}   mano non trovata")
            continue
        lo, mid, hi = est.for_type(r["tipo"])
        err = (mid - truth) / truth
        errors.append(err)
        flag = "" if lo <= truth <= hi else "  fuori range"
        print(f"{r['file']:28s} {r['tipo']:14s} {truth:6.0f} {mid:6d} {lo:5d}-{hi:<5d} {err:+6.0%}{flag}")
    if errors:
        print(f"\n{len(errors)} foto: errore medio {statistics.mean(errors):+.0%}, "
              f"errore assoluto medio {statistics.mean(abs(e) for e in errors):.0%}, "
              f"entro ±30 %: {sum(abs(e) <= 0.3 for e in errors)}/{len(errors)}")
