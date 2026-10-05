"""Try the CLIP analyzer on a photo from the command line.

Usage: python scripts/photo_test.py <photo.jpg> [k]

The first run downloads the two CLIP models (~1 GB) and embeds the ~1,300
labels (a minute on CPU); both are cached, later runs take about a second.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import Session

from app.db import engine
from app.photos.analyzer import ClipAnalyzer, photo_labels

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    with Session(engine) as db:
        labels = photo_labels(db)
    print(f"{len(labels)} etichette")
    analyzer = ClipAnalyzer(labels)
    t0 = time.time()
    for c in analyzer.analyze(Path(sys.argv[1]).read_bytes(), k):
        print(f"  {c.score:.3f}  {'[Piatto] ' if c.kind == 'recipe' else ''}{c.display}")
    print(f"{time.time() - t0:.1f} s")
