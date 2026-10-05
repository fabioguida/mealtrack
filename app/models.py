"""Database tables.

Nutrient columns on `foods` are per 100 g. `meal_items` stores the values
computed at save time, so editing a food later does not rewrite past meals.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

MEAL_TYPES = ("colazione", "pranzo", "spezzafame", "cena")
INPUT_METHODS = ("manual", "photo", "preset")
FOOD_SOURCES = ("usda", "custom")
SEXES = ("M", "F")
ACTIVITY_LEVELS = ("sedentario", "leggero", "moderato", "attivo", "molto_attivo")
GOALS = ("dimagrire", "mantenere")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    meals: Mapped[list["Meal"]] = relationship(back_populates="user")
    profile: Mapped["Profile | None"] = relationship(back_populates="user", uselist=False)


class Profile(Base):
    """What the targets need, except the weight, which lives in `weights`."""

    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    sex: Mapped[str] = mapped_column(String(1), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    height_cm: Mapped[float] = mapped_column(Float, nullable=False)
    activity: Mapped[str] = mapped_column(String(16), nullable=False)
    goal: Mapped[str] = mapped_column(String(16), nullable=False, default="dimagrire")
    deficit_kcal: Mapped[float] = mapped_column(Float, nullable=False, default=500)
    protein_g_per_kg: Mapped[float] = mapped_column(Float, nullable=False, default=1.5)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="profile")


class Weight(Base):
    __tablename__ = "weights"
    __table_args__ = (UniqueConstraint("user_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    kg: Mapped[float] = mapped_column(Float, nullable=False)


class Workout(Base):
    __tablename__ = "workouts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    activity: Mapped[str] = mapped_column(String(32), nullable=False)
    duration_min: Mapped[float] = mapped_column(Float, nullable=False)
    # Computed at save time from the MET table and the weight of that day.
    kcal_burned: Mapped[float] = mapped_column(Float, nullable=False)


class Food(Base):
    __tablename__ = "foods"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Italian name; search matches both names.
    name_it: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    usda_fdc_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    # Set only for custom foods.
    owner_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    kcal: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)

    @property
    def label(self) -> str:
        return self.name_it or self.name


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


class MealPreset(Base):
    """A recurring meal saved with its quantities, recalled with one tap."""

    __tablename__ = "meal_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    items: Mapped[list["MealPresetItem"]] = relationship(
        back_populates="preset", cascade="all, delete-orphan"
    )


class MealPresetItem(Base):
    __tablename__ = "meal_preset_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    preset_id: Mapped[int] = mapped_column(
        ForeignKey("meal_presets.id", ondelete="CASCADE"), nullable=False
    )
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"), nullable=False)
    grams: Mapped[float] = mapped_column(Float, nullable=False)

    preset: Mapped[MealPreset] = relationship(back_populates="items")
    food: Mapped[Food] = relationship()


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
