# CLAUDE.md for Idea Canvas

## Project Overview

Idea Canvas is a lightweight FastAPI web application for capturing and organizing ideas.
It follows the same patterns as other automation components deployed to Hetzner VPS.

## Architecture

- **Backend**: FastAPI + Uvicorn
- **Database**: SQLite (via sqlite3)
- **Frontend**: Vanilla JS + CSS (SPA pattern)
- **Deployment**: Ansible + systemd

## Key Files

- `app/app.py` - FastAPI application factory
- `app/main.py` - CLI entry point (Click-based)
- `app/config.py` - Configuration management
- `app/database.py` - SQLite data layer
- `app/models.py` - Data classes
- `config/config.yaml` - Default configuration

## Running Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main -c config/config.yaml -v
```

## Testing

```bash
PYTHONPATH=. pytest tests/ -v
```

## Deployment

The app is deployed via Ansible to the Hetzner VPS:

```bash
cd /path/to/automation/infra/hetzner
ansible-playbook -i inventory.local.ini idea_canvas_setup.yml
```

Service: `idea-canvas.service`
Port: 8084 (Tailscale-only)

## Conventions

- Config files: `config.yaml` (default), `config.local.yaml` (local override, gitignored)
- Logging: stdout via Python logging, captured by journald
- Database: SQLite file at path from config
