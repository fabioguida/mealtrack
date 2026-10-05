"""Create the tables and seed the first user.

Usage: python scripts/init_db.py
SEED_USER_EMAIL and SEED_USER_PASSWORD come from the environment / .env.
Without a password the user exists but cannot log in (see set_password.py).
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app import models  # noqa: F401  (registers the tables on Base)
from app.auth import hash_password
from app.db import Base, engine
from app.models import User


def add_missing_columns(bind) -> list[str]:
    """Pending Alembic (phase 9): add columns that new phases introduced to an
    existing database. Only nullable / defaulted columns can be added this way."""
    added = []
    inspector = inspect(bind)
    with bind.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in inspector.get_table_names():
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                ddl = f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col.type.compile(bind.dialect)}"
                conn.execute(text(ddl))
                added.append(f"{table.name}.{col.name}")
    return added


def init_db(bind, seed_email: str, seed_password: str | None = None) -> User:
    Base.metadata.create_all(bind)
    add_missing_columns(bind)
    with Session(bind, expire_on_commit=False) as db:
        user = db.scalar(select(User).where(User.email == seed_email))
        if user is None:
            user = User(email=seed_email)
            db.add(user)
        if seed_password:
            user.password_hash = hash_password(seed_password)
        db.commit()
        return user


if __name__ == "__main__":
    email = os.environ.get("SEED_USER_EMAIL", "afguida@gmail.com").lower()
    user = init_db(engine, email, os.environ.get("SEED_USER_PASSWORD") or None)
    status = "con password" if user.password_hash else "SENZA password (usa scripts/set_password.py)"
    print(f"Tabelle pronte. Utente iniziale: {user.email} (id {user.id}), {status}")
