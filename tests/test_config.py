from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_core.cli import main
from harness_core.config import ConfigError, load_config


def test_missing_config_uses_secure_defaults(tmp_path: Path) -> None:
    config = load_config(tmp_path / ".harness" / "config.json")

    assert config["knowledge_sync"] == {"enabled": False}
    assert config["security"]["secret_scan"] is True
    assert config["ci"]["required_check_name"] == "moondex-verify"


def test_enabled_sync_requires_organization_settings(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"knowledge_sync": {"enabled": True}}), encoding="utf-8")

    with pytest.raises(ConfigError, match="missing: destination, credential_source, retention_policy"):
        load_config(path)


def test_valid_enabled_sync_is_loaded(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "knowledge_sync": {
                    "enabled": True,
                    "destination": "company-knowledge",
                    "credential_source": "environment",
                    "retention_policy": "90-days",
                }
            }
        ),
        encoding="utf-8",
    )

    assert load_config(path)["knowledge_sync"]["destination"] == "company-knowledge"


def test_doctor_returns_actionable_error_for_invalid_config(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "config.json"
    path.write_text("not-json", encoding="utf-8")

    assert main(["doctor", "--config", str(path)]) == 2
    assert "CONFIG_INVALID" in capsys.readouterr().out


def test_default_configuration_contains_no_personal_absolute_path() -> None:
    serialized = json.dumps(load_config(Path("does-not-exist.json")))

    assert "/Users/" not in serialized

