"""Outbound URL validation -- the SSRF guard.

Every action adapter resolves its destination through :func:`validate_target`
before a request is made, so a workflow cannot be pointed at the machine's own
metadata service, a database on the private network, or ``localhost``.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import settings

ALLOWED_SCHEMES = {"http", "https"}


class UnsafeTargetError(ValueError):
    """The configured URL may not be called."""


def validate_target(url: str, *, require_https: bool = False) -> str:
    """Return the URL unchanged, or raise :class:`UnsafeTargetError`."""
    parsed = urlparse(url.strip())

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UnsafeTargetError("URL must start with http:// or https://")
    if require_https and parsed.scheme != "https":
        raise UnsafeTargetError("URL must use https://")
    if not parsed.hostname:
        raise UnsafeTargetError("URL has no host")
    if parsed.username or parsed.password:
        raise UnsafeTargetError("Credentials in the URL are not allowed")

    if settings.allow_private_network_targets:
        return url

    for address in _resolve(parsed.hostname):
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            raise UnsafeTargetError(
                f"{parsed.hostname} resolves to a private address ({address}); "
                "outbound actions may only target public hosts"
            )
    return url


def _resolve(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return [ipaddress.ip_address(hostname)]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsafeTargetError(f"{hostname} could not be resolved") from exc
    return [ipaddress.ip_address(info[4][0]) for info in infos]
