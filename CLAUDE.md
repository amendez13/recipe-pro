# CLAUDE.md for Recipe Pro

## Project Specification

See **[AGENT.md](AGENT.md)** for the complete project specification including:
- Core functionality and features
- Database schema
- API endpoints
- UI views

## Development

### Running Locally

```bash
cd /home/admin/projects/recipe-pro
source .venv/bin/activate
python -m app.main -c config/config.local.yaml -v
```

### Testing

```bash
PYTHONPATH=. pytest tests/ -v
```

### Project Structure

```
recipe-pro/  (Recipe Pro)
├── app/
│   ├── __init__.py
│   ├── main.py          # CLI entry point
│   ├── app.py           # FastAPI application
│   ├── config.py        # Configuration loader
│   ├── models.py        # Data models
│   ├── database.py      # SQLite database layer
│   ├── static/          # CSS and JavaScript
│   └── templates/       # HTML templates
├── config/
│   ├── config.yaml      # Default configuration
│   └── config.local.yaml # Local overrides (gitignored)
├── tests/
├── AGENT.md             # Project specification
├── CLAUDE.md            # This file
└── requirements.txt
```

## Conventions

- **Config**: `config.yaml` (defaults), `config.local.yaml` (local overrides, gitignored)
- **Database**: SQLite file, path from config
- **Logging**: stdout via Python logging, captured by journald on VPS
- **Ingredient normalization**: lowercase, trimmed, for deduplication

## Deployment

Service: `recipe-pro.service` (port 8084, Tailscale-only)

```bash
cd /path/to/automation/infra/hetzner
ansible-playbook -i inventory.local.ini recipe_pro_setup.yml
```
