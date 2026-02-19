"""Redis-based distributed lock using SET NX EX pattern.

Ensures only one instance of a job runs at a time across multiple
ShieldOps API instances.  Uses a unique UUID per acquisition so that
only the lock owner can release, and an auto-renewal background task
to prevent expiry during long-running operations.

Usage::

    lock = DistributedLock(redis_url, "my-job", ttl=300)
    async with lock as acquired:
        if acquired:
            await do_work()
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid

import redis.asyncio as aioredis
import structlog

logger = structlog.get_logger()

# Lua script: atomic release -- only delete if value matches (CAS).
_RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

# Lua script: atomic renew -- extend TTL only if we still own the lock.
_RENEW_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("pexpire", KEYS[1], ARGV[2])
else
    return 0
end
"""

KEY_PREFIX = "shieldops:lock"


class DistributedLock:
    """Redis-based distributed lock with auto-renewal.

    Parameters
    ----------
    redis_url:
        Redis connection URL (e.g. ``redis://localhost:6379/0``).
    lock_name:
        Logical name for the lock.  The Redis key will be
        ``shieldops:lock:{lock_name}``.
    ttl:
        Time-to-live in seconds for the lock key.  Must be > 0.
    retry_interval:
        Seconds to wait between acquisition retries.
    max_retries:
        Maximum number of retry attempts after the first failure.
        ``0`` means no retries (single attempt).
    """

    def __init__(
        self,
        redis_url: str,
        lock_name: str,
        ttl: int = 300,
        retry_interval: float = 1.0,
        max_retries: int = 0,
    ) -> None:
        if ttl <= 0:
            raise ValueError(f"ttl must be positive, got {ttl}")
        self._redis_url = redis_url
        self._lock_name = lock_name
        self._ttl = ttl
        self._retry_interval = retry_interval
        self._max_retries = max_retries
        self._lock_value: str | None = None
        self._client: aioredis.Redis | None = None  # type: ignore[type-arg]
        self._renewal_task: asyncio.Task[None] | None = None

    # -- properties ----------------------------------------------------------

    @property
    def key(self) -> str:
        """Full Redis key for this lock."""
        return f"{KEY_PREFIX}:{self._lock_name}"

    @property
    def lock_value(self) -> str | None:
        """UUID value identifying the current lock owner."""
        return self._lock_value

    # -- internal helpers ----------------------------------------------------

    async def _ensure_client(self) -> aioredis.Redis:  # type: ignore[type-arg]
        if self._client is None:
            self._client = aioredis.from_url(  # type: ignore[no-untyped-call]
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
            )
        return self._client

    async def _close_client(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # -- core operations -----------------------------------------------------

    async def acquire(self) -> bool:
        """Attempt to acquire the lock.

        If ``max_retries > 0``, will retry with ``retry_interval``
        between attempts.  On success, starts the auto-renewal
        background task.

        Returns ``True`` if the lock was acquired, ``False`` otherwise.
        """
        client = await self._ensure_client()
        self._lock_value = uuid.uuid4().hex
        attempts = 1 + self._max_retries

        for attempt in range(attempts):
            acquired: bool = await client.set(  # type: ignore[assignment]
                self.key,
                self._lock_value,
                nx=True,
                ex=self._ttl,
            )
            if acquired:
                logger.info(
                    "lock_acquired",
                    lock=self._lock_name,
                    ttl=self._ttl,
                    attempt=attempt + 1,
                )
                self._renewal_task = asyncio.create_task(
                    self._auto_renew(),
                    name=f"lock-renew:{self._lock_name}",
                )
                return True

            if attempt < attempts - 1:
                logger.debug(
                    "lock_acquire_retry",
                    lock=self._lock_name,
                    attempt=attempt + 1,
                    max_retries=self._max_retries,
                )
                await asyncio.sleep(self._retry_interval)

        logger.info(
            "lock_acquire_failed",
            lock=self._lock_name,
            attempts=attempts,
        )
        self._lock_value = None
        return False

    async def release(self) -> bool:
        """Release the lock if we still own it (CAS via Lua script).

        Cancels the auto-renewal task.  Returns ``True`` if the lock
        was successfully released, ``False`` if it was already expired
        or owned by another instance.
        """
        # Cancel renewal first regardless of release outcome
        await self._cancel_renewal()

        if self._lock_value is None:
            return False

        try:
            client = await self._ensure_client()
            result = await client.eval(  # type: ignore[union-attr,misc]
                _RELEASE_SCRIPT, 1, self.key, self._lock_value
            )
            released: bool = result == 1
            if released:
                logger.info("lock_released", lock=self._lock_name)
            else:
                logger.warning(
                    "lock_release_failed_not_owner",
                    lock=self._lock_name,
                )
            return released
        except Exception:
            logger.exception("lock_release_error", lock=self._lock_name)
            return False
        finally:
            self._lock_value = None
            await self._close_client()

    async def renew(self) -> bool:
        """Extend the lock TTL if we still own it.

        Returns ``True`` if renewed, ``False`` if the lock is no
        longer ours (or does not exist).
        """
        if self._lock_value is None:
            return False

        try:
            client = await self._ensure_client()
            ttl_ms = self._ttl * 1000
            result = await client.eval(  # type: ignore[union-attr,misc]
                _RENEW_SCRIPT,
                1,
                self.key,
                self._lock_value,
                str(ttl_ms),
            )
            renewed: bool = result == 1
            if renewed:
                logger.debug(
                    "lock_renewed",
                    lock=self._lock_name,
                    ttl=self._ttl,
                )
            else:
                logger.warning(
                    "lock_renew_failed_not_owner",
                    lock=self._lock_name,
                )
            return renewed
        except Exception:
            logger.exception("lock_renew_error", lock=self._lock_name)
            return False

    # -- auto-renewal --------------------------------------------------------

    async def _auto_renew(self) -> None:
        """Background task that renews the lock at ``ttl / 2``."""
        interval = self._ttl / 2
        try:
            while True:
                await asyncio.sleep(interval)
                if not await self.renew():
                    logger.warning(
                        "auto_renew_stopped",
                        lock=self._lock_name,
                        reason="renew_failed",
                    )
                    break
        except asyncio.CancelledError:
            logger.debug(
                "auto_renew_cancelled",
                lock=self._lock_name,
            )

    async def _cancel_renewal(self) -> None:
        """Cancel the auto-renewal task if running."""
        if self._renewal_task is not None:
            self._renewal_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._renewal_task
            self._renewal_task = None

    # -- context manager -----------------------------------------------------

    async def __aenter__(self) -> bool:
        """Acquire the lock and return whether it was obtained."""
        return await self.acquire()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Release the lock on context exit."""
        await self.release()
