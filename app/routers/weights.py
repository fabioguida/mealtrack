"""Weigh-ins: log, history, inline SVG chart, delete."""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_user, templates
from app.models import User, Weight

router = APIRouter(prefix="/peso")

CHART_DAYS = 90
CHART_W, CHART_H, PAD = 600, 220, 28


def chart_points(rows: list[Weight], end: date) -> dict | None:
    """Scale the last CHART_DAYS weigh-ins into the SVG viewBox."""
    start = end - timedelta(days=CHART_DAYS)
    pts = [(r.date, r.kg) for r in rows if r.date >= start]
    if len(pts) < 2:
        return None
    lo, hi = min(k for _, k in pts), max(k for _, k in pts)
    if hi - lo < 1:
        lo, hi = lo - 0.5, hi + 0.5
    def x(d): return PAD + (d - start).days / CHART_DAYS * (CHART_W - 2 * PAD)
    def y(k): return CHART_H - PAD - (k - lo) / (hi - lo) * (CHART_H - 2 * PAD)
    return {
        "w": CHART_W, "h": CHART_H, "pad": PAD,
        "lo": lo, "hi": hi,
        "polyline": " ".join(f"{x(d):.1f},{y(k):.1f}" for d, k in pts),
        "points": [(f"{x(d):.1f}", f"{y(k):.1f}", d, k) for d, k in pts],
        "start": start, "end": end,
    }


def _page(request, db, user, errors, form=None):
    rows = db.scalars(
        select(Weight).where(Weight.user_id == user.id).order_by(Weight.date.desc())
    ).all()
    return templates.TemplateResponse(
        request,
        "weights/list.html",
        {
            "rows": rows[:60],
            "chart": chart_points(list(reversed(rows)), date.today()),
            "errors": errors,
            "form": form or {"date": date.today().isoformat(), "kg": ""},
        },
    )


@router.get("")
def elenco(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _page(request, db, user, [])


@router.post("")
def registra(
    request: Request,
    day: Annotated[str, Form()],
    kg: Annotated[float, Form()],
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    errors = []
    try:
        when = date.fromisoformat(day)
    except ValueError:
        when, errors = date.today(), ["Data non valida."]
    if when > date.today():
        errors.append("La data non può essere nel futuro.")
    if not 25 <= kg <= 300:
        errors.append("Peso non valido (25–300 kg).")
    if errors:
        return _page(request, db, user, errors, {"date": day, "kg": kg})
    row = db.scalar(select(Weight).where(Weight.user_id == user.id, Weight.date == when))
    if row is None:
        db.add(Weight(user_id=user.id, date=when, kg=kg))
    else:
        row.kg = kg  # one weigh-in per day: the later entry replaces the earlier
    db.commit()
    return RedirectResponse("/peso", status_code=303)


@router.post("/{weight_id}/elimina")
def elimina(weight_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = db.scalar(select(Weight).where(Weight.id == weight_id, Weight.user_id == user.id))
    if row is None:
        raise HTTPException(404)
    db.delete(row)
    db.commit()
    return RedirectResponse("/peso", status_code=303)
