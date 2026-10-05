"""The meal planner (HANDOVER.md feature 9), pure functions over plain data.

Per day: kcal of each meal = day target × the meal's share; a template dish
(fixed proportions) is scaled to that kcal; the day's protein is then checked
and, if short, protein ingredients are raised and carb ingredients lowered at
constant kcal; finally grams are rounded to practical values.

Dishes are picked by rules (open decision 8.3): weekly rotation with quotas
on the main meals (pasta exactly twice, fish and legumes at least twice),
filtered by the user's preferences, never the same dish within three days.
"""

import random
from dataclasses import dataclass, field
from datetime import date

ROLES = ("protein", "carb", "veg", "fat", "fruit", "mixed")
MAIN_MEALS = ("pranzo", "cena")
WEEK_MIN = {"pesce": 2, "legumi": 2, "pasta": 2}
WEEK_MAX = {"pasta": 2}
LIGHT_KCAL = 450          # below this a "light" dish is preferred
SCALE_MIN, SCALE_MAX = 0.5, 2.5
PROTEIN_TOL_G = 5.0
ROUND_G = 5
TRADABLE = ("carb", "fruit")   # roles that give up kcal to the protein ingredient
FLOOR_FRACTION, CEILING_FRACTION = 0.4, 2.5


@dataclass(frozen=True)
class Ingredient:
    food_id: int
    label: str
    grams: float               # base grams in the template
    role: str
    kcal: float                # per 100 g
    protein_g: float
    carbs_g: float
    fat_g: float
    unit_g: float | None = None


@dataclass(frozen=True)
class Dish:
    key: str
    name: str
    meal_types: tuple[str, ...]
    categories: tuple[str, ...]
    ingredients: tuple[Ingredient, ...]
    light: bool = False

    @property
    def base_kcal(self) -> float:
        return sum(i.kcal * i.grams / 100 for i in self.ingredients)


@dataclass
class PlannedItem:
    ingredient: Ingredient
    grams: float
    floor: float = 0.0         # carb items are not reduced below this
    ceiling: float = 1e9       # protein items are not raised above this

    def _v(self, per100: float) -> float:
        return per100 * self.grams / 100

    @property
    def kcal(self) -> float: return self._v(self.ingredient.kcal)
    @property
    def protein_g(self) -> float: return self._v(self.ingredient.protein_g)
    @property
    def carbs_g(self) -> float: return self._v(self.ingredient.carbs_g)
    @property
    def fat_g(self) -> float: return self._v(self.ingredient.fat_g)


@dataclass
class PlannedMeal:
    meal_type: str
    dish: Dish
    items: list[PlannedItem]

    @property
    def kcal(self) -> float: return sum(i.kcal for i in self.items)
    @property
    def protein_g(self) -> float: return sum(i.protein_g for i in self.items)
    @property
    def carbs_g(self) -> float: return sum(i.carbs_g for i in self.items)
    @property
    def fat_g(self) -> float: return sum(i.fat_g for i in self.items)


@dataclass(frozen=True)
class Slot:
    meal_type: str
    share: float               # fraction of the day's kcal target (not normalised)


@dataclass(frozen=True)
class DaySpec:
    day: date
    kcal_target: float
    protein_target_g: float
    slots: tuple[Slot, ...]


@dataclass
class PlannedDay:
    day: date
    meals: list[PlannedMeal]
    protein_target_g: float = 0.0

    @property
    def kcal(self) -> float: return sum(m.kcal for m in self.meals)
    @property
    def protein_g(self) -> float: return sum(m.protein_g for m in self.meals)
    @property
    def protein_short_g(self) -> float:
        """How far below the protein target the day stays after the fix (0 if met)."""
        return max(0.0, self.protein_target_g - self.protein_g)


@dataclass(frozen=True)
class Preferences:
    avoid_categories: frozenset[str] = frozenset()
    avoid_foods: frozenset[int] = frozenset()
    like_categories: frozenset[str] = frozenset()
    like_foods: frozenset[int] = frozenset()

    def avoids(self, dish: Dish) -> bool:
        return bool(set(dish.categories) & self.avoid_categories) or any(
            i.food_id in self.avoid_foods for i in dish.ingredients
        )


# --- step 1: kcal per meal -------------------------------------------------

def meal_kcal(day_target: float, share: float) -> float:
    return day_target * share


# --- step 2: scale a dish --------------------------------------------------

def scale_dish(dish: Dish, target_kcal: float) -> list[PlannedItem]:
    """Keep the proportions, hit the kcal (within the sanity clamp)."""
    base = dish.base_kcal
    factor = target_kcal / base if base > 0 else 1.0
    factor = min(SCALE_MAX, max(SCALE_MIN, factor))
    items = []
    for ing in dish.ingredients:
        g = ing.grams * factor
        items.append(PlannedItem(ing, g, floor=FLOOR_FRACTION * g, ceiling=CEILING_FRACTION * g))
    return items


def protein_density(dish: Dish) -> float:
    """Grams of protein per 100 kcal of the dish as templated."""
    kcal = dish.base_kcal
    protein = sum(i.protein_g * i.grams / 100 for i in dish.ingredients)
    return 100 * protein / kcal if kcal > 0 else 0.0


# --- step 3: protein check -------------------------------------------------

def fix_protein(meals: list[PlannedMeal], protein_target_g: float, passes: int = 8) -> None:
    """Raise protein ingredients and lower carb (and fruit) ingredients, meal by
    meal, at constant kcal, until the day's protein is within PROTEIN_TOL_G of
    target or no ingredient can move further within its bounds. With low-density
    protein sources (legumes, milk) the target may stay out of reach: the day
    is then reported short rather than distorted."""
    for _ in range(passes):
        deficit = protein_target_g - sum(m.protein_g for m in meals)
        if deficit <= PROTEIN_TOL_G:
            return
        candidates = []
        for m in meals:
            prot = [i for i in m.items if i.ingredient.role == "protein" and i.grams < i.ceiling]
            carbs = [i for i in m.items if i.ingredient.role in TRADABLE and i.grams > i.floor]
            if prot and carbs:
                p = max(prot, key=lambda i: i.ingredient.protein_g / max(i.ingredient.kcal, 1))
                candidates.append((p.ingredient.protein_g / max(p.ingredient.kcal, 1), m, p, carbs))
        if not candidates:
            return
        _, meal, p, carbs = max(candidates, key=lambda c: c[0])
        per_g_protein = p.ingredient.protein_g / 100
        if per_g_protein <= 0:
            return
        add_g = min(deficit / per_g_protein, p.ceiling - p.grams)
        add_kcal = add_g * p.ingredient.kcal / 100
        removable = sum((c.grams - c.floor) * c.ingredient.kcal / 100 for c in carbs)
        take = min(add_kcal, removable)
        if take <= 0:
            # Nothing to trade in this meal: block it and try the next pass.
            p.ceiling = p.grams
            continue
        add_g *= take / add_kcal if add_kcal > 0 else 0
        p.grams += add_g
        for c in carbs:
            share = (c.grams - c.floor) * c.ingredient.kcal / 100 / removable
            c.grams -= take * share / (c.ingredient.kcal / 100)


# --- step 4: practical grams ----------------------------------------------

def round_practical(meals: list[PlannedMeal]) -> None:
    """Whole units for eggs, fruit, bread slices; multiples of 5 g otherwise.
    The kcal drift of the unit rounding is taken back on the dish's biggest
    free ingredient (within its bounds) before that one is rounded too."""
    for m in meals:
        before = m.kcal
        for i in m.items:
            if i.ingredient.unit_g:
                i.grams = max(1, round(i.grams / i.ingredient.unit_g)) * i.ingredient.unit_g
        free = [i for i in m.items if not i.ingredient.unit_g and i.ingredient.kcal > 0]
        drift = m.kcal - before
        if free and drift:
            big = max(free, key=lambda x: x.kcal)
            per_g = big.ingredient.kcal / 100
            big.grams = min(big.ceiling, max(big.floor, big.grams - drift / per_g))
        for i in free:
            i.grams = max(ROUND_G, ROUND_G * round(i.grams / ROUND_G))


# --- dish selection --------------------------------------------------------

def pick_dish(
    dishes: list[Dish],
    slot: Slot,
    kcal: float,
    day: date,
    week_counts: dict[str, int],
    recent: dict[str, date],
    prefs: Preferences,
    rng: random.Random,
) -> Dish | None:
    best, best_score = None, None
    main = slot.meal_type in MAIN_MEALS
    for d in dishes:
        if slot.meal_type not in d.meal_types or prefs.avoids(d):
            continue
        if main and any(week_counts.get(c, 0) >= WEEK_MAX[c] for c in d.categories if c in WEEK_MAX):
            continue
        score = rng.random()
        for c in d.categories:
            if main and c in WEEK_MIN and week_counts.get(c, 0) < WEEK_MIN[c]:
                score += 3
            if c in prefs.like_categories:
                score += 2
        if any(i.food_id in prefs.like_foods for i in d.ingredients):
            score += 2
        last = recent.get(d.key)
        if last is not None:
            gap = (day - last).days
            if gap < 3:
                score -= 5
            elif gap < 7:
                score -= 2
        if d.light:
            score += 2 if kcal < LIGHT_KCAL else -1
        elif kcal < LIGHT_KCAL:
            score -= 1
        # Tie-break toward protein-dense dishes (fish ≈ +1.9, pasta e ceci ≈ +0.5),
        # below the quota and recency terms so the rotation still rules.
        score += protein_density(d) / 10
        if best_score is None or score > best_score:
            best, best_score = d, score
    return best


# --- the whole period ------------------------------------------------------

def plan_period(
    dishes: list[Dish], days: list[DaySpec], prefs: Preferences, seed: str = ""
) -> list[PlannedDay]:
    rng = random.Random(seed)
    recent: dict[str, date] = {}
    out: list[PlannedDay] = []
    week_counts: dict[str, int] = {}
    week_start = days[0].day if days else None
    for spec in days:
        if (spec.day - week_start).days >= 7:
            week_start, week_counts = spec.day, {}
        meals: list[PlannedMeal] = []
        for slot in spec.slots:
            kcal = meal_kcal(spec.kcal_target, slot.share)
            dish = pick_dish(dishes, slot, kcal, spec.day, week_counts, recent, prefs, rng)
            if dish is None:
                continue
            recent[dish.key] = spec.day
            if slot.meal_type in MAIN_MEALS:
                for c in dish.categories:
                    week_counts[c] = week_counts.get(c, 0) + 1
            meals.append(PlannedMeal(slot.meal_type, dish, scale_dish(dish, kcal)))
        fix_protein(meals, spec.protein_target_g)
        round_practical(meals)
        out.append(PlannedDay(spec.day, meals, spec.protein_target_g))
    return out
