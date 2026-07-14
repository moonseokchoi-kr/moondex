"""Project-local configuration with secure defaults."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 1,
    "knowledge_sync": {"enabled": False},
    "ci": {"required_check_name": "moondex-verify"},
    "security": {"secret_scan": True, "protected_paths": []},
}


class ConfigError(ValueError):
    """Raised when project configuration cannot safely be used."""


def default_config() -> dict[str, Any]:
    return deepcopy(DEFAULT_CONFIG)


def load_config(path: Path) -> dict[str, Any]:
    """Load a project configuration, returning secure defaults when absent."""

    if not path.exists():
        return default_config()

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"Cannot read configuration {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Configuration {path} is not valid JSON: {exc.msg}") from exc

    return validate_config(payload, path)


def validate_config(payload: object, path: Path | None = None) -> dict[str, Any]:
    """Validate the small, explicit configuration contract."""

    source = str(path) if path else "configuration"
    if not isinstance(payload, dict):
        raise ConfigError(f"{source} must contain a JSON object.")
    if payload.get("schema_version", 1) != 1:
        raise ConfigError(f"{source} has unsupported schema_version; expected 1.")

    config = default_config()
    config["schema_version"] = 1

    for section in ("knowledge_sync", "ci", "security"):
        value = payload.get(section, {})
        if not isinstance(value, dict):
            raise ConfigError(f"{source}.{section} must be an object.")
        config[section].update(value)

    _validate_knowledge_sync(config["knowledge_sync"], source)
    _validate_ci(config["ci"], source)
    _validate_security(config["security"], source)
    return config


def _validate_knowledge_sync(value: dict[str, Any], source: str) -> None:
    if not isinstance(value.get("enabled"), bool):
        raise ConfigError(f"{source}.knowledge_sync.enabled must be true or false.")
    if not value["enabled"]:
        return

    required = ("destination", "credential_source", "retention_policy")
    missing = [key for key in required if not isinstance(value.get(key), str) or not value[key].strip()]
    if missing:
        names = ", ".join(missing)
        raise ConfigError(
            "Enabled knowledge sync requires destination, credential_source, and "
            f"retention_policy; missing: {names}."
        )


def _validate_ci(value: dict[str, Any], source: str) -> None:
    name = value.get("required_check_name")
    if not isinstance(name, str) or not name.strip():
        raise ConfigError(f"{source}.ci.required_check_name must be a non-empty string.")


def _validate_security(value: dict[str, Any], source: str) -> None:
    if not isinstance(value.get("secret_scan"), bool):
        raise ConfigError(f"{source}.security.secret_scan must be true or false.")
    paths = value.get("protected_paths")
    if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
        raise ConfigError(f"{source}.security.protected_paths must be a list of strings.")

