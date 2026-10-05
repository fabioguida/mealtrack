"""Meal photos: upload, portion estimate (hand on the plate), optional recognition, serving."""

import io
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import config
from app.db import get_db
from app.deps import current_user, templates
from app.models import Profile, User
from app.photos.analyzer import Analyzer, get_analyzer
from app.photos.portion import PortionEstimate
from app.recipes import recipe_by_key

router = APIRouter()

MAX_UPLOAD = 12 * 1024 * 1024
ESTIMATE_TYPES = [  # what the user sees under the photo, in this order
    ("pasta", "Pasta o riso"),
    ("carne", "Carne"),
    ("pesce", "Pesce"),
    ("legumi", "Legumi"),
    ("verdure cotte", "Verdure cotte"),
    ("insalata", "Insalata"),
    ("pizza", "Pizza"),
]


def analyzer_dep(db: Session = Depends(get_db)) -> Analyzer | None:
    return get_analyzer(db)


def estimator_dep():
    """The portion estimator as a dependency, so tests can replace it."""
    if not config.PORTION_ESTIMATOR:
        return None
    from app.photos.portion import estimate_portion

    return estimate_portion


def store_photo(user: User, image_bytes: bytes) -> tuple[str, bytes, "Image"]:
    """Resize to PHOTO_MAX_PX, save as JPEG under PHOTO_DIR/<user>/, return (url, jpeg, image)."""
    from PIL import Image, UnidentifiedImageError

    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(422, "Il file non è un'immagine.")
    from PIL import ImageOps

    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((config.PHOTO_MAX_PX, config.PHOTO_MAX_PX))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=85)
    name = f"{uuid.uuid4().hex}.jpg"
    folder = config.PHOTO_DIR / str(user.id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(out.getvalue())
    return f"/foto/{user.id}/{name}", out.getvalue(), image


@router.post("/foto/analizza")
async def analizza(
    request: Request,
    foto: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    analyzer: Analyzer | None = Depends(analyzer_dep),
    estimator=Depends(estimator_dep),
):
    data = await foto.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(422, "Foto troppo grande (massimo 12 MB).")
    url, jpeg, image = store_photo(user, data)

    estimate: PortionEstimate | None = None
    estimate_error = None
    if estimator is not None:
        profile = db.get(Profile, user.id)
        if profile is None:
            estimate_error = "Compila il profilo (sesso e altezza) per la stima della porzione."
        else:
            try:
                import numpy as np

                estimate = estimator(np.asarray(image), profile.sex, profile.height_cm)
            except Exception as exc:  # model file missing, odd image...: the photo is still saved
                estimate_error = f"Stima non riuscita ({type(exc).__name__})."

    candidates, error = [], None
    if analyzer is not None:
        try:
            candidates = analyzer.analyze(jpeg, config.PHOTO_CANDIDATES)
        except Exception as exc:
            error = f"Riconoscimento non riuscito ({type(exc).__name__})."
        candidates = [c for c in candidates if c.kind == "food" or recipe_by_key(c.ref)]

    return templates.TemplateResponse(
        request,
        "partials/photo_results.html",
        {
            "photo_url": url,
            "estimate": estimate,
            "estimate_error": estimate_error,
            "estimate_on": estimator is not None,
            "estimate_types": ESTIMATE_TYPES,
            "candidates": candidates,
            "error": error,
        },
    )


@router.get("/foto/{user_id}/{name}")
def foto(user_id: int, name: str, user: User = Depends(current_user)):
    """Photos are private: only their owner can see them."""
    if user_id != user.id or "/" in name or ".." in name or not name.endswith(".jpg"):
        raise HTTPException(404)
    path = config.PHOTO_DIR / str(user.id) / name
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg")
