from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User
from scripts.init_db import init_db


def test_init_db_seeds_user_once(engine):
    first = init_db(engine, "seed@example.com")
    second = init_db(engine, "seed@example.com")

    assert first.id == second.id
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
