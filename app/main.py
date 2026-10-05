from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from app.auth import LoginRequired
from app.deps import ProfileRequired
from app.routers import auth, balance, foods, meals, profile

app = FastAPI(title="Meal Tracker")
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static"),
    name="static",
)
app.include_router(auth.router)
app.include_router(profile.router)
app.include_router(balance.router)
app.include_router(meals.router)
app.include_router(foods.router)


def _redirect(request: Request, url: str) -> Response:
    # HTMX swaps cannot follow a redirect to a full page: ask the browser to navigate.
    if request.headers.get("HX-Request"):
        return Response(status_code=204, headers={"HX-Redirect": url})
    return RedirectResponse(url, status_code=303)


@app.exception_handler(LoginRequired)
def login_required(request: Request, exc: LoginRequired):
    return _redirect(request, f"/accedi?next={quote(request.url.path)}")


@app.exception_handler(ProfileRequired)
def profile_required(request: Request, exc: ProfileRequired):
    return _redirect(request, "/profilo")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
