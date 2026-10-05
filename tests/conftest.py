"""Shared fixtures: one in-memory SQLite database per test, a seeded user, a client."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (registers the tables on Base)
from app.db import Base, get_db, make_engine
from app.main import app
from app.models import Food, User


@pytest.fixture
def engine():
    # StaticPool keeps the single in-memory connection alive across sessions.
    eng = make_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine) -> Session:
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture
def user(db) -> User:
    """The first user; `current_user` resolves to this one until phase 4."""
    u = User(email="test@example.com")
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def client(db, user):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_food(db, name, kcal, protein, carbs, fat, fdc_id=None, owner=None):
    food = Food(
        name=name,
        source="custom" if owner else "usda",
        usda_fdc_id=fdc_id,
        owner_user_id=owner.id if owner else None,
        kcal=kcal,
        protein_g=protein,
        carbs_g=carbs,
        fat_g=fat,
    )
    db.add(food)
    db.commit()
    return food


@pytest.fixture
def pasta(db):
    return make_food(db, "Pasta, cooked", 371, 13.0, 74.7, 1.5, fdc_id=170148)


@pytest.fixture
def oil(db):
    return make_food(db, "Oil, olive", 884, 0, 0, 100, fdc_id=171413)
