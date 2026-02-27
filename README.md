# Recipe Pro

Recipe Pro is a FastAPI + SQLite web app for managing recipes, cooking from a readable detail view, generating shopping lists, and finding recipes by available ingredients.

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

database:
  path: "/home/admin/projects/idea-canvas/data/ideas.db"
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

## Test

```bash
source .venv/bin/activate
pytest -q
```

## Architecture Docs

- `docs/architecture.md`
- `docs/deployment.md`

## Deployment

Systemd (same VPS, Tailscale network):

- unit template: `ansible/templates/idea-canvas.service`
- restart service:

```bash
sudo systemctl restart idea-canvas
sudo systemctl status idea-canvas --no-pager
```
