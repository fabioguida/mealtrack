from fastapi import FastAPI

app = FastAPI(title="Meal Tracker")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
