"""Tiny compatibility layer for the shared client supplied by the foundation."""

from collections.abc import Mapping
from typing import Any


def get_json(client: Any, path: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Call any of the supported shared-client interfaces.

    The foundation client is intentionally allowed to evolve.  Supporting the
    common ``get_json`` and ``request_json`` spellings keeps these endpoint
    modules independently testable with a simple fake client.
    """
    for name in ("get_json", "request_json", "get"):
        method = getattr(client, name, None)
        if method is None:
            continue
        response = method(path, params=params) if params is not None else method(path)
        # The shared NHLHTTPClient returns (payload, raw-response metadata).
        if isinstance(response, tuple) and response:
            response = response[0]
        if hasattr(response, "json"):
            response = response.json()
        if not isinstance(response, dict):
            raise TypeError(f"NHL endpoint {path!r} returned {type(response).__name__}, expected object")
        return response
    raise TypeError("client must expose get_json(path, params=...), request_json, or get")
