"""HTTP client utilities for CLI commands."""

from __future__ import annotations

from typing import Any

import click
import httpx

from shieldops.cli.output import print_error

# Default timeout for all API requests (seconds)
DEFAULT_TIMEOUT = 30.0


def get_client(ctx: click.Context) -> httpx.Client:
    """Build an httpx.Client from the Click context.

    Reads ``api_url`` and ``api_key`` from ``ctx.obj`` and returns a
    pre-configured synchronous client with appropriate headers and timeout.
    """
    headers: dict[str, str] = {"Accept": "application/json"}
    api_key: str | None = ctx.obj.get("api_key")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    base_url: str = ctx.obj.get("api_url", "http://localhost:8000/api/v1")
    return httpx.Client(
        base_url=base_url,
        headers=headers,
        timeout=DEFAULT_TIMEOUT,
    )


def api_request(
    ctx: click.Context,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any] | list[Any] | None:
    """Execute an API request and return parsed JSON, or None on failure.

    Handles connection errors, HTTP error codes, and JSON parse failures
    gracefully -- printing user-friendly messages to stderr and returning
    ``None`` so callers can short-circuit.
    """
    # Strip None values from params
    if params:
        params = {k: v for k, v in params.items() if v is not None}

    try:
        with get_client(ctx) as client:
            response = client.request(
                method,
                path,
                json=json_body,
                params=params or None,
            )
    except httpx.ConnectError:
        print_error(f"Could not connect to API at {ctx.obj.get('api_url')}. Is the server running?")
        return None
    except httpx.TimeoutException:
        print_error("Request timed out. The server may be under heavy load.")
        return None
    except httpx.HTTPError as exc:
        print_error(f"HTTP error: {exc}")
        return None

    if response.status_code >= 400:
        _handle_error_response(response)
        return None

    # 204 No Content
    if response.status_code == 204:
        return {}

    try:
        return response.json()  # type: ignore[no-any-return]
    except Exception:
        print_error("Failed to parse API response as JSON.")
        return None


def _handle_error_response(response: httpx.Response) -> None:
    """Print a user-friendly message for HTTP error responses."""
    try:
        body = response.json()
        detail = body.get("detail", response.text)
    except Exception:
        detail = response.text

    if response.status_code == 401:
        print_error("Authentication required. Set SHIELDOPS_API_KEY or use --api-key.")
    elif response.status_code == 403:
        print_error(f"Permission denied: {detail}")
    elif response.status_code == 404:
        print_error(f"Not found: {detail}")
    else:
        print_error(f"API error ({response.status_code}): {detail}")
