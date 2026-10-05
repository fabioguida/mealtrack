"""Database glue for the planner: dishes, schedule, preferences, plans."""

import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.calc.planner import DaySpec, Dish, Ingredient, PlannedDay, Preferences, Slot, plan_period
from app.config import PROJECT_ROOT
from app.models import (
    MEAL_TYPES,
    EatingSchedule,
    Food,
    FoodPreference,
    MealPlan,
    MealPlanItem,
    MealPreset,
    MealPresetItem,
    User,
)
from app.services import targets_for

TEMPLATE_FILE = PROJECT_ROOT / "data" / "template_dishes.json"
CATEGORIES = {
    "pasta": "Pasta",
    "pesce": "Pesce",
    "carne": "Carne",
    "legumi": "Legumi",
    "uova": "Uova",
    "latticini": "Latticini",
    "frutta_secca": "Frutta secca",
}
DEFAULT_SCHEDULE = {  # a plain four-meal day; each user then sets their own
    "colazione": ("07:30", 0.25),
    "pranzo": ("13:00", 0.35),
    "spezzafame": ("16:30", 0.10),
    "cena": ("20:00", 0.30),
}


def _ingredient(food: Food, grams: float, role: str, unit_g: float | None) -> Ingredient:
    return Ingredient(
        food_id=food.id, label=food.label, grams=grams, role=role,
        kcal=food.kcal, protein_g=food.protein_g, carbs_g=food.carbs_g, fat_g=food.fat_g,
        unit_g=unit_g,
    )


def template_dishes(db: Session, path: Path = TEMPLATE_FILE) -> tuple[list[Dish], list[str]]:
    """Dishes from the JSON whose ingredients are all in the foods table."""
    data = json.loads(path.read_text(encoding="utf-8"))["dishes"]
    ids = {i["fdc_id"] for d in data for i in d["ingredients"]}
    foods = {f.usda_fdc_id: f for f in db.scalars(select(Food).where(Food.usda_fdc_id.in_(ids)))}
    dishes, skipped = [], []
    for d in data:
        try:
            ings = tuple(
                _ingredient(foods[i["fdc_id"]], i["grams"], i["role"], i.get("unit_g"))
                for i in d["ingredients"]
            )
        except KeyError:
            skipped.append(d["name"])
            continue
        dishes.append(Dish(d["key"], d["name"], tuple(d["meal_types"]), tuple(d["categories"]), ings, d.get("light", False)))
    return dishes, skipped


def preset_dishes(db: Session, user: User) -> list[Dish]:
    """The user's presets as dishes (fixed proportions, no roles to rebalance)."""
    presets = db.scalars(
        select(MealPreset)
        .options(selectinload(MealPreset.items).selectinload(MealPresetItem.food))
        .where(MealPreset.user_id == user.id)
    ).all()
    out = []
    for p in presets:
        if not p.items:
            continue
        ings = tuple(_ingredient(i.food, i.grams, "mixed", None) for i in p.items)
        out.append(Dish(f"preset-{p.id}", p.name, tuple(MEAL_TYPES), (), ings))
    return out


def schedule_for(db: Session, user: User) -> dict[int, list[EatingSchedule]]:
    rows = db.scalars(select(EatingSchedule).where(EatingSchedule.user_id == user.id)).all()
    by_day: dict[int, list[EatingSchedule]] = defaultdict(list)
    for r in rows:
        by_day[r.day_of_week].append(r)
    if not rows:
        for dow in range(7):
            for mt, (t, share) in DEFAULT_SCHEDULE.items():
                by_day[dow].append(EatingSchedule(user_id=user.id, day_of_week=dow, meal_type=mt, time=t, share=share))
    order = {mt: i for i, mt in enumerate(MEAL_TYPES)}
    for dow in by_day:
        by_day[dow].sort(key=lambda r: order[r.meal_type])
    return by_day


def preferences_for(db: Session, user: User) -> Preferences:
    rows = db.scalars(select(FoodPreference).where(FoodPreference.user_id == user.id)).all()
    return Preferences(
        avoid_categories=frozenset(r.category for r in rows if r.kind == "avoid" and r.category),
        avoid_foods=frozenset(r.food_id for r in rows if r.kind == "avoid" and r.food_id),
        like_categories=frozenset(r.category for r in rows if r.kind == "like" and r.category),
        like_foods=frozenset(r.food_id for r in rows if r.kind == "like" and r.food_id),
    )


def day_specs(db: Session, user: User, start: date, weeks: int) -> list[DaySpec] | None:
    targets = targets_for(db, user, start)
    if targets is None:
        return None
    schedule = schedule_for(db, user)
    specs = []
    for n in range(7 * weeks):
        day = start + timedelta(days=n)
        slots = tuple(Slot(r.meal_type, r.share) for r in schedule.get(day.weekday(), []))
        specs.append(DaySpec(day, targets.kcal, targets.protein_g, slots))
    return specs


def generate_plan(db: Session, user: User, start: date, weeks: int = 2) -> MealPlan | None:
    """Plan `weeks` weeks from `start`; replaces the user's previous plans."""
    specs = day_specs(db, user, start, weeks)
    if specs is None:
        return None
    dishes, _ = template_dishes(db)
    dishes += preset_dishes(db, user)
    days = plan_period(dishes, specs, preferences_for(db, user), seed=f"{user.id}-{start}")

    for old in db.scalars(select(MealPlan).where(MealPlan.user_id == user.id)):
        db.delete(old)
    plan = MealPlan(
        user_id=user.id, start_date=start, weeks=weeks,
        kcal_target=specs[0].kcal_target, protein_target_g=specs[0].protein_target_g,
    )
    for d in days:
        for m in d.meals:
            for i in m.items:
                plan.items.append(MealPlanItem(
                    date=d.day, meal_type=m.meal_type, dish=m.dish.name, food_id=i.ingredient.food_id,
                    grams=i.grams, kcal=i.kcal, protein_g=i.protein_g, carbs_g=i.carbs_g, fat_g=i.fat_g,
                ))
    db.add(plan)
    db.commit()
    return plan


def current_plan(db: Session, user: User) -> MealPlan | None:
    return db.scalar(
        select(MealPlan)
        .options(selectinload(MealPlan.items).selectinload(MealPlanItem.food))
        .where(MealPlan.user_id == user.id)
        .order_by(MealPlan.created_at.desc(), MealPlan.id.desc())
        .limit(1)
    )


def plan_is_stale(db: Session, user: User, plan: MealPlan, tolerance: float = 0.05) -> bool:
    """True when the target moved by more than `tolerance` since the plan was made."""
    targets = targets_for(db, user, date.today())
    if targets is None or plan.kcal_target <= 0:
        return False
    return abs(targets.kcal - plan.kcal_target) / plan.kcal_target > tolerance


def plan_days(plan: MealPlan) -> list[dict]:
    """The plan grouped by day and meal, for the page and the suggestions."""
    by_day: dict[date, dict[str, dict]] = defaultdict(dict)
    for i in plan.items:
        meal = by_day[i.date].setdefault(i.meal_type, {"dish": i.dish, "items": [], "kcal": 0.0, "protein_g": 0.0})
        meal["items"].append(i)
        meal["kcal"] += i.kcal
        meal["protein_g"] += i.protein_g
    order = {mt: n for n, mt in enumerate(MEAL_TYPES)}
    out = []
    for day in sorted(by_day):
        meals = sorted(by_day[day].items(), key=lambda kv: order[kv[0]])
        out.append({
            "day": day,
            "meals": [{"meal_type": mt, **m} for mt, m in meals],
            "kcal": sum(m["kcal"] for _, m in meals),
            "protein_g": sum(m["protein_g"] for _, m in meals),
        })
    return out


def suggestions_for(db: Session, user: User, day: date, logged_types: set[str]) -> list[dict]:
    """Planned meals of `day` whose type has not been logged yet."""
    plan = current_plan(db, user)
    if plan is None:
        return []
    for d in plan_days(plan):
        if d["day"] == day:
            return [m for m in d["meals"] if m["meal_type"] not in logged_types]
    return []
