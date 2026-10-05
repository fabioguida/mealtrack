"""Workouts: log with MET-based kcal, history, delete."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calc.activity import MET_TABLE, kcal_for
from app.db import get_db
from app.deps import ProfileRequired, current_user, templates
from app.models import User, Workout
from app.services import current_weight

router = APIRouter(prefix="/attivita")


def _page(request, db, user, errors, form=None):
    rows = db.scalars(
        select(Workout).where(Workout.user_id == user.id).order_by(Workout.date.desc(), Workout.id.desc()).limit(60)
    ).all()
    weight = current_weight(db, user)
    return templates.TemplateResponse(
        request,
        "workouts/list.html",
        {
            "rows": rows,
            "met": MET_TABLE,
            "weight": weight,
            "errors": errors,
            "form": form or {"date": date.today().isoformat(), "activity": "camminata", "duration_min": 30},
        },
    )


@router.get("")
def elenco(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _page(request, db, user, [])


@router.post("")
def registra(
    request: Request,
    day: Annotated[str, Form()],
    activity: Annotated[str, Form()],
    duration_min: Annotated[float, Form()],
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    errors = []
    try:
        when = date.fromisoformat(day)
    except ValueError:
        when, errors = date.today(), ["Data non valida."]
    if activity not in MET_TABLE:
        errors.append("Attività non valida.")
    if not 1 <= duration_min <= 600:
        errors.append("Durata non valida (1–600 minuti).")
    weight = current_weight(db, user, when)
    if weight is None:
        raise ProfileRequired()
    if errors:
        return _page(request, db, user, errors, {"date": day, "activity": activity, "duration_min": duration_min})
    db.add(
        Workout(
            user_id=user.id,
            date=when,
            activity=activity,
            duration_min=duration_min,
            kcal_burned=kcal_for(activity, weight, duration_min),
        )
    )
    db.commit()
    return RedirectResponse("/attivita", status_code=303)


@router.post("/{workout_id}/elimina")
def elimina(workout_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.scalar(select(Workout).where(Workout.id == workout_id, Workout.user_id == user.id))
    if row is None:
        raise HTTPException(404)
    db.delete(row)
    db.commit()
    return RedirectResponse("/attivita", status_code=303)
