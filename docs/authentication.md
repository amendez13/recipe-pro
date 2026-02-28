# Authentication Architecture

## Overview

Recipe Pro uses cookie-based authentication with exactly two configured users.
Each authenticated user is mapped to a dedicated SQLite database file for strict data isolation.

## Components

- Config models: `app/config.py`
  - `AuthConfig` holds:
    - `session_secret`
    - `session_cookie_name`
    - `session_max_age_seconds`
    - `session_secure`
    - `users` (must be exactly 2)
  - `UserConfig` holds:
    - `username`
    - `password_hash`
    - `db_path`

- Auth utilities: `app/auth.py`
  - `hash_password(password)` creates PBKDF2-SHA256 hashes
  - `verify_credentials(username, password, users)` checks credentials
  - `create_session_token(username, secret, ttl_seconds)` creates signed token
  - `decode_session_token(token, secret)` validates signature + expiry

- HTTP integration: `app/app.py`
  - `POST /api/auth/login`
  - `POST /api/auth/logout`
  - `GET /api/auth/me`
  - Protected endpoints require a valid session user
  - DB access is resolved per authenticated username

## Session Model

- Session token is signed with HMAC-SHA256 using `auth.session_secret`.
- Cookie fields:
  - `HttpOnly=true`
  - `SameSite=lax`
  - `Secure` from `auth.session_secure`
  - `Max-Age` from `auth.session_max_age_seconds` (or shorter when `remember=false`)
- Logout clears the cookie.

## Data Isolation

- User identity is resolved from the signed cookie on each request.
- API handlers route to a `RecipeDatabase` instance keyed by that user’s `db_path`.
- One user cannot read or mutate the other user’s data through the API.

## Configuration Example

```yaml
auth:
  session_secret: "${RECIPE_PRO_SESSION_SECRET}"
  session_cookie_name: "recipe_pro_session"
  session_max_age_seconds: 2592000
  session_secure: false
  users:
    - username: "alex"
      password_hash: "pbkdf2_sha256$<iterations>$<salt>$<hash>"
      db_path: "/home/admin/projects/recipe-pro/data/alex.db"
    - username: "kris"
      password_hash: "pbkdf2_sha256$<iterations>$<salt>$<hash>"
      db_path: "/home/admin/projects/recipe-pro/data/kris.db"
```

## Usage

1. Generate password hash:

```bash
.venv/bin/python - <<'PY'
from app.auth import hash_password
print(hash_password("replace-with-strong-password"))
PY
```

2. Set `auth.users` and `auth.session_secret` in active config.
3. Restart service:

```bash
sudo systemctl restart recipe-pro.service
```

4. Log in from UI or via API:

```bash
curl -i -X POST http://127.0.0.1:8084/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"alex","password":"...","remember":true}'
```

5. Verify active session:

```bash
curl -b cookies.txt http://127.0.0.1:8084/api/auth/me
```

## Frontend Flow

- App boot calls `/api/auth/me`.
- If authenticated, it loads the normal recipe views.
- If unauthenticated (or any later 401), it redirects to login view.
- Logout clears session and returns to login.
