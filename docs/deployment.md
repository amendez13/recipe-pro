# Deployment Architecture, Implementation, and Usage

Recipe Pro is deployed on the same Hetzner VPS where development is done, reachable over the Tailscale network.

The service is multi-user and expects two configured users with isolated databases.

## Architecture

Systemd unit template: `ansible/templates/recipe-pro.service`

Key settings:

- Working directory: `/home/admin/projects/recipe-pro`
- Start command: `/home/admin/projects/recipe-pro/.venv/bin/uvicorn app.app:app --host 0.0.0.0 --port 8084`

## Implementation Checklist

1. Ensure code is present in `/home/admin/projects/recipe-pro`.
2. Ensure virtualenv and dependencies are installed.
3. Ensure active config has valid `web` and `auth` sections.
4. Ensure both per-user databases exist and are writable by service user.
5. Ensure `recipe-pro.service` is enabled.

## Usage: Restart and Verify

```bash
sudo systemctl restart recipe-pro
sudo systemctl is-active recipe-pro
curl -sSf http://127.0.0.1:8084/health
```

## Multi-user Config Requirements

Before restart, ensure `config/config.local.yaml` (or active config) includes:

- `auth.session_secret` (strong random string)
- `auth.users` with exactly 2 entries
- each user has unique `username`
- each user has unique `db_path`
- `password_hash` values generated via `app.auth.hash_password`

Quick hash generation:

```bash
.venv/bin/python - <<'PY'
from app.auth import hash_password
print(hash_password("replace-with-strong-password"))
PY
```

Post-deploy checks:

1. Log in as user A and create a test recipe.
2. Log in as user B and verify user A recipe is not visible.
3. Confirm browser session persistence and logout behavior.

## Notes

- Deployment and runtime are on the same machine.
- No external deployment target is required for this project.
