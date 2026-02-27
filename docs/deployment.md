# Deployment Notes

Recipe Pro is deployed on the same Hetzner VPS where development is done, reachable over the Tailscale network.

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

## Notes

- Deployment and runtime are on the same machine.
- No external deployment target is required for this project.
