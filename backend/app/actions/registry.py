"""Action lookup, config validation and secret handling.

The registry is the only place that knows which config fields are secret, so
encryption at rest and redaction on the way out cannot drift apart.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from app.actions.base import Action
from app.actions.discord import DiscordAction
from app.actions.http import HttpAction
from app.actions.telegram import TelegramAction
from app.core.security import decrypt_secret, encrypt_secret

REDACTED = "••••••••"

ACTIONS: dict[str, Action] = {
    action.type: action
    for action in (DiscordAction(), TelegramAction(), HttpAction())
}


class ConfigError(ValueError):
    """The configuration does not fit the chosen action."""


def get_action(action_type: str) -> Action:
    try:
        return ACTIONS[action_type]
    except KeyError:
        raise ConfigError(f"Unknown action type '{action_type}'") from None


def describe_actions() -> list[dict[str, Any]]:
    """Powers the action picker in the UI, straight from the adapters."""
    return [
        {
            "type": action.type,
            "label": action.label,
            "description": action.description,
            "secret_fields": list(action.secret_fields),
            "schema": action.config_model.model_json_schema(),
        }
        for action in ACTIONS.values()
    ]


def validate_config(action_type: str, raw: dict[str, Any]) -> BaseModel:
    action = get_action(action_type)
    try:
        return action.config_model.model_validate(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        field = ".".join(str(part) for part in first["loc"]) or "config"
        raise ConfigError(f"{field}: {first['msg']}") from exc


def encrypt_config(action_type: str, config: BaseModel) -> dict[str, Any]:
    """Serialise for storage, with the adapter's secret fields encrypted."""
    action = get_action(action_type)
    data = config.model_dump(mode="json")
    for name in action.secret_fields:
        value = data.get(name)
        if value in (None, "", {}):
            continue
        data[name] = {"__enc__": encrypt_secret(_to_text(value))}
    return data


def decrypt_config(action_type: str, stored: dict[str, Any]) -> BaseModel:
    """Rebuild the validated config an adapter runs with."""
    action = get_action(action_type)
    data = dict(stored)
    for name in action.secret_fields:
        value = data.get(name)
        if isinstance(value, dict) and "__enc__" in value:
            plain = decrypt_secret(value["__enc__"])
            if plain is None:
                raise ConfigError(
                    f"Stored {name} could not be decrypted -- was SECRET_KEY rotated?"
                )
            data[name] = _from_text(plain)
    return action.config_model.model_validate(data)


def redact_config(action_type: str, stored: dict[str, Any]) -> dict[str, Any]:
    """What the API is allowed to show: secrets replaced, never decrypted."""
    action = get_action(action_type)
    data: dict[str, Any] = {}
    for key, value in stored.items():
        if key in action.secret_fields:
            if isinstance(value, dict) and "__enc__" in value:
                data[key] = REDACTED
            elif isinstance(value, dict):
                data[key] = {name: REDACTED for name in value}
            else:
                data[key] = REDACTED
        else:
            data[key] = value
    return data


def _to_text(value: Any) -> str:
    import json

    return value if isinstance(value, str) else json.dumps(value)


def _from_text(text: str) -> Any:
    import json

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text
