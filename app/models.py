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
    # The user's choice: kg to lose per week (0 = maintain). Deficit and protein
    # level are derived from it (app/calc/targets.py), not entered.
    kg_per_week: Mapped[float | None] = mapped_column(Float)
    # Derived at save time and kept for the record; older rows may predate kg_per_week.
    goal: Mapped[str] = mapped_column(String(16), nullable=False, default="dimagrire")
    deficit_kcal: Mapped[float] = mapped_column(Float, nullable=False, default=500)
    protein_g_per_kg: Mapped[float] = mapped_column(Float, nullable=False, default=1.5)

    @property
    def pace(self) -> float:
        if self.kg_per_week is not None:
            return self.kg_per_week
        return 0.0 if self.goal == "mantenere" else self.deficit_kcal * 7 / 7700
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


class EatingSchedule(Base):
    """One row per weekday and meal the user eats: time and share of the day's kcal."""

    __tablename__ = "eating_schedules"
    __table_args__ = (UniqueConstraint("user_id", "day_of_week", "meal_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0 = Monday
    meal_type: Mapped[str] = mapped_column(String(12), nullable=False)
    time: Mapped[str | None] = mapped_column(String(5))  # "07:30"
    share: Mapped[float] = mapped_column(Float, nullable=False)  # fraction of the day's kcal


class FoodPreference(Base):
    __tablename__ = "food_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    food_id: Mapped[int | None] = mapped_column(ForeignKey("foods.id"))
    category: Mapped[str | None] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(8), nullable=False)  # like / avoid

    food: Mapped["Food | None"] = relationship()


class MealPlan(Base):
    __tablename__ = "meal_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    kcal_target: Mapped[float] = mapped_column(Float, nullable=False)
    protein_target_g: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    items: Mapped[list["MealPlanItem"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan", order_by="MealPlanItem.id"
    )


class MealPlanItem(Base):
    __tablename__ = "meal_plan_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("meal_plans.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    meal_type: Mapped[str] = mapped_column(String(12), nullable=False)
    dish: Mapped[str] = mapped_column(String(120), nullable=False)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id"), nullable=False)
    grams: Mapped[float] = mapped_column(Float, nullable=False)
    kcal: Mapped[float] = mapped_column(Float, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)

    plan: Mapped[MealPlan] = relationship(back_populates="items")
    food: Mapped["Food"] = relationship()


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
