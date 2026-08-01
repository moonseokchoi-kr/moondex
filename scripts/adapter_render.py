"""Shared presentation boundary for portable skill adapters."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any


_SENSITIVE_KEY_SUFFIXES = (
    "token",
    "secret",
    "password",
    "authorization",
    "apikey",
    "credential",
    "bearer",
)
_SENSITIVE_FLAG = re.compile(
    r"^--?(?:password|passwd|token|secret|authorization|api[-_]?key|credential)$",
    re.IGNORECASE,
)
_SENSITIVE_FLAG_VALUE = re.compile(
    r"(?P<flag>--?(?:password|passwd|token|secret|authorization|api[-_]?key|credential))"
    r"=(?P<value>[^\s]+)",
    re.IGNORECASE,
)
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?P<label>\b(?:password|passwd|token|secret|api[-_]?key|credential)\b"
    r"\s*[:=]\s*)(?P<value>(?:Bearer\s+)?[^\s,;]+)",
    re.IGNORECASE,
)
_AUTHORIZATION_HEADER = re.compile(
    r"(?P<prefix>^|\r\n|\r|\n|\\+(?:r\\+n|[rn])|[^A-Za-z0-9_-])"
    r"(?P<label>(?:Proxy-Authorization|Authorization)[ \t]*:[ \t]*)"
    r"(?P<value>(?:(?!\\+(?:r\\+n|[rn]))[^\r\n])*)"
    r"(?=\r\n|\r|\n|\\+(?:r\\+n|[rn])|$)",
    re.IGNORECASE,
)
_BEARER_VALUE = re.compile(r"(?P<label>\bBearer\s+)(?P<value>[^\s,;]+)", re.IGNORECASE)
_RAW_CREDENTIAL = re.compile(
    r"gh[pousr]_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]+|AKIA[A-Z0-9]{16}",
    re.IGNORECASE,
)
_TEST_LITERAL = re.compile(r"\b(?:secret|token)[-_]literal\b", re.IGNORECASE)


def _is_sensitive_key(key: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
    return any(normalized.endswith(part) for part in _SENSITIVE_KEY_SUFFIXES)


def _redact_text(value: str) -> str:
    """Redact credential values while retaining harmless command context."""
    if _TEST_LITERAL.search(value):
        return "[REDACTED]"
    rendered = _SENSITIVE_FLAG_VALUE.sub(lambda match: f"{match.group('flag')}=[REDACTED]", value)
    rendered = _AUTHORIZATION_HEADER.sub(_redact_authorization_header, rendered)
    rendered = _SENSITIVE_ASSIGNMENT.sub(lambda match: f"{match.group('label')}[REDACTED]", rendered)
    rendered = _BEARER_VALUE.sub(lambda match: f"{match.group('label')}[REDACTED]", rendered)
    rendered = _RAW_CREDENTIAL.sub("[REDACTED]", rendered)
    return rendered[:4000]


def _redact_authorization_header(match: re.Match[str]) -> str:
    """Mask a complete HTTP authorization field value, including its auth scheme.

    RFC authorization values contain an auth scheme followed by credentials or
    parameters. Requiring that second component keeps prose such as
    ``authorization: approved`` readable while still covering standard and
    extension schemes. The field value runs to the line boundary, so Digest
    parameters and opaque suffixes cannot survive the presentation boundary.
    """
    value = match.group("value")
    stripped = value.rstrip(" \t")
    trailing = value[len(stripped):]
    if re.fullmatch(r"[^\s,;]+[ \t]+\S.*", stripped) is None:
        return match.group(0)
    return f"{match.group('prefix')}{match.group('label')}[REDACTED]{trailing}"


def _redact_list(value: list[Any] | tuple[Any, ...]) -> list[Any]:
    rendered: list[Any] = []
    redact_next = False
    for item in value:
        if redact_next:
            rendered.append("[REDACTED]")
            redact_next = False
            continue
        rendered.append(redact(item))
        redact_next = isinstance(item, str) and _SENSITIVE_FLAG.fullmatch(item) is not None
    return rendered


def redact(value: Any) -> Any:
    """Return a JSON-compatible redacted view without changing raw evidence."""
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if _is_sensitive_key(key) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return _redact_list(value)
    if isinstance(value, tuple):
        return _redact_list(value)
    if isinstance(value, str):
        return _redact_text(value)
    return value


def rendered_json(value: Any) -> str:
    """Serialize only the redacted presentation view."""
    return json.dumps(redact(value), sort_keys=True)


def write_rendered_json(path: Path, value: Any) -> None:
    """Atomically write a redacted report or explicit export."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as output:
            output.write(rendered_json(value))
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
            temporary = output.name
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            try:
                Path(temporary).unlink()
            except FileNotFoundError:
                pass
