"""Meal photos: upload, analysis into candidates, and serving the stored image."""

import io
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import config
from app.db import get_db
from app.deps import current_user, templates
from app.models import User
from app.photos.analyzer import Analyzer, get_analyzer
from app.recipes import recipe_by_key

router = APIRouter()

MAX_UPLOAD = 12 * 1024 * 1024


def analyzer_dep(db: Session = Depends(get_db)) -> Analyzer | None:
    return get_analyzer(db)


def store_photo(user: User, image_bytes: bytes) -> tuple[str, bytes]:
    """Resize to PHOTO_MAX_PX, save as JPEG under PHOTO_DIR/<user>/, return (url, jpeg bytes)."""
    from PIL import Image, UnidentifiedImageError

    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except (UnidentifiedImageError, OSError):
        raise HTTPException(422, "Il file non è un'immagine.")
    image = image.convert("RGB")
    image.thumbnail((config.PHOTO_MAX_PX, config.PHOTO_MAX_PX))
    out = io.BytesIO()
    image.save(out, "JPEG", quality=85)
    name = f"{uuid.uuid4().hex}.jpg"
    folder = config.PHOTO_DIR / str(user.id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(out.getvalue())
    return f"/foto/{user.id}/{name}", out.getvalue()


@router.post("/foto/analizza")
async def analizza(
    request: Request,
    foto: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    analyzer: Analyzer | None = Depends(analyzer_dep),
):
    data = await foto.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(422, "Foto troppo grande (massimo 12 MB).")
    url, jpeg = store_photo(user, data)
    candidates, error = [], None
    if analyzer is None:
        error = "Il riconoscimento delle foto non è attivo: la foto resta allegata al pasto."
    else:
        try:
            candidates = analyzer.analyze(jpeg, config.PHOTO_CANDIDATES)
        except Exception as exc:  # model missing, out of memory...: the photo is still saved
            error = f"Riconoscimento non riuscito ({type(exc).__name__}): la foto resta allegata al pasto."
    # Recipes that no longer exist are dropped.
    candidates = [c for c in candidates if c.kind == "food" or recipe_by_key(c.ref)]
    return templates.TemplateResponse(
        request,
        "partials/photo_results.html",
        {"candidates": candidates, "photo_url": url, "error": error, "provider": analyzer.name if analyzer else None},
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
