"""Unit tests for the two pieces that handle untrusted input."""

from __future__ import annotations

import pytest

from app.core.net import UnsafeTargetError, validate_target
from app.services.templating import placeholders, render


def test_paths_resolve_through_dicts_and_lists() -> None:
    payload = {"order": {"id": 7, "items": [{"sku": "A-1"}, {"sku": "B-2"}]}}
    assert render("{{order.id}} / {{order.items.1.sku}}", payload).text == "7 / B-2"


def test_values_are_stringified_predictably() -> None:
    payload = {"n": 49.99, "flag": True, "none": None, "obj": {"a": 1}}
    assert render("{{n}} {{flag}} {{obj}}", payload).text == '49.99 true {"a":1}'


def test_a_missing_path_renders_empty_and_is_reported() -> None:
    result = render("Hi {{customer.name}}!", {"customer": {}})
    assert result.text == "Hi !"
    assert result.missing == ["customer.name"]


def test_placeholders_are_not_evaluated() -> None:
    """Whatever the payload contains, it is data -- never an expression."""
    payload = {"x": "{{y}}", "y": "leaked"}
    assert render("{{x}}", payload).text == "{{y}}"


def test_json_mode_escapes_values_so_the_document_survives() -> None:
    import json

    payload = {"customer": 'Alex "The Quote" O\'Brien\nsecond line'}
    body = render('{"who": "{{customer}}"}', payload, json_string=True).text
    assert json.loads(body)["who"] == payload["customer"]


def test_placeholders_lists_every_referenced_path() -> None:
    assert placeholders("{{a}} {{ b.c }} {{a}}") == ["a", "b.c"]


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/x",
        "https://user:pass@example.com/x",
        "not-a-url",
    ],
)
def test_obviously_bad_targets_are_refused(url: str, monkeypatch) -> None:
    with pytest.raises(UnsafeTargetError):
        validate_target(url)


def test_private_addresses_are_refused_when_the_guard_is_on(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.core.net.settings.allow_private_network_targets", False, raising=False
    )
    for url in (
        "http://127.0.0.1:8000/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.0.0.5/internal",
    ):
        with pytest.raises(UnsafeTargetError):
            validate_target(url)


def test_public_https_targets_pass(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.core.net.settings.allow_private_network_targets", False, raising=False
    )
    assert validate_target("https://93.184.216.34/webhook") is not None
