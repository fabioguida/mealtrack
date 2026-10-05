"""Food search (HTMX partial) and custom foods."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user, templates
from app.models import Food, User
from app.recipes import search_recipes
from app.textsearch import query_words, search_key

router = APIRouter(prefix="/alimenti")

SEARCH_LIMIT = 20


def visible_foods(user: User):
    """Foods this user may use: every shared row plus their own custom ones."""
    return select(Food).where(
        or_(Food.source != "custom", Food.owner_user_id == user.id)
    )


def search_foods(db: Session, user: User, q: str) -> list[Food]:
    """Every word of the query must start a word of the food's name or synonyms,
    in any order, ignoring accents. Basic foods come before prepared dishes
    ("Cibi/..."), the user's own foods first of all, shorter names first."""
    words = query_words(q)
    if not words or len("".join(words)) < 2:
        return []
    stmt = visible_foods(user)
    for w in words:
        stmt = stmt.where(Food.search_key.like(f"% {w}%"))
    stmt = stmt.order_by(
        case((Food.source == "custom", 0), else_=1),
        case((Food.category.like("Cibi%"), 1), else_=0),
        func.length(Food.name),
    ).limit(SEARCH_LIMIT)
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
    recipes = [] if mode == "pref" else search_recipes(q)
    if recipes:
        foods = foods[:12]  # keep the dishes within reach on a phone
    return templates.TemplateResponse(
        request,
        "partials/food_results.html",
        {"foods": foods, "recipes": recipes, "q": q.strip(), "mode": mode},
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
            search_key=search_key(name),
            kcal=kcal,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fat_g=fat_g,
        )
    )
    db.commit()
    return RedirectResponse("/pasti/nuovo", status_code=303)
