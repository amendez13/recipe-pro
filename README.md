# Recipe Pro

Recipe Pro is a FastAPI + SQLite web app for managing recipes, cooking from a readable detail view, generating shopping lists, and finding recipes by available ingredients.

The app now runs in **multi-user mode** with exactly two users, each isolated to a dedicated SQLite database.

## Features

- Recipe CRUD with normalized shared ingredients
- Bilingual ingredient names (`name_en` / `name_es`) with migration from legacy `name`
- Optional recipe category field (editable in add/edit form)
- Cooking Mode recipe detail with clear steps and ingredient panel
- Recipe list grouped by category with collapsible sections and live search
- Shopping list generation from selected recipes
- Shopping list and checked-item persistence per user (browser local storage)
- Recipe suggestions based on selected ingredients
- Ingredient management table (default selection, bilingual rename, usage visibility, delete, merge + undo)
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
      db_path: "/home/admin/projects/recipe-pro/data/user1.db"
    - username: "user2"
      password_hash: "pbkdf2_sha256$<iterations>$<salt>$<hash>"
      db_path: "/home/admin/projects/recipe-pro/data/user2.db"
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
- `PUT /api/ingredients/{id}/names`
- `POST /api/ingredients/{id}/default`
- `POST /api/ingredients/merge-preview`
- `POST /api/ingredients/merge`
- `POST /api/ingredients/merge/{merge_event_id}/undo`
- `GET /api/ingredients/merge-history`
- `GET /api/stats`

### Shopping and Suggestions

- `POST /api/shopping-list`
- `POST /api/suggestions`
- `POST /api/recipes/import-preview`

### Health

- `GET /health`

### Authentication

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

## Ingredient Data Model

- Ingredients are independent records (`name_en`, `name_es`, legacy `name`, optional `category`).
- `quantity`, `unit`, and `notes` are recipe-specific values stored on the recipe-ingredient link.
- The same ingredient can therefore have different quantities/units/notes in different recipes.
- Current rule: one ingredient can appear only once per recipe (`UNIQUE(recipe_id, ingredient_id)`).

## Usage

### Manage ingredient names (EN/ES)

1. Open `Recipe Finder`.
2. Click `Manage Ingredients`.
3. Edit `English` and/or `Spanish` in a row.
4. Click `Save`.

Changes apply globally in recipe detail and shopping list displays.

### Switch ingredient language

- Recipe detail: use `EN` / `ES` toggle in the Ingredients panel.
- Shopping list: use `EN` / `ES` toggle in the Shopping header.

Language preference is stored per logged-in user in browser local storage.

## Test

```bash
source .venv/bin/activate
RECIPE_PRO_SESSION_SECRET=synthetic-local-test-session pytest -q
```

The suite mocks Claude responses and blocks live Claude subprocess calls, so it
requires no paid model calls. Import regression cases cover both incomplete
responses and complete normalized recipes. The session value above is only for
local test initialization.

## Architecture Docs

- `docs/architecture.md`
- `docs/authentication.md`
- `docs/deployment.md`
- `docs/import-flow.md`

## Deployment

Systemd (same VPS, Tailscale network):

- unit template: `ansible/templates/recipe-pro.service`
- restart service:

```bash
sudo systemctl restart recipe-pro
sudo systemctl status recipe-pro --no-pager
```

Multi-user rollout checklist:

1. Set `auth.users` (exactly two users) with unique `db_path` values.
2. Generate and set password hashes (never store plaintext passwords).
3. Set `auth.session_secret` to a strong random value.
4. Restart service and verify login + user isolation behavior.

## Secret Scanning (gitleaks)

`.github/workflows/gitleaks.yml` runs the standardized `Secret Scanning` job on
`[self-hosted, fargate]`. It downloads gitleaks 8.30.1 and verifies the pinned
Linux x64 archive SHA-256 before execution.

Pull requests scan `base.sha..head.sha`. Pushes and manual runs scan the event
commit's full reachable history. Both include first-parent merge patches;
sibling branch refs are outside the scan scope. The job validates the revisions
and complete Git traversal, then fails on scanner errors even if gitleaks
returns zero.

Reports use `--redact=100`. The job uploads redacted SARIF as an artifact and
attempts GitHub code scanning ingestion when supported. Findings fail the job;
real credentials require approved remediation. Any false-positive exclusion
must be verified, justified in its PR, and restricted to an exact fingerprint.

This workflow is byte-identical to the reviewed template in
[automation#1020](https://github.com/amendez13/automation/pull/1020), delivered
under [automation#376](https://github.com/amendez13/automation/issues/376).
After merge, confirm a green Secret Scanning run on main. Roll back through a
reviewed revert PR if needed.
