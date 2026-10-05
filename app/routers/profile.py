"""The profile: personal facts only. Deficit and protein level are derived."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calc.targets import PACES, deficit_for, protein_g_per_kg_for
from app.db import get_db
from app.deps import current_user, templates
from app.models import ACTIVITY_LEVELS, SEXES, Profile, User, Weight
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
        "kg_per_week": profile.pace if profile else 0.5,
    }
    return {
        "errors": errors,
        "v": values,
        "is_new": profile is None,
        "activity_labels": ACTIVITY_LABELS,
        "paces": PACES,
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
    kg_per_week: Annotated[float, Form()],
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
    if kg_per_week not in PACES:
        errors.append("Obiettivo non valido.")

    profile = db.get(Profile, user.id)
    if errors:
        form = dict(sex=sex, age=age, height_cm=height_cm, weight_kg=weight_kg, activity=activity, kg_per_week=kg_per_week)
        return templates.TemplateResponse(
            request, "profile/form.html", _context(db, user, profile, errors, form), status_code=422
        )

    if profile is None:
        profile = Profile(user_id=user.id)
        db.add(profile)
    profile.sex, profile.age, profile.height_cm, profile.activity = sex, age, height_cm, activity
    profile.kg_per_week = kg_per_week
    # Derived values, kept for the record.
    profile.goal = "mantenere" if kg_per_week == 0 else "dimagrire"
    profile.deficit_kcal = deficit_for(kg_per_week)
    profile.protein_g_per_kg = protein_g_per_kg_for(kg_per_week)

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
