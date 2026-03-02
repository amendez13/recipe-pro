# Recipe Pro Architecture

## High-Level Architecture

- Backend: FastAPI application in `app/app.py`
- Persistence: SQLite with migration logic in `app/database.py`
- Data models: dataclasses in `app/models.py`
- Frontend: vanilla JS SPA in `app/templates/index.html`, `app/static/app.js`, `app/static/style.css`
- Runtime: systemd service (`recipe-pro`) on Hetzner VPS

## Data Model Implementation

### `ingredients`

- `id INTEGER PRIMARY KEY`
- `name TEXT UNIQUE NOT NULL` (legacy compatibility alias; mirrors `name_en`)
- `name_en TEXT UNIQUE` (normalized canonical key)
- `name_es TEXT` (localized display name)
- `category TEXT NULL`
- `default_available INTEGER NOT NULL DEFAULT 0`

### `recipes`

- `id INTEGER PRIMARY KEY`
- `title TEXT NOT NULL`
- `category TEXT NULL`
- `instructions TEXT NOT NULL` (compatibility text blob)
- `url TEXT NULL` (source URL for imported/manual recipes)
- `servings INTEGER NULL`
- `prep_time INTEGER NULL`
- `cook_time INTEGER NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`

### `recipe_steps`

- `id INTEGER PRIMARY KEY`
- `recipe_id INTEGER NOT NULL` (`ON DELETE CASCADE`)
- `step_order INTEGER NOT NULL`
- `instruction TEXT NOT NULL`

### `recipe_ingredients`

- `id INTEGER PRIMARY KEY`
- `recipe_id INTEGER NOT NULL` (`ON DELETE CASCADE`)
- `ingredient_id INTEGER NOT NULL`
- `quantity REAL NOT NULL`
- `unit TEXT NOT NULL`
- `notes TEXT NULL`
- `UNIQUE(recipe_id, ingredient_id)`

## Domain Semantics

- Ingredients are standalone entities and are shared across recipes.
- Quantity/unit/notes are recipe-specific attributes on `recipe_ingredients`.
- A single ingredient can vary by quantity/unit/notes across recipes.
- One ingredient may appear once per recipe because of `UNIQUE(recipe_id, ingredient_id)`.

## API Implementation Boundaries

- Auth/session:
  - `POST /api/auth/login`
  - `POST /api/auth/logout`
  - `GET /api/auth/me`
- Recipes:
  - `GET/POST /api/recipes`
  - `GET/PUT/DELETE /api/recipes/{id}`
  - `POST /api/recipes/import-preview`
- Ingredients:
  - `GET /api/ingredients`
  - `GET /api/ingredients/{id}/recipes`
  - `POST /api/ingredients/{id}/default`
  - `PUT /api/ingredients/{id}/names`
  - `DELETE /api/ingredients/{id}`
  - `POST /api/ingredients/merge-preview`
  - `POST /api/ingredients/merge`
  - `POST /api/ingredients/merge/{merge_event_id}/undo`
  - `GET /api/ingredients/merge-history`
- Derived features:
  - `POST /api/shopping-list`
  - `POST /api/suggestions`

## Frontend Implementation

- Login-gated SPA shell with route-based view rendering.
- Recipe list grouped by category with collapsible sections and search.
- Recipe detail with step list and focus mode (step-by-step navigation).
- Shopping list with recipe picker, generation, and per-user local persistence.
- Recipe finder with ingredient selection and dynamic suggestions.
- Ingredients management table for defaults, bilingual naming, merge, and cleanup.
- Ingredient language toggle (EN/ES) in recipe detail and shopping list.

## Multi-User Isolation

- Exactly two configured users.
- Each user is mapped to a dedicated SQLite database file.
- Request auth context determines which `RecipeDatabase` instance is used.
- Session loss/401 transitions SPA back to login.

See also:
- `docs/authentication.md`
- `docs/deployment.md`
