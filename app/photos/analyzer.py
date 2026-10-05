"""Meal photo analysis behind one interface (HANDOVER.md 8.1 stays open).

`analyze(image_bytes)` returns candidates: foods of our own table or recipes,
ranked. No analyzer estimates grams: the user confirms the candidate and the
portion comes from the personal library or is typed.

Providers:
- ClipAnalyzer: open-weights CLIP (sentence-transformers' clip-ViT-B-32 for the
  image, its multilingual text twin for the Italian labels), zero-shot over our
  list. Free, local, private. Good for one clear dish, weak for mixed plates.
- FakeAnalyzer: for tests.
A paid vision API can be added as another class behind the same interface.
"""

import hashlib
import io
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.models import Food
from app.recipes import load_recipes


@dataclass(frozen=True)
class Label:
    kind: str      # "food" | "recipe"
    ref: str       # food id or recipe key
    text: str      # what the model sees, e.g. "pollo, petto senza pelle"
    display: str   # what the user sees


@dataclass(frozen=True)
class Candidate:
    kind: str
    ref: str
    display: str
    score: float


class Analyzer(Protocol):
    name: str

    def analyze(self, image_bytes: bytes, k: int) -> list[Candidate]: ...


_PAREN = re.compile(r"\s*\([^)]*\)")


def clean_label(name: str, max_parts: int = 2) -> str:
    """'Pollo, petto senza pelle, crudo' → 'pollo, petto senza pelle':
    the first attributes identify the food; cooking notes only confuse CLIP."""
    parts = [p.strip() for p in _PAREN.sub("", name).split(",") if p.strip()]
    return ", ".join(parts[:max_parts]).lower()


def photo_labels(db: Session) -> list[Label]:
    """Shared foods (not oils, fats, spices, which no photo shows) and recipes."""
    skip = ("Grassi e oli", "Alimenti speciali")
    labels = []
    for f in db.scalars(select(Food).where(Food.source != "custom").order_by(Food.id)):
        if f.category and f.category.startswith(skip):
            continue
        labels.append(Label("food", str(f.id), clean_label(f.name), f.name))
    for r in load_recipes():
        labels.append(Label("recipe", r.key, r.name.lower(), r.name))
    return labels


class FakeAnalyzer:
    """Returns the given candidates; for tests."""

    name = "fake"

    def __init__(self, candidates: list[Candidate]):
        self.candidates = candidates

    def analyze(self, image_bytes: bytes, k: int) -> list[Candidate]:
        return self.candidates[:k]


class ClipAnalyzer:
    name = "clip"
    IMAGE_MODEL = "clip-ViT-B-32"
    TEXT_MODEL = "sentence-transformers/clip-ViT-B-32-multilingual-v1"
    PROMPT = "una foto di {}"

    def __init__(self, labels: list[Label], cache_dir: Path = config.CACHE_DIR):
        self.labels = labels
        self.cache_dir = cache_dir
        self._img_model = None
        self._text_emb = None

    def _load(self):
        try:
            # Model downloads on machines whose HTTPS goes through a local root
            # certificate (corporate proxy, antivirus): trust the OS store.
            import truststore

            truststore.inject_into_ssl()
        except ImportError:
            pass
        import numpy as np
        from sentence_transformers import SentenceTransformer

        self._img_model = SentenceTransformer(self.IMAGE_MODEL)
        key = hashlib.sha1(json.dumps([l.text for l in self.labels]).encode()).hexdigest()[:16]
        cache = self.cache_dir / f"clip_text_{key}.npy"
        if cache.is_file():
            self._text_emb = np.load(cache)
            return
        text_model = SentenceTransformer(self.TEXT_MODEL)
        emb = text_model.encode(
            [self.PROMPT.format(l.text) for l in self.labels],
            batch_size=64, normalize_embeddings=True, show_progress_bar=False,
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        np.save(cache, emb)
        self._text_emb = emb

    def analyze(self, image_bytes: bytes, k: int) -> list[Candidate]:
        import numpy as np
        from PIL import Image

        if self._img_model is None:
            self._load()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img_emb = self._img_model.encode([image], normalize_embeddings=True, show_progress_bar=False)[0]
        sims = self._text_emb @ img_emb
        top = np.argsort(-sims)[:k]
        return [Candidate(self.labels[i].kind, self.labels[i].ref, self.labels[i].display, float(sims[i])) for i in top]


_analyzer: Analyzer | None = None


def get_analyzer(db: Session) -> Analyzer | None:
    """The configured analyzer, built once; None when photos are off."""
    global _analyzer
    if config.PHOTO_PROVIDER == "none":
        return None
    if _analyzer is None and config.PHOTO_PROVIDER == "clip":
        _analyzer = ClipAnalyzer(photo_labels(db))
    return _analyzer
