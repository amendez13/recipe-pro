from app.auth import create_session_token, decode_session_token, hash_password, verify_credentials
from app.config import UserConfig


def test_hash_and_verify_credentials():
    hashed = hash_password("secret-password")
    users = [
        UserConfig(username="alice", password_hash=hashed, db_path="data/alice.db"),
        UserConfig(username="bob", password_hash=hash_password("bob-password"), db_path="data/bob.db"),
    ]

    assert verify_credentials("alice", "secret-password", users) is not None
    assert verify_credentials("alice", "wrong", users) is None
    assert verify_credentials("charlie", "secret-password", users) is None


def test_session_token_roundtrip_and_tamper_detection():
    token = create_session_token("alice", "top-secret", ttl_seconds=300, now=1_000)
    payload = decode_session_token(token, "top-secret", now=1_100)
    assert payload is not None
    assert payload["u"] == "alice"

    assert decode_session_token(token, "wrong-secret", now=1_100) is None
    assert decode_session_token(token + "x", "top-secret", now=1_100) is None
    assert decode_session_token(token, "top-secret", now=1_301) is None
