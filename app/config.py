"""Settings read from the environment (optionally from a .env file)."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, no quoting rules, env wins."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.environ.get(
    "DATABASE_URL", f"sqlite:///{PROJECT_ROOT / 'mealtrack.db'}"
)

# Profile of the seeded user until phase 4 (profiles table). Placeholder
# numbers; set the real ones in .env (see .env.example).
PROFILE = {
    "sex": os.environ.get("PROFILE_SEX", "M"),
    "age": int(os.environ.get("PROFILE_AGE", "45")),
    "height_cm": float(os.environ.get("PROFILE_HEIGHT_CM", "180")),
    "weight_kg": float(os.environ.get("PROFILE_WEIGHT_KG", "85")),
    "activity": os.environ.get("PROFILE_ACTIVITY", "leggero"),
    "deficit_kcal": float(os.environ.get("PROFILE_DEFICIT_KCAL", "500")),
    "protein_g_per_kg": float(os.environ.get("PROFILE_PROTEIN_G_PER_KG", "1.5")),
}
