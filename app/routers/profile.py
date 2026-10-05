"""The profile: what the daily targets are computed from."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user, templates
from app.models import ACTIVITY_LEVELS, GOALS, SEXES, Profile, User, Weight
from app.services import current_weight, targets_for

router = APIRouter(prefix="/profilo")

ACTIVITY_LABELS = {
    "sedentario": "Sedentario (poco o nessun esercizio)",
    "leggero": "Leggero (1–3 allenamenti a settimana)",
    "moderato": "Moderato (3–5 allenamenti a settimana)",
    "attivo": "Attivo (6–7 allenamenti a settimana)",
    "molto_attivo": "Molto attivo (lavoro fisico o doppi allenamenti)",
}


def _context(db: Session, user: User, profile: Profile | None, errors: list[str], form: dict | None = None):
    weight = current_weight(db, user)
    values = form or {
        "sex": profile.sex if profile else "M",
        "age": profile.age if profile else "",
        "height_cm": profile.height_cm if profile else "",
        "weight_kg": weight if weight else "",
        "activity": profile.activity if profile else "leggero",
        "goal": profile.goal if profile else "dimagrire",
        "deficit_kcal": profile.deficit_kcal if profile else 500,
        "protein_g_per_kg": profile.protein_g_per_kg if profile else 1.5,
    }
    return {
        "errors": errors,
        "v": values,
        "is_new": profile is None,
        "activity_labels": ACTIVITY_LABELS,
        "goals": GOALS,
        "targets": targets_for(db, user, date.today()),
    }


@router.get("")
def profilo(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    profile = db.get(Profile, user.id)
    return templates.TemplateResponse(request, "profile/form.html", _context(db, user, profile, []))


@router.post("")
def salva(
    request: Request,
    sex: Annotated[str, Form()],
    age: Annotated[int, Form()],
    height_cm: Annotated[float, Form()],
    weight_kg: Annotated[float, Form()],
    activity: Annotated[str, Form()],
    goal: Annotated[str, Form()],
    deficit_kcal: Annotated[float, Form()] = 500,
    protein_g_per_kg: Annotated[float, Form()] = 1.5,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    errors = []
    if sex not in SEXES:
        errors.append("Sesso non valido.")
    if not 10 <= age <= 110:
        errors.append("Età non valida (10–110 anni).")
    if not 100 <= height_cm <= 250:
        errors.append("Altezza non valida (100–250 cm).")
    if not 25 <= weight_kg <= 300:
        errors.append("Peso non valido (25–300 kg).")
    if activity not in ACTIVITY_LEVELS:
        errors.append("Livello di attività non valido.")
    if goal not in GOALS:
        errors.append("Obiettivo non valido.")
    if not 0 <= deficit_kcal <= 1500:
        errors.append("Deficit non valido (0–1500 kcal).")
    if not 0.5 <= protein_g_per_kg <= 3:
        errors.append("Proteine per kg non valide (0.5–3 g).")

    profile = db.get(Profile, user.id)
    if errors:
        form = dict(sex=sex, age=age, height_cm=height_cm, weight_kg=weight_kg, activity=activity,
                    goal=goal, deficit_kcal=deficit_kcal, protein_g_per_kg=protein_g_per_kg)
        return templates.TemplateResponse(
            request, "profile/form.html", _context(db, user, profile, errors, form), status_code=422
        )

    if profile is None:
        profile = Profile(user_id=user.id)
        db.add(profile)
    profile.sex, profile.age, profile.height_cm = sex, age, height_cm
    profile.activity, profile.goal = activity, goal
    profile.deficit_kcal, profile.protein_g_per_kg = deficit_kcal, protein_g_per_kg

    # The weight is a weigh-in of today; a second save today replaces it.
    today = date.today()
    if current_weight(db, user) != weight_kg:
        row = db.scalar(select(Weight).where(Weight.user_id == user.id, Weight.date == today))
        if row is None:
            db.add(Weight(user_id=user.id, date=today, kg=weight_kg))
        else:
            row.kg = weight_kg
    db.commit()
    return RedirectResponse("/", status_code=303)
