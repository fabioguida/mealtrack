# Development plan — Meal Tracker

Date: 5 October 2026. Companion to [HANDOVER.md](HANDOVER.md), which remains the binding spec. Where this plan and the handover disagree, the handover wins.

This plan turns the handover's build order into nine phases. Each phase has a fixed scope, the files it touches, the automated tests that must pass, the manual checks the user performs, and a definition of done. A phase is closed only when the user has checked it. Nothing from a later phase is started early.

---

## 0. Ground rules

**Working method.** One phase at a time, each split into steps small enough to be reviewed in one sitting. Before each step the file layout and the data model changes are proposed in chat; code is written only after the go. Every step ends with a passing test run and a commit.

**Stack (decided).** Python 3.11, FastAPI, SQLAlchemy 2.0 with SQLite, Jinja2 templates, HTMX from a local copy (no CDN, so the app works without internet and matches the website's self-hosted assets). Tests with pytest and FastAPI's `TestClient` (httpx). No JavaScript framework.

**Language.** Interface, templates and user-facing messages in Italian. Code, identifiers, commit messages and this plan in English.

**Project layout (target state at the end of phase 9).**

```
APP_MEALTRACK/
  app/
    main.py            FastAPI app, router registration, static files
    config.py          settings from environment (.env): DB path, secret key, S3 bucket, API keys
    db.py              engine, session factory, `get_db` dependency
    models.py          SQLAlchemy tables
    schemas.py         Pydantic request/response models
    auth.py            password hashing, session cookie, `current_user` dependency
    calc/
      nutrition.py     meal totals from (food, grams) lists
      targets.py       Mifflin-St Jeor, TDEE, daily targets, protein target
      activity.py      MET table and kcal burned
      trend.py         weekly averages and feedback
      planner.py       meal plan generation (phase 7)
    routers/           one file per feature: meals, balance, auth, profile, weights, workouts, presets, plan, photos
    templates/         Jinja2; base.html plus one folder per feature; partials/ for HTMX fragments
    static/            css/, js/htmx.min.js, img/
  scripts/
    init_db.py         create tables, seed first user
    import_usda.py     USDA CSV → foods table
    backup_db.sh       SQLite .backup + upload to S3 (phase 9)
  tests/
    conftest.py        in-memory SQLite, app fixture, logged-in client fixture
    test_<feature>.py  one per phase
  deploy/              systemd unit, nginx config, cron entry, AWS notes (phase 9)
  data/usda/           raw USDA CSV downloads, git-ignored
  requirements.txt
  .env.example
  HANDOVER.md  ARCHITECTURE.md  PLAN.md  PIANO_ALIMENTARE.md  README.md
```

**Test tooling.**

- `pytest` runs the whole suite in under a minute, with no network and no files written outside a temp directory.
- `tests/conftest.py` builds an in-memory SQLite database per test, overrides `get_db`, and provides a `client` (anonymous) and a `user_client` (logged in as a seeded user) fixture.
- HTML routes are tested by status code and by the presence of key Italian strings or `data-test` attributes in the response. HTMX partials are tested with the `HX-Request` header set.
- Calculation modules (`app/calc/`) are pure functions and are tested with hand-checked numbers listed in each phase.
- A GitHub Actions workflow (`.github/workflows/test.yml`) runs `pytest` on every push. Added in phase 1 so every later phase is covered.

**Definition of done (every phase).** All automated tests pass locally and in CI; the manual checklist for the phase has been run by the user; the code is committed and pushed; no new open decision has been implemented without being settled first.

---

## 1. Data model and USDA import

Handover step 1. No HTML yet.

### Scope

- `app/db.py`, `app/models.py`, `app/config.py`, `app/main.py` with a `/health` route returning `{"status": "ok"}`.
- Tables created in this phase: `users`, `foods`, `meals`, `meal_items`. The other tables are added by the phase that needs them, so each schema change is reviewed with its feature.
- `scripts/init_db.py`: creates the tables and seeds the first user (the author) with an empty password hash; auth comes in phase 4.
- `scripts/import_usda.py`: reads the FoodData Central CSV download and fills `foods` with `source = 'usda'`.
- Virtual environment `.venv/` in the project, `requirements.txt` pinned.
- CI workflow.

### Data model

| Table | Columns |
| --- | --- |
| `users` | `id`, `email` (unique, not null), `password_hash` (nullable until phase 4), `created_at` |
| `foods` | `id`, `name`, `source` (`usda`/`custom`), `usda_fdc_id` (nullable, unique), `owner_user_id` (nullable FK, custom foods only), `kcal`, `protein_g`, `carbs_g`, `fat_g` — all per 100 g, not null |
| `meals` | `id`, `user_id` (FK), `datetime`, `meal_type` (`colazione`/`pranzo`/`spezzafame`/`cena`), `photo_url` (nullable), `input_method` (`manual`/`photo`/`preset`) |
| `meal_items` | `id`, `meal_id` (FK, cascade delete), `food_id` (FK), `grams`, `kcal`, `protein_g`, `carbs_g`, `fat_g` (computed at save time) |

`meal_items` stores computed values so that editing a food later does not silently rewrite past meals.

### USDA import rules

- Datasets: **SR Legacy** and **Foundation Foods** only. **Branded** is excluded (over 400,000 packaged products, mostly US brands).
- Nutrients: energy kcal (nutrient id 1008), protein (1003), total fat (1004), carbohydrate by difference (1005). Foundation foods missing 1008 use the Atwater general-factor energy (2047) and, failing that, are skipped and counted in the import log.
- Names are kept in English in a `name` column; an optional `name_it` column (nullable) is added now so that Italian aliases can be filled by hand later without a migration. Search in later phases matches both.
- The import is idempotent: re-running it updates rows by `usda_fdc_id` instead of duplicating them.

### Tests

- `test_models.py`: create a food, a meal with two items, read back; deleting the meal deletes its items; `foods.usda_fdc_id` uniqueness is enforced.
- `test_import_usda.py`: run the importer on a 20-row fixture CSV set shipped in `tests/fixtures/usda/`; assert row count, one spot-checked food (e.g. fdc_id 170148 cooked spaghetti: ~158 kcal, 5.8 g protein per 100 g — verify the exact fixture values against the download), and that a second run leaves the row count unchanged.
- `test_health.py`: `GET /health` returns 200.

### Manual checks

- `python scripts/init_db.py` then `python scripts/import_usda.py data/usda/` on the real download completes and prints the number of foods imported and skipped.
- `sqlite3 mealtrack.db "select count(*) from foods"` is in the expected range (~8,000–9,000).

### Decisions needed before starting

- None blocking. Open: whether to also add an Italian name column now (proposed above: yes, nullable).

---

## 2. Manual meal entry and the calculation engine

Handover step 2. First pages, first HTMX.

### Scope

- `app/calc/nutrition.py`: `meal_totals(items: list[tuple[Food, grams]]) -> Totals` and `item_values(food, grams)`.
- Routes: `GET /pasti/nuovo` (form), `GET /alimenti/cerca?q=` (HTMX partial returning a list of matching foods), `POST /pasti` (create meal), `GET /pasti/{id}` (view), `GET /pasti/{id}/modifica` and `POST /pasti/{id}` (edit), `POST /pasti/{id}/elimina`.
- Custom foods: `GET /alimenti/nuovo`, `POST /alimenti` for Italian dishes missing from USDA, owned by the user.
- Templates: `base.html` following the Vere Novo site conventions (see phase 3 note), meal form with a food search box, a growing list of rows (food, grams), running totals updated by HTMX on each change.
- Until phase 4 every request acts as the seeded first user (`user_id = 1`) through a placeholder dependency that phase 4 replaces.

### Tests

- `test_nutrition.py`, pure function: food at 371 kcal / 13.0 g protein / 74.7 g carbs / 1.5 g fat per 100 g at 140 g → 519.4 kcal, 18.2 g, 104.58 g, 2.1 g; zero grams → zeros; totals of two items equal the sum; results rounded to 1 decimal only at presentation, not in the engine.
- `test_meals.py`: form page loads (200, contains "Nuovo pasto"); search partial returns foods matching "spaghetti" and nothing for "zzzz"; posting a meal with two items creates one `meals` row and two `meal_items` rows with correct stored values; editing grams updates stored values; deleting removes the meal; a meal with no items is rejected with an Italian error message; a custom food is visible only to its owner.

### Manual checks

- On a phone-width browser window, enter yesterday's lunch from the plan (e.g. pasta e ceci + insalata) in under a minute without the page reloading.

---

## 3. Daily balance

Handover step 3. The main screen.

### Scope

- `app/calc/targets.py`: Mifflin-St Jeor BMR, TDEE with activity factor, daily kcal target (`TDEE − deficit`), protein target (`g_per_kg × weight`). Until phase 4 the profile values come from a constant block in `config.py` for the seeded user; phase 4 moves them to `profiles`.
- Route `GET /` (today) and `GET /giorno/{date}`: the four indicators from the handover, top to bottom: big kcal bar (green within target, red over, remaining kcal shown), protein bar to fill, smaller carbs and fat bars side by side, then the day's meals with thumbnail placeholder, each tappable to edit.
- Day navigation (previous/next) as HTMX partial swap.
- Visible note that the app shows estimates, not medical prescriptions.

### Frontend conventions

Before the first template of this phase, read `verenovo-site` (local copy under `VERENOVO/WEBSITE/.../site/`, remote `github.com/fabioguida/verenovo-site`) and adopt: its CSS custom-property palette and dark/light handling, its self-hosted fonts and licences, its file naming, and its approach to static assets. A short `app/static/README.md` records which conventions were taken and which were deliberately not (e.g. the marketing layout).

### Tests

- `test_targets.py`: male, 45 y, 180 cm, 85 kg → BMR 1755.0; female same numbers → 1589.0; TDEE at factor 1.375 → 2413.1 (rounded); target with 500 deficit → 1913.1; protein at 1.5 g/kg → 127.5 g; deficit and g/kg are parameters, not constants inside the function.
- `test_balance.py`: a day with meals totalling 1,600 kcal against a 1,900 target renders the kcal bar with the `ok` class and shows "300 kcal" remaining; 2,100 kcal renders `over` and "200 kcal oltre"; a day without meals renders the empty state; the date route for a day in the past lists only that day's meals; the disclaimer text is present.

### Manual checks

- On the phone, the kcal bar and the protein bar are readable without zooming; tapping a meal opens its edit form; next/previous day works.

---

## 4. Authentication and profiles

Handover step 4. Multi-user from here on.

### Scope

- Tables: `profiles` (`user_id` PK/FK, `age`, `height_cm`, `sex`, `activity_level`, `goal`, `deficit_kcal`, `protein_g_per_kg`, `updated_at`). Weight is not stored here (see phase 5).
- Passwords hashed with `argon2-cffi` (or `bcrypt`, decide at the step). Session kept in a signed cookie (`itsdangerous`), `HttpOnly`, `SameSite=Lax`, `Secure` in production.
- Routes: `GET/POST /registrati`, `GET/POST /accedi`, `POST /esci`, `GET/POST /profilo`.
- Registration is open (family and friends) but can be closed with a config flag `ALLOW_SIGNUP=false` once everyone is in.
- The phase 2 placeholder dependency is replaced by `current_user`; every route that touches user data requires it; every query filters by `user_id`.
- `scripts/init_db.py` seeds the author with a real password taken from an environment variable, never from code.

### Tests

- `test_auth.py`: register, log in, log out; wrong password rejected; duplicate email rejected; password hash in the DB is not the plaintext; protected routes redirect anonymous users to `/accedi`.
- `test_isolation.py`: two users each create a meal and a custom food; user A's balance page and search results never include user B's rows; requesting B's meal id as A returns 404, not 403 (do not reveal existence).
- `test_profile.py`: saving the profile recalculates targets on the balance page; invalid values (age 0, height 50 cm) are rejected with Italian messages.

### Manual checks

- Register a second family member from a phone, enter one meal, confirm the two accounts show different data.

---

## 5. Weights and workouts

Handover step 5.

### Scope

- Tables: `weights` (`id`, `user_id`, `date`, `kg`; unique on `user_id, date`), `workouts` (`id`, `user_id`, `date`, `activity`, `duration_min`, `kcal_burned`).
- `app/calc/activity.py`: MET table as data (`app/calc/met_table.py` or a JSON file) with a reference comment per row to the Compendium of Physical Activities; `kcal_burned(met, weight_kg, minutes)`.
- Current weight = latest `weights` row on or before the day; if none, the weight entered at registration (stored as the first `weights` row).
- Routes: `GET/POST /peso` (log and history list with a simple line chart drawn as inline SVG, no chart library), `GET/POST /attivita` (log), delete for both.
- Balance page: logged workouts raise the day's kcal ceiling; the bar shows base target + activity.

### Tests

- `test_activity.py`: walking 3.5 MET, 85 kg, 60 min → 297.5 kcal; 0 min → 0; unknown activity raises.
- `test_weights.py`: two weigh-ins on different dates; balance for a date between them uses the earlier one; a weigh-in changes the kcal target on later days only; second entry on the same date replaces the first.
- `test_balance.py` (extended): a 300 kcal workout on a 1,900 target day with 2,100 kcal eaten renders `ok` with 100 kcal remaining.

### Manual checks

- Log a weight and a 45-minute tennis session, see the target rise on today's balance and the weight on the chart.

---

## 6. Presets and personal library

Handover step 6.

### Scope

- Table: `meal_presets` (`id`, `user_id`, `name`), `meal_preset_items` (`preset_id`, `food_id`, `grams`).
- Routes: `GET /preset`, `GET/POST /preset/nuovo`, "save this meal as preset" from the meal view, `POST /pasti/da-preset/{id}` (one tap creates today's meal with `input_method = preset`, editable afterwards).
- Personal library (no model training): when the user adds a food to a meal, the grams field is pre-filled with the median of that user's last 5 entries of the same food, with a hint "di solito 140 g". Implemented as a query on `meal_items`, no new table.

### Tests

- `test_presets.py`: creating a preset from a meal copies its items; creating a meal from a preset produces the same totals as the original meal; presets of another user are not listed and not usable.
- `test_library.py`: after three meals with pasta at 120/140/160 g, the suggestion for pasta is 140; with no history the field is empty; another user's history does not leak.

### Manual checks

- Save "avocado toast" as a preset, log it on two consecutive mornings with one tap each.

---

## 7. Per-user meal plan with quantities

Handover feature 9. Depends on open decisions 8.3 and 8.4 being settled.

### Scope

- Tables: `eating_schedules` (`user_id`, `day_of_week`, per-meal times nullable, per-meal kcal share), `food_preferences` (`user_id`, `food_id` nullable, `category` nullable, `kind` = `like`/`dislike`/`avoid`), `meal_plans` (`id`, `user_id`, `start_date`, `weeks`, `kcal_target`, `protein_target_g`, `created_at`), `meal_plan_items` (`plan_id`, `date`, `meal_type`, `food_id`, `grams`, computed values).
- `app/calc/planner.py`, in this order and tested separately:
  1. `meal_kcal(day_target, share)`;
  2. `scale_dish(template_items, target_kcal)` keeps ingredient proportions;
  3. `fix_protein(day_items, protein_target)` raises protein items and lowers carb items when the day is short;
  4. `round_practical(items)` rounds to 5 g, whole units for eggs, fruit, bread slices (unit mass stored per food in a new nullable `unit_g` column on `foods`);
  5. `pick_dishes(user, week)` — rule-based rotation (recommended option of 8.3): pasta 2×, fish 2×, legumes 2× per week, filtered by preferences, drawn from the user's presets and a seeded set of template dishes.
- Routes: `GET/POST /orari`, `GET/POST /preferenze`, `GET /piano` (two-week table), `POST /piano/rigenera`; the balance page shows the planned meal of the current slot as a suggestion with a "conferma" button that creates the real meal.
- Regeneration is triggered manually and suggested automatically when weight or target changes by more than a configurable threshold.

### Tests

- `test_planner.py`: shares 30/45/25 on 1,900 kcal → 570/855/475; scaling a 600 kcal template dish to 855 multiplies every ingredient by 1.425; after `fix_protein`, the day's protein is within 5 g of target and kcal within 3 %; rounding never moves a day's kcal by more than 5 %; eggs come out as whole numbers; a dish containing an `avoid` food is never picked; over two weeks pasta appears exactly 4 times for the author's schedule; Friday and Saturday have no `spezzafame` and Sunday has no `cena` for the author's schedule.
- `test_plan_routes.py`: the author's schedule from [PIANO_ALIMENTARE.md](PIANO_ALIMENTARE.md) entered as fixture; the plan page renders 14 days; confirming a suggested meal creates a meal whose totals equal the plan item.

### Manual checks

- The author's generated plan looks like the hand-written one in shape (same slots, similar dishes) and every meal has grams.

### Decisions needed before starting

- 8.3 rules vs AI for dish selection (plan assumes rules).
- 8.4 meal shares and rounding steps (plan assumes 30/45/25 and 5 g as defaults, both editable in `/orari`).

### Findings from the build (phase 7 done, decisions 8.3 = rules and 8.4 = 30/45/25, 5 g)

- The shares are fractions of the day's target and are **not** normalised: a day whose dinner is eaten out keeps that share free, as the author's schedule needs.
- The protein check works as the handover describes (protein up, carbs down, at constant kcal) but **cannot always reach 1.5 g/kg**: with legume-, milk- or yogurt-based dishes the protein source is too thin, and distorting the dish further would be worse than reporting the shortfall. Days short by more than 10 g are flagged on the plan page with the suggestion to add a protein source or lower the g/kg. Dish selection has a small protein-density tie-break (fish ≈ +1.9, pasta e ceci ≈ +0.5) under the rotation quotas.
- A dish is scaled at most 2.5× its template (and at least 0.5×). A single slot above that — the Sunday family lunch at 70 % of the day — lands short by design; the page shows the real kcal.
- Unit rounding (whole eggs, slices, fruit) is compensated on the dish's largest free ingredient, so a meal stays within a few percent of its share.
- Template dishes live in `data/template_dishes.json` (26 dishes from PIANO_ALIMENTARE.md, USDA ids); the user's presets join them as candidates. Whole-unit masses are in that file, not in a `foods.unit_g` column.

---

## 8. Photo analysis

Handover step 8. Depends on open decision 8.1.

### Scope

- Photo upload on the meal form; stored on S3 (bucket with versioning) under `photos/{user_id}/{uuid}.jpg`, resized to max 1,600 px before upload; `photo_url` stored on the meal; a thumbnail shown on the balance page.
- Vision model call through a single adapter `app/photos/analyzer.py` with one interface: `analyze(image_bytes) -> list[(food_name, grams, confidence)]`. The concrete provider (Claude API or other) is a configuration choice behind that interface; the API key comes from the environment and is never committed.
- The result is shown as a pre-filled, editable meal form (feature 2 of the handover); food names are matched to `foods` by search, unmatched ones are highlighted for the user to pick or create.
- Cost control: a per-user daily cap on analysis calls (`PHOTO_DAILY_LIMIT`, default 10) and a log table `photo_analyses` (`user_id`, `datetime`, `provider`, `cost_estimate`).

### Tests

- `test_photos.py` with a fake analyzer and a fake S3 (`moto` or an in-memory stub): upload stores the object key on the meal; the pre-filled form contains the analyzer's items; editing grams before saving stores the edited values; the daily cap returns an Italian message on the 11th call; no real network call happens in the suite.

### Manual checks

- Photograph a plate from the plan, confirm the suggestion is editable and the saved meal shows its thumbnail.

### Decisions needed before starting

- 8.1 provider and per-image cost, checked on the official pricing page at the time.

---

## 9. AWS deployment and backups

Handover step 9.

### Scope

- `deploy/`: systemd unit running `uvicorn` behind `nginx` with HTTPS from Let's Encrypt (`certbot`); `.env` on the instance only; `deploy/README.md` with the exact commands to recreate the instance from scratch.
- Instance: smallest current-generation EC2 that runs the app; the type is chosen after checking the AWS pricing calculator, not from memory (handover §6).
- S3: one bucket, versioning on, prefixes `photos/` and `backups/`, lifecycle rule deleting `backups/` objects after 60 days.
- Backup: `scripts/backup_db.sh` runs `sqlite3 mealtrack.db ".backup /tmp/backup.db"` then uploads to `s3://.../backups/mealtrack-YYYY-MM-DD.db`; weekly cron; logs to a file.
- Alembic introduced here, with the current schema as the initial migration, so future schema changes on the live DB are scripted.
- Domain and HTTPS are open point 8.5; the plan assumes a subdomain of a domain the user already owns.

### Tests

- `test_backup.sh` (run manually on the instance and in CI against a local MinIO or stub): the backup file opens with `sqlite3` and `PRAGMA integrity_check` returns `ok`; the S3 object exists after the script; a restore into a fresh `mealtrack.db` boots the app and `/health` answers.
- CI runs the Alembic migration from empty to head and back to empty.

### Manual checks

- The app is reachable over HTTPS from a phone on mobile data; a second user logs in; after a week the first backup object appears in `backups/`; after 61 days (checked later) the first one is gone.

---

## 10. Traceability

| Handover item | Phase |
| --- | --- |
| Feature 1 manual entry, calculation engine | 2 |
| Feature 1 photo entry | 8 |
| Feature 2 correction of estimates | 8 (form is the same as 2) |
| Feature 3 personal library | 6 |
| Feature 4 presets | 6 |
| Feature 5 daily balance | 3 (activity term added in 5) |
| Feature 6 activity | 5 |
| Feature 7 weigh-ins | 5 |
| Feature 8 weekly feedback | 3 renders the day; weekly average and coaching text added as a small step at the end of 5, once weights and workouts exist (`app/calc/trend.py`, test: 7 days at 1,800/2,000/1,900/2,200/1,700/1,900/1,800 on a 1,900 target → average 1,900, feedback "in linea") |
| Feature 9 meal plan | 7 |
| §5 formulas | 3 (BMR/TDEE/protein), 5 (MET) |
| §6 AWS | 9 (S3 photos first used in 8) |
| Open 8.1 | gate for 8 |
| Open 8.2 | 4 |
| Open 8.3, 8.4 | gate for 7 |
| Open 8.5 language | Italian, all phases |
| Open 8.5 domain/HTTPS, password recovery | 9 (recovery deferred, admin resets by script) |
