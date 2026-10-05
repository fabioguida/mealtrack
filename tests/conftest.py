"""Shared fixtures: one in-memory SQLite database per test, users, logged-in clients."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401  (registers the tables on Base)
from app.auth import COOKIE, hash_password, make_session
from app.db import Base, get_db, make_engine
from app.main import app
from app.models import Food, Profile, User, Weight
from app.textsearch import search_key

PASSWORD = "password-di-prova"


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


def make_user(db, email, with_profile=True, weight=85.0):
    u = User(email=email, password_hash=hash_password(PASSWORD))
    db.add(u)
    db.flush()
    if with_profile:
        # pace 500/1100 kg/week → a 500 kcal deficit and 1.5 g/kg, the suite's reference numbers
        db.add(Profile(user_id=u.id, sex="M", age=45, height_cm=180, activity="leggero",
                       kg_per_week=500 / 1100, goal="dimagrire", deficit_kcal=500, protein_g_per_kg=1.5))
        db.add(Weight(user_id=u.id, date=date(2026, 1, 1), kg=weight))
    db.commit()
    return u


def login_client(db, user) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    c.cookies.set(COOKIE, make_session(user.id))
    return c


@pytest.fixture
def user(db) -> User:
    """A registered user with a complete profile (85 kg → 1913 kcal target)."""
    return make_user(db, "test@example.com")


@pytest.fixture
def client(db, user):
    """Logged in as `user`."""
    c = login_client(db, user)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon(db):
    """Not logged in."""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def make_food(db, name, kcal, protein, carbs, fat, source_id=None, owner=None):
    food = Food(
        name=name,
        source="custom" if owner else "swiss",
        source_id=None if owner else source_id,
        search_key=search_key(name),
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
    return make_food(db, "Pasta, cooked", 371, 13.0, 74.7, 1.5, source_id="t-pasta")


@pytest.fixture
def oil(db):
    return make_food(db, "Oil, olive", 884, 0, 0, 100, source_id="t-oil")
