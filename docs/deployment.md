# Deployment Notes

Recipe Pro is deployed on the same Hetzner VPS where development is done, reachable over the Tailscale network.

The service is multi-user and expects two configured users with isolated databases.

## Service

Systemd unit template: `ansible/templates/idea-canvas.service`

Key settings:

- Working directory: `/home/admin/projects/idea-canvas`
- Start command: `/home/admin/projects/idea-canvas/.venv/bin/uvicorn app.app:app --host 100.84.173.75 --port 8084`

## Restart and Verify

```bash
sudo systemctl restart idea-canvas
sudo systemctl is-active idea-canvas
curl -sSf http://100.84.173.75:8084/health
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
