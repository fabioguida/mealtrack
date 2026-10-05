from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.routers import foods, meals

app = FastAPI(title="Meal Tracker")
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static"),
    name="static",
)
app.include_router(meals.router)
app.include_router(foods.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def home():
    # Phase 3 replaces this with the daily balance page.
    return RedirectResponse("/pasti", status_code=307)
