# Recipe Pro Architecture

## Stack

- Backend: FastAPI (`app/app.py`)
- Data layer: SQLite (`app/database.py`)
- Models: dataclasses (`app/models.py`)
- Frontend: vanilla JS SPA (`app/templates/index.html`, `app/static/app.js`, `app/static/style.css`)

## Database Schema

### `ingredients`

- `id INTEGER PRIMARY KEY`
- `name TEXT UNIQUE NOT NULL` (normalized lowercase + trimmed)
- `category TEXT NULL`

### `recipes`

- `id INTEGER PRIMARY KEY`
- `title TEXT NOT NULL`
- `instructions TEXT NOT NULL`
- `servings INTEGER NULL`
- `prep_time INTEGER NULL`
- `cook_time INTEGER NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

### `recipe_ingredients`

- `id INTEGER PRIMARY KEY`
- `recipe_id INTEGER NOT NULL` (`ON DELETE CASCADE`)
- `ingredient_id INTEGER NOT NULL`
- `quantity REAL NOT NULL`
- `unit TEXT NOT NULL`
- `notes TEXT NULL`
- `UNIQUE(recipe_id, ingredient_id)`

## Ingredient Semantics

- `ingredients` are independent entities (name/category/default flags).
- `ingredients` do **not** own `quantity`, `unit`, or `notes`.
- `quantity`, `unit`, and `notes` are attributes of the **recipe-to-ingredient link** in `recipe_ingredients`.
- This means the same ingredient can have different quantities/units/notes across different recipes.
- Current constraint: `UNIQUE(recipe_id, ingredient_id)` allows only one row per ingredient per recipe.

## API Boundaries

- Recipe CRUD endpoints handle full recipe payloads including ingredients.
- Ingredient endpoints are read-only; ingredient records are created/updated via recipe writes.
- Shopping list endpoint computes consolidated items on-demand (not persisted).
- Suggestions endpoint computes match percentage and matched/missing ingredient names on-demand.
- Auth endpoints manage session cookies (`/api/auth/login`, `/api/auth/logout`, `/api/auth/me`).

## Frontend Views

- Recipe list + search + selection state for shopping list
- Recipe detail cooking mode
- Add/edit recipe form with dynamic ingredient rows
- Shopping list view grouped by category
- Recipe finder view using ingredient selection + suggestions
- Login view + authenticated app shell

## Authentication and Isolation

- Exactly 2 configured users are supported.
- Each user maps to a dedicated SQLite database path.
- All recipe-related APIs require an authenticated session.
- Session failures (401) redirect the SPA to login.

See: `docs/authentication.md`
