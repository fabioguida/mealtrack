"""The shopping list: what the plan's meals need over a range of days,
aggregated per food and rounded to what one actually buys."""

import math
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.models import Food, User
from app.plan_service import current_plan
from app.textsearch import normalize

# (words in the food's name, unit label singular/plural, grams per unit)
BUY_UNITS = [
    (("uovo", "uova"), ("uovo", "uova"), 55),
    (("mela",), ("mela", "mele"), 180),
    (("pera",), ("pera", "pere"), 180),
    (("arancia",), ("arancia", "arance"), 130),
    (("banana",), ("banana", "banane"), 120),
    (("kiwi",), ("kiwi", "kiwi"), 75),
    (("pesca",), ("pesca", "pesche"), 150),
    (("avocado",), ("avocado", "avocado"), 150),
    (("yogurt greco",), ("vasetto", "vasetti"), 170),
    (("yogurt",), ("vasetto", "vasetti"), 125),
    (("mozzarella",), ("mozzarella", "mozzarelle"), 125),
    (("tonno in salamoia", "tonno sott", "tonno in scatola", "tonno al naturale"), ("scatoletta", "scatolette"), 80),
]

GROUPS = [  # (category prefixes, group name) — first match wins; "Dispensa" otherwise
    (("Frutta", "Verdure", "Noci"), "Frutta e verdura"),
    (("Carne", "Pesce", "Prodotti carnei"), "Carne e pesce"),
    (("Latte", "Uova"), "Latticini e uova"),
    (("Pane", "Prodotti a base di cereali"), "Pane, pasta, riso e legumi"),
]
GROUP_ORDER = [g for _, g in GROUPS] + ["Dispensa"]


@dataclass(frozen=True)
class ShoppingItem:
    food: Food
    grams: float
    display: str      # "2 uova", "pasta 200 g"


@dataclass(frozen=True)
class ShoppingGroup:
    name: str
    items: list[ShoppingItem]


def group_of(food: Food) -> str:
    cat = food.category or ""
    for prefixes, name in GROUPS:
        if cat.startswith(prefixes):
            return name
    return "Dispensa"


def buy_quantity(food: Food, grams: float) -> str:
    text = " " + normalize(f"{food.name} {food.synonyms or ''}") + " "
    for words, (one, many), unit_g in BUY_UNITS:
        if any(f" {w}" in text for w in words):
            n = max(1, math.ceil(grams / unit_g - 0.1))  # 1.9 units → 2, 2.05 → 2
            return f"{n} {one if n == 1 else many}"
    step = 10 if grams < 100 else 50
    return f"{int(math.ceil(grams / step) * step)} g"


def shopping_list(db: Session, user: User, start: date, end: date) -> list[ShoppingGroup]:
    """Foods needed from `start` to `end` inclusive, from the current plan."""
    plan = current_plan(db, user)
    if plan is None:
        return []
    totals: dict[int, float] = {}
    foods: dict[int, Food] = {}
    for i in plan.items:
        if start <= i.date <= end:
            totals[i.food_id] = totals.get(i.food_id, 0.0) + i.grams
            foods[i.food_id] = i.food
    groups: dict[str, list[ShoppingItem]] = {}
    for food_id, grams in totals.items():
        food = foods[food_id]
        groups.setdefault(group_of(food), []).append(ShoppingItem(food, grams, buy_quantity(food, grams)))
    out = []
    for name in GROUP_ORDER:
        if name in groups:
            out.append(ShoppingGroup(name, sorted(groups[name], key=lambda it: it.food.name)))
    return out
