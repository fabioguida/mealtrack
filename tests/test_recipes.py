"""Composite dishes: the recipe file, the search and the one-tap rows."""

import pytest

from app.recipes import load_recipes, recipe_by_key, resolve, search_recipes
from scripts.import_foods import FILES, import_foods
from tests.plan_foods import load_recipe_foods


def test_recipe_file_is_consistent(db):
    recipes = load_recipes()
    assert len(recipes) >= 35
    keys = [r.key for r in recipes]
    assert len(keys) == len(set(keys))
    # Every ingredient exists in the CSVs (the loader asserts it).
    load_recipe_foods(db)
    for r in recipes:
        assert resolve(db, r) is not None, r.key
        assert all(g > 0 for _, _, g in r.ingredients)


def test_search_recipes():
    assert [r.name for r in search_recipes("pasta pomodoro")][0] == "Pasta al pomodoro"
    assert "Pasta al pomodoro" in [r.name for r in search_recipes("spaghetti pomodoro")]  # synonym
    assert len(search_recipes("pizza")) == 6  # capped; there are more
    assert search_recipes("carbonara")[0].key == "pasta-carbonara"
    assert search_recipes("p") == [] and search_recipes("xyz") == []


def test_recipe_in_search_results_and_rows(client, db, user):
    foods = load_recipe_foods(db)
    r = client.get("/alimenti/cerca", params={"q": "pasta al pomodoro"})
    assert 'data-test="recipe"' in r.text
    assert 'hx-get="/pasti/righe?piatto=pasta-pomodoro"' in r.text
    # Preferences mode offers foods only, never dishes.
    assert 'data-test="recipe"' not in client.get("/alimenti/cerca", params={"q": "pasta", "mode": "pref"}).text

    rows = client.get("/pasti/righe", params={"piatto": "pasta-pomodoro"})
    assert rows.status_code == 200
    recipe = recipe_by_key("pasta-pomodoro")
    assert rows.text.count('class="riga"') == len(recipe.ingredients)
    by_ref = {(f.source, f.source_id): f for f in foods}
    for source, source_id, grams in recipe.ingredients:
        food = by_ref[(source, source_id)]
        assert f'name="food_id" value="{food.id}"' in rows.text
        assert f'value="{grams:g}"' in rows.text
    assert "Pasta, cotta in acqua salata" in rows.text and "Passata di pomodoro" in rows.text

    assert client.get("/pasti/righe", params={"piatto": "non-esiste"}).status_code == 404


def test_recipe_with_missing_food_is_404(client, db, user):
    # Empty food table: the recipe cannot be resolved.
    assert client.get("/pasti/righe", params={"piatto": "pasta-pomodoro"}).status_code == 404


def test_imported_synonyms_make_shapes_searchable(client, db, user):
    import_foods(db, FILES)
    names = [line.split("</span>")[0] for line in client.get("/alimenti/cerca", params={"q": "spaghetti"}).text.split('<span class="nome">')[1:]]
    assert "Pasta, cotta in acqua salata (sale non iodato)" in names
    names = [line.split("</span>")[0] for line in client.get("/alimenti/cerca", params={"q": "petto di pollo"}).text.split('<span class="nome">')[1:]]
    assert names[0] == "Pollo, petto senza pelle, crudo"
