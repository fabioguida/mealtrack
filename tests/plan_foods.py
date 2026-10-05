"""Realistic per-100 g values for the foods of data/template_dishes.json, so the
planner tests do not need the USDA download. fdc_id: (name, kcal, protein, carbs, fat)."""

PLAN_FOODS = {
    171304: ("Yogurt, Greek, plain, whole milk", 97, 9.0, 3.98, 5.0),
    170894: ("Yogurt, Greek, plain, nonfat", 59, 10.2, 3.6, 0.4),
    173904: ("Cereals, oats, regular and quick, not fortified, dry", 379, 13.2, 67.7, 6.5),
    171711: ("Blueberries, raw", 57, 0.74, 14.5, 0.33),
    171688: ("Apples, raw, with skin", 52, 0.26, 13.8, 0.17),
    170567: ("Nuts, almonds", 579, 21.2, 21.6, 49.9),
    172688: ("Bread, whole-wheat, commercially prepared", 252, 12.3, 42.7, 3.5),
    171705: ("Avocados, raw, all commercial varieties", 160, 2.0, 8.53, 14.7),
    172187: ("Egg, whole, cooked, scrambled", 149, 9.99, 1.61, 11.0),
    169097: ("Oranges, raw, all commercial varieties", 47, 0.94, 11.8, 0.12),
    173944: ("Bananas, raw", 89, 1.09, 22.8, 0.33),
    171265: ("Milk, whole, 3.25% milkfat, with added vitamin D", 61, 3.15, 4.8, 3.25),
    169737: ("Pasta, cooked, enriched, without added salt", 158, 5.8, 30.9, 0.93),
    168910: ("Pasta, whole-wheat, cooked", 149, 5.99, 30.1, 1.71),
    173757: ("Chickpeas (garbanzo beans, bengal gram), mature seeds, cooked, boiled, without salt", 164, 8.86, 27.4, 2.59),
    172421: ("Lentils, mature seeds, cooked, boiled, without salt", 116, 9.02, 20.1, 0.38),
    169247: ("Lettuce, cos or romaine, raw", 17, 1.23, 3.29, 0.3),
    173694: ("Fish, sea bass, mixed species, cooked, dry heat", 124, 23.6, 0, 2.56),
    171956: ("Fish, cod, Atlantic, cooked, dry heat", 105, 22.8, 0, 0.86),
    175168: ("Fish, salmon, Atlantic, farmed, cooked, dry heat", 206, 22.1, 0, 12.4),
    173709: ("Fish, tuna, light, canned in water, drained solids", 86, 19.4, 0, 0.96),
    169704: ("Rice, brown, long-grain, cooked", 123, 2.74, 25.6, 0.97),
    169292: ("Squash, summer, zucchini, includes skin, cooked, boiled, drained, without salt", 15, 1.14, 2.69, 0.36),
    170457: ("Tomatoes, red, ripe, raw, year round average", 18, 0.88, 3.89, 0.2),
    171477: ("Chicken, broilers or fryers, breast, meat only, cooked, roasted", 165, 31.0, 0, 3.57),
    169288: ("Spinach, frozen, chopped or leaf, cooked, boiled, drained, without salt", 34, 4.01, 4.8, 0.87),
    168153: ("Kiwifruit, green, raw", 61, 1.14, 14.7, 0.52),
    169118: ("Pears, raw", 57, 0.36, 15.2, 0.14),
    170440: ("Potatoes, boiled, cooked without skin, flesh, without salt", 86, 1.71, 20.0, 0.1),
    169141: ("Beans, snap, green, cooked, boiled, drained, without salt", 35, 1.89, 7.88, 0.28),
    171975: ("Mollusks, clam, mixed species, cooked, moist heat", 148, 25.5, 5.13, 1.95),
    174217: ("Mollusks, mussel, blue, cooked, moist heat", 172, 23.8, 7.39, 4.48),
    175203: ("Beans, white, mature seeds, cooked, boiled, without salt", 139, 9.73, 25.1, 0.35),
    171413: ("Oil, olive, salad or cooking", 884, 0, 0, 100),
    321360: ("Tomatoes, grape, raw", 27, 0.83, 5.51, 0.63),
    171247: ("Cheese, parmesan, grated", 420, 28.4, 13.9, 27.8),
    170054: ("Tomato products, canned, sauce", 24, 1.2, 5.31, 0.3),
}


def load_plan_foods(db):
    from app.models import Food

    rows = [
        Food(name=name, source="usda", usda_fdc_id=fdc, kcal=k, protein_g=p, carbs_g=c, fat_g=f)
        for fdc, (name, k, p, c, f) in PLAN_FOODS.items()
    ]
    db.add_all(rows)
    db.commit()
    return rows
