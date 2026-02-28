# Recipe Pro

Recipe Pro is a FastAPI + SQLite web app for managing recipes, cooking from a readable detail view, generating shopping lists, and finding recipes by available ingredients.

The app now runs in **multi-user mode** with exactly two users, each isolated to a dedicated SQLite database.

## Features

- Recipe CRUD with normalized shared ingredients
- Cooking Mode recipe detail with clear steps and ingredient panel
- Shopping list generation from selected recipes
- Recipe suggestions based on selected ingredients
- Ingredient and stats endpoints for UI dashboards

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main -c config/config.local.yaml -v
```

App URL (local config): `http://100.84.173.75:8084/`

## Configuration

Config files:

- `config/config.local.yaml` (preferred local override)
- `config/config.yaml` (default)

Example:

```yaml
web:
  host: "100.84.173.75"
  port: 8084

auth:
  session_secret: "${RECIPE_PRO_SESSION_SECRET}"
  session_cookie_name: "recipe_pro_session"
  session_max_age_seconds: 2592000
  session_secure: false
  users:
    - username: "user1"
      password_hash: "pbkdf2_sha256$<iterations>$<salt>$<hash>"
      db_path: "/home/admin/projects/idea-canvas/data/user1.db"
    - username: "user2"
      password_hash: "pbkdf2_sha256$<iterations>$<salt>$<hash>"
      db_path: "/home/admin/projects/idea-canvas/data/user2.db"
```

### Generate Password Hashes

Use the built-in helper:

```bash
.venv/bin/python - <<'PY'
from app.auth import hash_password
print(hash_password("replace-with-strong-password"))
PY
```

## API Summary

### Recipes

- `GET /api/recipes?search=<term>`
- `POST /api/recipes`
- `GET /api/recipes/{id}`
- `PUT /api/recipes/{id}`
- `DELETE /api/recipes/{id}`

### Ingredients and Stats

- `GET /api/ingredients`
- `GET /api/ingredients/{id}/recipes`
- `GET /api/stats`

### Shopping and Suggestions

- `POST /api/shopping-list`
- `POST /api/suggestions`

### Health

- `GET /health`

### Authentication

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

## Ingredient Data Model

- Ingredients are independent records (`name`, optional `category`).
- `quantity`, `unit`, and `notes` are recipe-specific values stored on the recipe-ingredient link.
- The same ingredient can therefore have different quantities/units/notes in different recipes.
- Current rule: one ingredient can appear only once per recipe (`UNIQUE(recipe_id, ingredient_id)`).

## Test

```bash
source .venv/bin/activate
pytest -q
```

## Architecture Docs

- `docs/architecture.md`
- `docs/authentication.md`
- `docs/deployment.md`

## Deployment

Systemd (same VPS, Tailscale network):

- unit template: `ansible/templates/idea-canvas.service`
- restart service:

```bash
sudo systemctl restart idea-canvas
sudo systemctl status idea-canvas --no-pager
```

Multi-user rollout checklist:

1. Set `auth.users` (exactly two users) with unique `db_path` values.
2. Generate and set password hashes (never store plaintext passwords).
3. Set `auth.session_secret` to a strong random value.
4. Restart service and verify login + user isolation behavior.
