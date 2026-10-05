from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Food, Meal, MealItem, User


def _food(name, kcal, protein, carbs, fat, source_id=None):
    return Food(
        name=name,
        source="swiss" if source_id else "custom",
        source_id=source_id,
        kcal=kcal,
        protein_g=protein,
        carbs_g=carbs,
        fat_g=fat,
    )


def test_meal_with_items_round_trip(db):
    user = User(email="a@example.com")
    pasta = _food("Pasta, cooked", 158, 5.8, 30.9, 0.9, source_id="378")
    oil = _food("Olive oil", 884, 0, 0, 100, source_id="591")
    db.add_all([user, pasta, oil])
    db.flush()

    meal = Meal(
        user_id=user.id,
        datetime=datetime(2026, 10, 5, 13, 30),
        meal_type="pranzo",
        input_method="manual",
        items=[
            MealItem(food=pasta, grams=140, kcal=221.2, protein_g=8.12, carbs_g=43.26, fat_g=1.26),
            MealItem(food=oil, grams=10, kcal=88.4, protein_g=0, carbs_g=0, fat_g=10),
        ],
    )
    db.add(meal)
    db.commit()

    loaded = db.get(Meal, meal.id)
    assert loaded.user.email == "a@example.com"
    assert [i.food.name for i in loaded.items] == ["Pasta, cooked", "Olive oil"]
    assert sum(i.kcal for i in loaded.items) == pytest.approx(309.6)


def test_deleting_meal_deletes_items(db):
    user = User(email="a@example.com")
    food = _food("Apple", 52, 0.3, 13.8, 0.2)
    db.add_all([user, food])
    db.flush()
    meal = Meal(
        user_id=user.id,
        datetime=datetime(2026, 10, 5, 15, 30),
        meal_type="spezzafame",
        input_method="manual",
        items=[MealItem(food=food, grams=150, kcal=78, protein_g=0.45, carbs_g=20.7, fat_g=0.3)],
    )
    db.add(meal)
    db.commit()
    assert db.scalar(select(MealItem).where(MealItem.meal_id == meal.id)) is not None

    db.delete(meal)
    db.commit()
    assert db.scalars(select(MealItem)).all() == []


def test_source_id_is_unique_per_source(db):
    db.add(_food("Pasta", 158, 5.8, 30.9, 0.9, source_id="378"))
    db.commit()
    db.add(_food("Pasta again", 158, 5.8, 30.9, 0.9, source_id="378"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_user_email_is_unique(db):
    db.add(User(email="a@example.com"))
    db.commit()
    db.add(User(email="a@example.com"))
    with pytest.raises(IntegrityError):
        db.commit()
