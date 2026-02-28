"""Configuration management for Recipe Pro."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class WebConfig:
    host: str = "127.0.0.1"
    port: int = 8084


@dataclass
class DatabaseConfig:
    path: str = "data/ideas.db"


@dataclass
class UserConfig:
    username: str
    password_hash: str
    db_path: str


@dataclass
class AuthConfig:
    users: list[UserConfig] = field(default_factory=list)
    session_secret: str = ""
    session_cookie_name: str = "recipe_pro_session"
    session_max_age_seconds: int = 60 * 60 * 24 * 30
    session_secure: bool = False


@dataclass
class Config:
    web: WebConfig = field(default_factory=WebConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)


def _resolve_env_vars(value: str) -> str:
    if not isinstance(value, str):
        return value

    pattern = r"\$\{([^}]+)\}"
    matches = re.findall(pattern, value)
    for var_name in matches:
        env_value = os.environ.get(var_name, "")
        value = value.replace(f"${{{var_name}}}", env_value)
    return value


def _resolve_env_in_data(data: Any) -> Any:
    if isinstance(data, dict):
        return {key: _resolve_env_in_data(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_resolve_env_in_data(value) for value in data]
    if isinstance(data, str):
        return _resolve_env_vars(data)
    return data


def _expand_path(value: str) -> str:
    if not isinstance(value, str) or value == "":
        return value
    return str(Path(value).expanduser())


def load_config(config_path: str | Path) -> Config:
    config_file = Path(config_path).expanduser()
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_file}")

    with open(config_file, encoding="utf-8") as handle:
        raw_config = yaml.safe_load(handle) or {}

    resolved = _resolve_env_in_data(raw_config)

    config = Config()

    web = resolved.get("web", {})
    config.web = WebConfig(
        host=str(web.get("host", config.web.host)),
        port=int(web.get("port", config.web.port)),
    )

    database = resolved.get("database", {})
    config.database = DatabaseConfig(
        path=_expand_path(str(database.get("path", config.database.path)))
    )

    auth = resolved.get("auth", {})
    raw_users = auth.get("users", [])
    if not isinstance(raw_users, list):
        raise ValueError("Configuration error: auth.users must be a list")
    if len(raw_users) != 2:
        raise ValueError("Configuration error: auth.users must define exactly 2 users")

    users: list[UserConfig] = []
    for index, raw_user in enumerate(raw_users, start=1):
        if not isinstance(raw_user, dict):
            raise ValueError(f"Configuration error: auth.users[{index}] must be an object")
        username = str(raw_user.get("username", "")).strip()
        password_hash = str(raw_user.get("password_hash", "")).strip()
        db_path = _expand_path(str(raw_user.get("db_path", "")).strip())
        if not username:
            raise ValueError(f"Configuration error: auth.users[{index}].username is required")
        if not password_hash:
            raise ValueError(f"Configuration error: auth.users[{index}].password_hash is required")
        if not db_path:
            raise ValueError(f"Configuration error: auth.users[{index}].db_path is required")
        users.append(UserConfig(username=username, password_hash=password_hash, db_path=db_path))
    session_secret = str(auth.get("session_secret", "")).strip()
    if not session_secret:
        raise ValueError("Configuration error: auth.session_secret is required")

    config.auth = AuthConfig(
        users=users,
        session_secret=session_secret,
        session_cookie_name=str(auth.get("session_cookie_name", "recipe_pro_session")).strip()
        or "recipe_pro_session",
        session_max_age_seconds=int(auth.get("session_max_age_seconds", 60 * 60 * 24 * 30)),
        session_secure=bool(auth.get("session_secure", False)),
    )

    return config


def get_default_config_path() -> Path:
    candidates = [
        Path("config/config.local.yaml"),
        Path("config/config.yaml"),
        Path.home() / ".config" / "recipe-pro" / "config.yaml",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[1]
