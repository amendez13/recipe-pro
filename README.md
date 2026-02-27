# Idea Canvas

A FastAPI web app for capturing and organizing ideas. Accessible only within your Tailscale network.

## Features

- Create, edit, and delete ideas
- Organize by categories
- Tag ideas for easy filtering
- Full-text search
- Light/dark theme support
- Responsive design

## Quick Start

### Local Development

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python -m app.main -c config/config.yaml -v
```

Open http://127.0.0.1:8084/ in your browser.

### Deploy to VPS

```bash
cd /path/to/automation/infra/hetzner
ansible-playbook -i inventory.local.ini idea_canvas_setup.yml
```

## Configuration

Config file: `config/config.yaml` (default) or `config/config.local.yaml` (local override)

```yaml
web:
  host: "127.0.0.1"
  port: 8084

database:
  path: "data/ideas.db"
```

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ideas` | GET | List all ideas |
| `/api/ideas` | POST | Create new idea |
| `/api/ideas/{id}` | GET | Get idea by ID |
| `/api/ideas/{id}` | PUT | Update idea |
| `/api/ideas/{id}` | DELETE | Delete idea |
| `/api/categories` | GET | List categories |
| `/api/search?q=` | GET | Search ideas |
| `/api/stats` | GET | Get statistics |
| `/health` | GET | Health check |

## Project Structure

```
idea-canvas/
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
│   └── config.yaml      # Default configuration
├── ansible/
│   └── templates/       # Ansible templates
├── tests/               # Test files
├── docs/                # Documentation
├── requirements.txt
└── README.md
```

## License

MIT
