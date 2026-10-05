"""Food search (HTMX partial) and custom foods."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user, templates
from app.models import Food, User

router = APIRouter(prefix="/alimenti")

SEARCH_LIMIT = 20


def visible_foods(user: User):
    """Foods this user may use: all USDA rows plus their own custom ones."""
    return select(Food).where(
        or_(Food.source == "usda", Food.owner_user_id == user.id)
    )


def search_foods(db: Session, user: User, q: str) -> list[Food]:
    q = q.strip()
    if len(q) < 2:
        return []
    pattern = f"%{q}%"
    stmt = (
        visible_foods(user)
        .where(or_(Food.name.ilike(pattern), Food.name_it.ilike(pattern)))
        # Custom foods first (the user's own dishes), then short names first.
        .order_by(Food.source.desc(), Food.name)
        .limit(SEARCH_LIMIT)
    )
    return list(db.scalars(stmt))


@router.get("/cerca")
def cerca(
    request: Request,
    q: str = "",
    mode: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    foods = search_foods(db, user, q)
    return templates.TemplateResponse(
        request, "partials/food_results.html", {"foods": foods, "q": q.strip(), "mode": mode}
    )


@router.get("/nuovo")
def nuovo(request: Request, user: User = Depends(current_user)):
    return templates.TemplateResponse(request, "foods/new.html", {"errors": []})


@router.post("")
def crea(
    request: Request,
    name: Annotated[str, Form()],
    kcal: Annotated[float, Form()],
    protein_g: Annotated[float, Form()],
    carbs_g: Annotated[float, Form()],
    fat_g: Annotated[float, Form()],
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    errors = []
    name = name.strip()
    if not name:
        errors.append("Il nome è obbligatorio.")
    if min(kcal, protein_g, carbs_g, fat_g) < 0:
        errors.append("I valori non possono essere negativi.")
    if errors:
        return templates.TemplateResponse(
            request, "foods/new.html", {"errors": errors}, status_code=422
        )
    db.add(
        Food(
            name=name,
            source="custom",
            owner_user_id=user.id,
            kcal=kcal,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
        )
    )
    db.commit()
    return RedirectResponse("/pasti/nuovo", status_code=303)
