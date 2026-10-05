# Meal Tracker Web App — Architecture Spec

Oct 5, 2026 · @Fabio Guida

## Overview

A web app to track meals, nutrition and activity so each user sees whether they are on target for weight loss. Built for personal and family use: the user, family and a few friends.

- **Stack:** Python backend (FastAPI), SQLite to start, server-rendered HTML templates (Jinja) plus HTMX for a responsive feel, no heavy JS framework.
- **Hosting:** the user's own AWS account; free tier is expired, so run on the cheapest setup, low single-digit dollars per month.
- **Auth:** email + password, passwords hashed; no email verification or 2FA for now.
- **Goal logic:** daily calorie and macro targets from each user's profile; logged exercise raises the day's ceiling; feedback is judged on the weekly trend, not a single day.

## Architecture

Four parts: a Python backend, a database, a server-rendered frontend, and AWS infrastructure.

| Layer | Choice | Notes |
| --- | --- | --- |
| Backend | Python + FastAPI | Routes: upload meal, log weight, log workout, read daily balance, auth |
| Database | SQLite to start → RDS/Postgres later | Single file, zero config; migrate when it grows |
| Food data | USDA FoodData Central, imported once | Base table; Italian dishes added by hand into the personal library as needed |
| Frontend | Jinja templates + HTMX | Server-rendered, partial updates without full reload; no React/Vue |
| Photo storage | AWS S3, versioning on | Meal photos kept off the app server |
| Meal photo analysis | Open decision (see below) | API billed per image; subscription plans don't cover app calls |
| Backups | Weekly copy of the DB to S3 | Retention max 2 months (\~8 copies), older ones auto-deleted |
| Hosting | AWS EC2 (small), user's account | Cheapest setup; app + DB together to start |

## Data model

Every table carries a user\_id so each person's data stays separate.

| Table | Key fields |
| --- | --- |
| users | id, email, password\_hash |
| profiles | user\_id, age, height, weight, sex, activity\_level, goal (maintain/lose), daily targets |
| foods | id, name, source (USDA or custom), kcal, protein, carbs, fat per 100 g |
| meals | id, user\_id, datetime, type (breakfast/lunch/snack), photo\_url, foods + grams, computed kcal and macros |
| weights | id, user\_id, date, kg |
| workouts | id, user\_id, date, activity, duration, estimated kcal burned (MET-based) |
| meal\_presets | id, user\_id, name, foods + grams (recurring meals for quick entry) |

## Core features

1. **Meal entry, two ways into one engine.** Upload a photo (AI estimates foods and grams) or type foods and grams by hand. Both produce the same thing: a list of foods with grams, fed to one calculation engine.
2. **Personal library, learning without training a model.** Each corrected meal is saved with its real quantities; next time a similar meal appears, the app suggests the user's usual portion (e.g. "your pasta is usually 140 g").
3. **Quick entry for recurring meals.** Fixed meals (avocado toast, Sunday pasta, the snack yogurt) are saved as presets with set quantities and recalled with one tap.
4. **Daily balance, four indicators.** Top to bottom: a big calories bar (green within target, red over), a protein bar to fill (target \~1.5 g per kg), smaller carbs and fat bars, then today's meals with thumbnails, tappable to correct.
5. **Activity folds into the target.** Each logged workout (gym, run, walk, tennis) adds its estimated burn and raises that day's calorie ceiling.
6. **Feedback on the weekly trend.** One day over target is fine if the weekly average holds; the app coaches the trend, not each evening.

## Open decisions

- [ ] **Meal photo analysis.** Which AI reads the photos and estimates grams. Note: Claude Pro/Max subscriptions do not cover automated app calls; that needs an API key billed per image (a few cents each). Alternative: ship manual entry first, add photos later.
- [ ] **Portion quantities per user.** Needs age, height, weight, sex and activity to compute the daily target (Mifflin-St Jeor); not yet provided.

## Notes for Claude Code

- **Match the existing GitHub repo.** The frontend should follow the conventions, structure and style of the user's existing website in their GitHub repo. Point Claude Code at that repo and have it mirror those standards, since this spec doesn't capture them.
- **Build order suggestion:** manual meal entry and the calculation engine first (no AI dependency), then the daily balance, then auth, then photo analysis, then AWS deploy.
- This document is the starting point; use it as the base and continue in Claude Code.
