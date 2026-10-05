"""Registration, login, logout."""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import clear_session, hash_password, set_session, verify_password
from app.config import ALLOW_SIGNUP
from app.db import get_db
from app.deps import templates
from app.models import User

router = APIRouter()

MIN_PASSWORD = 8


def _safe_next(value: str | None) -> str:
    # Only same-site paths, so the login page cannot bounce elsewhere.
    return value if value and value.startswith("/") and not value.startswith("//") else "/"


@router.get("/accedi")
def accedi_form(request: Request, next: str = "/"):
    return templates.TemplateResponse(
        request, "auth/login.html", {"errors": [], "next": _safe_next(next), "signup": ALLOW_SIGNUP}
    )


@router.post("/accedi")
def accedi(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: Annotated[str, Form()] = "/",
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not verify_password(user.password_hash, password):
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {"errors": ["Email o password non corretti."], "next": _safe_next(next), "signup": ALLOW_SIGNUP},
            status_code=401,
        )
    response = RedirectResponse(_safe_next(next), status_code=303)
    set_session(response, user)
    return response


@router.post("/esci")
def esci():
    response = RedirectResponse("/accedi", status_code=303)
    clear_session(response)
    return response


@router.get("/registrati")
def registrati_form(request: Request):
    if not ALLOW_SIGNUP:
        return RedirectResponse("/accedi", status_code=303)
    return templates.TemplateResponse(request, "auth/register.html", {"errors": [], "email": ""})


@router.post("/registrati")
def registrati(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    password2: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    if not ALLOW_SIGNUP:
        return RedirectResponse("/accedi", status_code=303)
    email = email.strip().lower()
    errors = []
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        errors.append("Inserisci un indirizzo email valido.")
    if len(password) < MIN_PASSWORD:
        errors.append(f"La password deve avere almeno {MIN_PASSWORD} caratteri.")
    if password != password2:
        errors.append("Le due password non coincidono.")
    if not errors and db.scalar(select(User).where(User.email == email)):
        errors.append("Esiste già un account con questa email.")
    if errors:
        return templates.TemplateResponse(
            request, "auth/register.html", {"errors": errors, "email": email}, status_code=422
        )
    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    response = RedirectResponse("/profilo", status_code=303)
    set_session(response, user)
    return response
