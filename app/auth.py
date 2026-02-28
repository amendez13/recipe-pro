"""Authentication and session helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional

from .config import UserConfig


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def hash_password(password: str, iterations: int = 600_000) -> str:
    """Create a PBKDF2-SHA256 password hash."""
    salt = os.urandom(16).hex()
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return f"pbkdf2_sha256${iterations}${salt}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored hash."""
    try:
        scheme, raw_iterations, salt, expected_hex = stored_hash.split("$", 3)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    try:
        iterations = int(raw_iterations)
    except ValueError:
        return False
    if iterations <= 0 or not salt or not expected_hex:
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return hmac.compare_digest(candidate, expected_hex)


def verify_credentials(username: str, password: str, users: list[UserConfig]) -> Optional[UserConfig]:
    """Return the matched user if credentials are valid."""
    found_user: Optional[UserConfig] = None
    for user in users:
        if hmac.compare_digest(user.username, username):
            found_user = user
            break
    if found_user is None:
        return None
    if not verify_password(password, found_user.password_hash):
        return None
    return found_user


def create_session_token(username: str, secret: str, ttl_seconds: int, now: Optional[int] = None) -> str:
    """Create signed session token."""
    issued = int(now if now is not None else time.time())
    payload = {
        "u": username,
        "iat": issued,
        "exp": issued + int(ttl_seconds),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    return f"{_b64url_encode(payload_bytes)}.{_b64url_encode(signature)}"


def decode_session_token(token: str, secret: str, now: Optional[int] = None) -> Optional[dict[str, int | str]]:
    """Decode and verify token, returning payload dict."""
    if not token or "." not in token:
        return None
    payload_part, sig_part = token.split(".", 1)
    try:
        payload_bytes = _b64url_decode(payload_part)
        signature = _b64url_decode(sig_part)
    except Exception:
        return None

    expected_sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_sig):
        return None

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    username = payload.get("u")
    exp = payload.get("exp")
    if not isinstance(username, str) or not isinstance(exp, int):
        return None
    current = int(now if now is not None else time.time())
    if exp <= current:
        return None
    return payload
