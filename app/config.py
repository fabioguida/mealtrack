"""Settings read from the environment (optionally from a .env file)."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, `#` comments, env wins."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.environ.get(
    "DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'mealtrack.db'}"
)

# Signs the session cookie. Set a long random value in production.
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
# Send the cookie only over HTTPS (set to true behind nginx in production).
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"
SESSION_DAYS = int(os.environ.get("SESSION_DAYS", "30"))
# Family and friends register themselves; close it once everyone is in.
ALLOW_SIGNUP = os.environ.get("ALLOW_SIGNUP", "true").lower() == "true"

# Meal photos: where they are stored and which analyzer reads them.
# PHOTO_PROVIDER: "clip" (open-weights CLIP, local, free) or "none".
PHOTO_DIR = Path(os.environ.get("PHOTO_DIR", PROJECT_ROOT / "data" / "photos"))
PHOTO_PROVIDER = os.environ.get("PHOTO_PROVIDER", "clip")
PHOTO_MAX_PX = int(os.environ.get("PHOTO_MAX_PX", "1600"))
PHOTO_CANDIDATES = int(os.environ.get("PHOTO_CANDIDATES", "8"))
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
