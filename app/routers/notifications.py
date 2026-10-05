"""Email settings, 'send me one now', and the shopping list page."""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config
from app.db import get_db
from app.deps import current_user, templates
from app.emails import compose_daily, compose_weekly, get_backend, send_logged, settings_for
from app.models import EmailLog, NotificationSettings, User
from app.shopping import shopping_list

router = APIRouter()


@router.get("/notifiche")
def notifiche(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user), msg: str = ""):
    log = db.scalars(select(EmailLog).where(EmailLog.user_id == user.id).order_by(EmailLog.sent_at.desc()).limit(10)).all()
    return templates.TemplateResponse(
        request, "notifications/settings.html",
        {"s": settings_for(db, user), "log": log, "msg": msg, "backend": config.EMAIL_BACKEND, "email": user.email},
    )


@router.post("/notifiche")
async def salva(request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    form = await request.form()
    row = db.get(NotificationSettings, user.id)
    if row is None:
        row = NotificationSettings(user_id=user.id)
        db.add(row)
    row.daily_shopping = bool(form.get("daily_shopping"))
    row.weekly_shopping = bool(form.get("weekly_shopping"))
    row.progress = bool(form.get("progress"))
    row.weekly_only = bool(form.get("weekly_only"))
    db.commit()
    return RedirectResponse("/notifiche?msg=salvato", status_code=303)


@router.post("/notifiche/invia")
def invia(kind: Annotated[str, Form()], db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Send the daily or the weekly email now (logged as a test, never deduplicated)."""
    today = date.today()
    if kind == "weekly":
        msg = compose_weekly(db, user, today)
    else:
        msg = compose_daily(db, user, today)
    period = f"test-{today.isoformat()}-{len(db.scalars(select(EmailLog).where(EmailLog.user_id == user.id)).all())}"
    status = send_logged(db, user, f"test-{kind}", period, msg)
    where = "nel log del server" if config.EMAIL_BACKEND == "console" else f"a {user.email}"
    text = {"sent": f"inviata {where}", "skipped": "niente da inviare: nessun piano e nessun profilo", "failed": "invio fallito, vedi il registro"}.get(status, status)
    return RedirectResponse(f"/notifiche?msg={text}", status_code=303)


@router.get("/spesa")
def spesa(request: Request, periodo: str = "domani", db: Session = Depends(get_db), user: User = Depends(current_user)):
    today = date.today()
    if periodo == "settimana":
        start = today + timedelta(days=(7 - today.weekday()) % 7 or 7)
        end = start + timedelta(days=6)
    elif periodo == "oggi":
        start = end = today
    else:
        periodo = "domani"
        start = end = today + timedelta(days=1)
    return templates.TemplateResponse(
        request, "notifications/shopping.html",
        {"groups": shopping_list(db, user, start, end), "periodo": periodo, "start": start, "end": end},
    )
