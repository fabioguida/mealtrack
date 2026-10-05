"""Create the tables and seed the first user.

Usage: python scripts/init_db.py
The seed user's email comes from SEED_USER_EMAIL (see .env.example).
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models  # noqa: F401  (registers the tables on Base)
from app.db import Base, engine
from app.models import User


def init_db(bind, seed_email: str) -> User:
    Base.metadata.create_all(bind)
    with Session(bind, expire_on_commit=False) as db:
        user = db.scalar(select(User).where(User.email == seed_email))
        if user is None:
            user = User(email=seed_email)
            db.add(user)
            db.commit()
        return user


if __name__ == "__main__":
    email = os.environ.get("SEED_USER_EMAIL", "afguida@gmail.com")
    user = init_db(engine, email)
    print(f"Tabelle create. Utente iniziale: {user.email} (id {user.id})")
