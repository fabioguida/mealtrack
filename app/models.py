"""Database tables. Phase 1: users, foods, meals, meal_items.

Nutrient columns on `foods` are per 100 g. `meal_items` stores the values
computed at save time, so editing a food later does not rewrite past meals.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

MEAL_TYPES = ("colazione", "pranzo", "spezzafame", "cena")
INPUT_METHODS = ("manual", "photo", "preset")
FOOD_SOURCES = ("usda", "custom")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # Nullable until phase 4 (authentication).
    password_hash: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    meals: Mapped[list["Meal"]] = relationship(back_populates="user")


class Food(Base):
    __tablename__ = "foods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Italian alias, filled by hand; search matches both names.
    name_it: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    usda_fdc_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    # Set only for custom foods.
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    kcal: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)


class Meal(Base):
    __tablename__ = "meals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    datetime: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    meal_type: Mapped[str] = mapped_column(String(12), nullable=False)
    photo_url: Mapped[str | None] = mapped_column(String(512))
    input_method: Mapped[str] = mapped_column(String(10), nullable=False)

    user: Mapped[User] = relationship(back_populates="meals")
    items: Mapped[list["MealItem"]] = relationship(
        back_populates="meal", cascade="all, delete-orphan"
    )


class MealItem(Base):
    __tablename__ = "meal_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meal_id: Mapped[int] = mapped_column(
        ForeignKey("meals.id", ondelete="CASCADE"), nullable=False
    )
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"), nullable=False)
    grams: Mapped[float] = mapped_column(Float, nullable=False)
    kcal: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)

    meal: Mapped[Meal] = relationship(back_populates="items")
    food: Mapped[Food] = relationship()
