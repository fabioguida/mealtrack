"""Alembic: the baseline migration builds the whole schema and tears it down,
and it matches the models (no autogenerate drift)."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

ROOT = Path(__file__).resolve().parent.parent


def alembic(*args, db_path):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{db_path.as_posix()}"}
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True)


def test_upgrade_head_and_downgrade_base(tmp_path):
    db = tmp_path / "m.db"
    r = alembic("upgrade", "head", db_path=db)
    assert r.returncode == 0, r.stderr
    tables = set(inspect(create_engine(f"sqlite:///{db.as_posix()}")).get_table_names())
    assert {"users", "profiles", "weights", "workouts", "foods", "meals", "meal_items", "meal_presets",
            "meal_preset_items", "eating_schedules", "food_preferences", "meal_plans", "meal_plan_items"} <= tables
    r = alembic("downgrade", "base", db_path=db)
    assert r.returncode == 0, r.stderr
    assert set(inspect(create_engine(f"sqlite:///{db.as_posix()}")).get_table_names()) == {"alembic_version"}


def test_models_match_migrations(tmp_path):
    """A model change without a migration shows up as an autogenerate diff."""
    db = tmp_path / "m.db"
    assert alembic("upgrade", "head", db_path=db).returncode == 0
    r = alembic("check", db_path=db)
    assert r.returncode == 0, r.stdout + r.stderr
