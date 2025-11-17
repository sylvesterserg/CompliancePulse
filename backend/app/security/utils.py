from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any, Dict

from fastapi import Request

from .config import security_settings


SENSITIVE_KEYS = {"password", "secret", "token", "api_key", "session", "stripe"}


def mask_secret(value: str, visible: int = 4) -> str:
    if value is None:
        return ""
    text = str(value)
    if len(text) <= visible:
        return "*" * len(text)
    return "*" * (len(text) - visible) + text[-visible:]


def sanitize_metadata(metadata: Dict[str, Any] | None) -> Dict[str, Any]:
    if not metadata:
        return {}
    sanitized: Dict[str, Any] = {}
    for key, value in metadata.items():
        if value is None:
            sanitized[key] = None
            continue
        if key.lower() in SENSITIVE_KEYS:
            sanitized[key] = mask_secret(str(value))
        else:
            sanitized[key] = value
    return sanitized


def get_client_context(request: Request | None) -> tuple[str | None, str | None]:
    if request is None:
        return None, None
    client_ip = request.headers.get("x-forwarded-for")
    if client_ip:
        client_ip = client_ip.split(",")[0].strip()
    elif request.client:
        client_ip = request.client.host
    user_agent = request.headers.get("user-agent")
    return client_ip, user_agent


def json_dumps(data: Dict[str, Any]) -> str:
    return json.dumps(data, default=str)


def ensure_command_allowed(command: str) -> None:
    tokens = shlex.split(command)
    if not tokens:
        raise ValueError("Command cannot be empty")
    binary = tokens[0]
    base = Path(binary).name
    allowed = set(security_settings.allowed_commands)
    if base not in allowed and binary not in allowed:
        raise PermissionError(f"Command '{base}' is not permitted by sandbox policy")
    forbidden_tokens = {";", "&&", "||", "`", "$("}
    for token in forbidden_tokens:
        if token in command:
            raise PermissionError("Pipelining and command chaining are disallowed in sandbox mode")
