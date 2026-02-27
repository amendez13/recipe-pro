"""Configuration management for Idea Canvas."""

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
class Config:
    web: WebConfig = field(default_factory=WebConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)


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

    return config


def get_default_config_path() -> Path:
    candidates = [
        Path("config/config.local.yaml"),
        Path("config/config.yaml"),
        Path.home() / ".config" / "idea-canvas" / "config.yaml",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[1]
