"""The planner's pure functions, with the author's schedule from PIANO_ALIMENTARE.md."""

from collections import Counter
from datetime import date, timedelta

import pytest

from app.calc.planner import (
    SCALE_MAX,
    SCALE_MIN,
    DaySpec,
    PlannedMeal,
    Preferences,
    Slot,
    fix_protein,
    meal_kcal,
    plan_period,
    round_practical,
    scale_dish,
)
from app.plan_service import template_dishes
from tests.plan_foods import load_plan_foods

KCAL, PROTEIN = 1900.0, 127.5


def author_slots(day: date) -> tuple[Slot, ...]:
    dow = day.weekday()
    if dow <= 3:   # Mon–Thu: breakfast, lunch, snack, no dinner
        return (Slot("colazione", 0.30), Slot("pranzo", 0.45), Slot("spezzafame", 0.25))
    if dow <= 5:   # Fri–Sat: light lunch, no snack, dinner out
        return (Slot("colazione", 0.30), Slot("pranzo", 0.25))
    return (Slot("colazione", 0.30), Slot("pranzo", 0.70))  # Sunday family lunch


def author_days(start=date(2026, 10, 5), weeks=2):
    return [DaySpec(start + timedelta(days=n), KCAL, PROTEIN, author_slots(start + timedelta(days=n))) for n in range(7 * weeks)]


@pytest.fixture
def dishes(db):
    load_plan_foods(db)
    dishes, skipped = template_dishes(db)
    assert skipped == []
    return dishes


def test_meal_kcal_shares():
    assert [meal_kcal(KCAL, s) for s in (0.30, 0.45, 0.25)] == [570, 855, 475]


def test_scale_dish_keeps_proportions(dishes):
    dish = next(d for d in dishes if d.key == "pasta-ceci")
    base = dish.base_kcal
    items = scale_dish(dish, 855)
    factor = 855 / base
    for item in items:
        assert item.grams == pytest.approx(item.ingredient.grams * factor)
    assert sum(i.kcal for i in items) == pytest.approx(855)


def test_scale_is_clamped(dishes):
    dish = next(d for d in dishes if d.key == "mela-mandorle")
    assert sum(i.kcal for i in scale_dish(dish, 5000)) == pytest.approx(2.5 * dish.base_kcal)
    assert sum(i.kcal for i in scale_dish(dish, 10)) == pytest.approx(0.5 * dish.base_kcal)


def test_fix_protein_hits_target_at_constant_kcal(dishes):
    by_key = {d.key: d for d in dishes}
    meals = [
        PlannedMeal("colazione", by_key["porridge-banana"], scale_dish(by_key["porridge-banana"], 570)),
        PlannedMeal("pranzo", by_key["pasta-ceci"], scale_dish(by_key["pasta-ceci"], 855)),
        PlannedMeal("spezzafame", by_key["yogurt-kiwi"], scale_dish(by_key["yogurt-kiwi"], 475)),
    ]
    kcal_before = sum(m.kcal for m in meals)
    before = sum(m.protein_g for m in meals)
    assert before < PROTEIN - 5
    fix_protein(meals, PROTEIN)
    after = sum(m.protein_g for m in meals)
    # Legume / milk based dishes cannot reach 127.5 g without being distorted:
    # the fix moves a long way toward the target, at constant kcal, within bounds.
    assert after > before + 15
    assert sum(m.kcal for m in meals) == pytest.approx(kcal_before, rel=0.03)
    for m in meals:
        for i in m.items:
            assert i.floor - 1e-6 <= i.grams <= i.ceiling + 1e-6

    # With dense protein sources the target is reached.
    meals = [
        PlannedMeal("colazione", by_key["avocado-toast-uova"], scale_dish(by_key["avocado-toast-uova"], 570)),
        PlannedMeal("pranzo", by_key["orata-riso-zucchine"], scale_dish(by_key["orata-riso-zucchine"], 855)),
        PlannedMeal("spezzafame", by_key["yogurt-kiwi"], scale_dish(by_key["yogurt-kiwi"], 475)),
    ]
    kcal_before = sum(m.kcal for m in meals)
    fix_protein(meals, PROTEIN)
    assert sum(m.protein_g for m in meals) >= PROTEIN - 5
    assert sum(m.kcal for m in meals) == pytest.approx(kcal_before, rel=0.03)


def test_round_practical(dishes):
    dish = next(d for d in dishes if d.key == "avocado-toast-uova")
    meals = [PlannedMeal("colazione", dish, scale_dish(dish, 570))]
    kcal_before = meals[0].kcal
    round_practical(meals)
    for i in meals[0].items:
        if i.ingredient.unit_g:
            assert i.grams % i.ingredient.unit_g == 0 and i.grams >= i.ingredient.unit_g
        else:
            assert i.grams % 5 == 0
    eggs = next(i for i in meals[0].items if i.ingredient.unit_g == 55)
    assert eggs.grams / 55 == int(eggs.grams / 55)  # whole eggs
    assert abs(meals[0].kcal - kcal_before) / kcal_before < 0.05


def test_two_weeks_for_the_author(dishes):
    days = plan_period(dishes, author_days(), Preferences(), seed="test")
    assert len(days) == 14
    for d in days:
        types = [m.meal_type for m in d.meals]
        dow = d.day.weekday()
        assert "cena" not in types
        if dow in (4, 5):
            assert "spezzafame" not in types and types == ["colazione", "pranzo"]
        elif dow == 6:
            assert types == ["colazione", "pranzo"]
        else:
            assert types == ["colazione", "pranzo", "spezzafame"]
        # Each meal within 6 % of its share (protein fix at constant kcal, rounding
        # compensated), except where the scaling clamp caps a huge slot such as
        # the Sunday family lunch at 70 % of the day.
        shares = {s.meal_type: s.share for s in author_slots(d.day)}
        for m in d.meals:
            wanted = KCAL * shares[m.meal_type]
            expected = min(max(wanted, SCALE_MIN * m.dish.base_kcal), SCALE_MAX * m.dish.base_kcal)
            assert abs(m.kcal - expected) / expected < 0.06, (d.day, m.dish.key, m.kcal, expected)
    # Pasta exactly twice a week on the main meals; fish and legumes at least twice.
    for week in (days[:7], days[7:]):
        cats = Counter(c for d in week for m in d.meals if m.meal_type == "pranzo" for c in m.dish.categories)
        assert cats["pasta"] == 2
        assert cats["pesce"] >= 2 and cats["legumi"] >= 2
    # Never the same dish within three days.
    last = {}
    for d in days:
        for m in d.meals:
            if m.dish.key in last:
                assert (d.day - last[m.dish.key]).days >= 3
            last[m.dish.key] = d.day


def test_protein_on_full_days_is_reported_honestly(dishes):
    days = plan_period(dishes, author_days(), Preferences(), seed="test")
    full = [d for d in days if d.day.weekday() <= 3]
    # Most full days reach the target or get close; any shortfall is exposed, not hidden.
    for d in full:
        assert d.protein_short_g == pytest.approx(max(0.0, PROTEIN - d.protein_g))
    assert sum(1 for d in full if d.protein_short_g <= 10) >= len(full) // 2, [round(d.protein_g) for d in full]


def test_preferences_exclude_and_favour(dishes):
    clams = next(i.food_id for d in dishes if d.key == "spaghetti-vongole" for i in d.ingredients if "clam" in i.label)
    prefs = Preferences(avoid_categories=frozenset({"carne"}), avoid_foods=frozenset({clams}))
    days = plan_period(dishes, author_days(), prefs, seed="test")
    for d in days:
        for m in d.meals:
            assert "carne" not in m.dish.categories
            assert all(i.ingredient.food_id != clams for i in m.items)

    liked = Preferences(like_categories=frozenset({"uova"}))
    n_eggs = sum(1 for d in plan_period(dishes, author_days(), liked, seed="test") for m in d.meals if "uova" in m.dish.categories)
    n_plain = sum(1 for d in days for m in d.meals if "uova" in m.dish.categories)
    assert n_eggs >= n_plain


def test_same_seed_same_plan(dishes):
    a = plan_period(dishes, author_days(), Preferences(), seed="x")
    b = plan_period(dishes, author_days(), Preferences(), seed="x")
    assert [[m.dish.key for m in d.meals] for d in a] == [[m.dish.key for m in d.meals] for d in b]
