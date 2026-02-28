from pathlib import Path

import pytest

from app.config import load_config


def write_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_config_requires_exactly_two_users(tmp_path):
    path = write_config(
        tmp_path,
        """
web:
  host: "127.0.0.1"
  port: 8084
auth:
  users:
    - username: "a"
      password_hash: "hash-a"
      db_path: "data/a.db"
""",
    )

    with pytest.raises(ValueError, match="exactly 2 users"):
        load_config(path)


def test_load_config_parses_auth_users(tmp_path):
    path = write_config(
        tmp_path,
        """
web:
  host: "127.0.0.1"
  port: 8084
auth:
  users:
    - username: "alice"
      password_hash: "hash-a"
      db_path: "data/alice.db"
    - username: "bob"
      password_hash: "hash-b"
      db_path: "data/bob.db"
""",
    )

    config = load_config(path)
    assert len(config.auth.users) == 2
    assert config.auth.users[0].username == "alice"
    assert config.auth.users[0].db_path.endswith("data/alice.db")
    assert config.auth.users[1].username == "bob"
