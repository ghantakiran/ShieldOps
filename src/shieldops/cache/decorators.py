"""Caching decorators for async functions.

Provides ``@cached`` for transparent read-through caching and
``@cache_invalidate`` for clearing a namespace after write operations.
"""

from __future__ import annotations

import functools
import hashlib
from collections.abc import Callable
from typing import Any

import structlog

logger = structlog.get_logger()

# Module-level reference to the active RedisCache instance.
# Set via ``set_cache()`` at application startup.
_cache_instance: Any = None


def set_cache(cache: Any) -> None:
    """Wire the global cache instance used by decorators."""
    global _cache_instance
    _cache_instance = cache


def get_cache() -> Any:
    """Return the global cache instance (may be ``None``)."""
    return _cache_instance


def _build_cache_key(
    func: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]
) -> str:
    """Deterministic cache key from function name + arguments."""
    parts = [func.__qualname__]
    for arg in args:
        parts.append(str(arg))
    for k, v in sorted(kwargs.items()):
        parts.append(f"{k}={v}")
    raw = ":".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def cached(
    ttl: int = 300,
    namespace: str = "default",
) -> Callable[..., Any]:
    """Decorator that caches the return value of an async function.

    Usage::

        @cached(ttl=300, namespace="investigations")
        async def list_investigations(...):
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache = _cache_instance
            if cache is None:
                # Cache not available -- fall through to the real function
                return await func(*args, **kwargs)

            key = _build_cache_key(func, args, kwargs)
            cached_value = await cache.get(key, namespace=namespace)
            if cached_value is not None:
                return cached_value

            result = await func(*args, **kwargs)
            await cache.set(key, result, ttl=ttl, namespace=namespace)
            return result

        return wrapper

    return decorator


def cache_invalidate(
    namespace: str = "default",
) -> Callable[..., Any]:
    """Decorator that clears a cache namespace after a write operation.

    Usage::

        @cache_invalidate(namespace="investigations")
        async def save_investigation(...):
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)

            cache = _cache_instance
            if cache is not None:
                pattern = f"{namespace}:*"
                await cache.invalidate_pattern(pattern)
                logger.debug(
                    "cache_namespace_invalidated",
                    namespace=namespace,
                    trigger=func.__qualname__,
                )

            return result

        return wrapper

    return decorator
