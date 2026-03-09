"""Tool functions for the Enterprise Integration Agent.

These bridge enterprise connectors, notification dispatchers, and the
integration repository to the agent's LangGraph nodes.  Each tool is a
self-contained async function that queries or mutates external systems and
returns structured data.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from shieldops.agents.enterprise_integration.models import (
    IntegrationConfig,
    IntegrationDirection,
    IntegrationHealth,
    IntegrationStatus,
    SyncEvent,
)

logger = structlog.get_logger()


class IntegrationToolkit:
    """Collection of tools available to the Enterprise Integration Agent.

    Injected into nodes at graph construction time to decouple agent logic
    from specific connector implementations.
    """

    def __init__(
        self,
        connector_router: Any | None = None,
        notification_dispatcher: Any | None = None,
        repository: Any | None = None,
    ) -> None:
        self._router = connector_router
        self._dispatcher = notification_dispatcher
        self._repository = repository

    async def check_health(self, integration_id: str) -> IntegrationHealth:
        """Ping the integration endpoint, check auth, and verify connectivity.

        Returns an IntegrationHealth snapshot.
        """
        logger.info("integration_health_check", integration_id=integration_id)

        if self._repository is not None:
            try:
                raw = await self._repository.get_integration_health(integration_id)
                if raw:
                    return IntegrationHealth.model_validate(raw)
            except Exception as e:
                logger.error(
                    "health_check_repo_failed",
                    integration_id=integration_id,
                    error=str(e),
                )

        # Fallback: construct a default health snapshot
        return IntegrationHealth(
            integration_id=integration_id,
            status=IntegrationStatus.DISCONNECTED,
            last_health_check=datetime.now(UTC),
            error_message="No repository available for health data",
        )

    async def get_sync_history(
        self,
        integration_id: str,
        hours: int = 24,
    ) -> list[SyncEvent]:
        """Retrieve recent sync events for the integration.

        Args:
            integration_id: The integration to query.
            hours: How many hours of history to retrieve.

        Returns:
            A list of SyncEvent records, most recent first.
        """
        if self._repository is None:
            return []

        since = datetime.now(UTC) - timedelta(hours=hours)
        try:
            raw_events: list[dict[str, Any]] = await self._repository.get_sync_events(
                integration_id, since=since
            )
            return [SyncEvent.model_validate(e) for e in raw_events]
        except Exception as e:
            logger.error(
                "sync_history_failed",
                integration_id=integration_id,
                error=str(e),
            )
            return []

    async def test_authentication(self, config: IntegrationConfig) -> dict[str, Any]:
        """Validate that the integration's credentials or tokens are still valid.

        Returns a dict with ``valid`` (bool), ``message``, and ``expires_at`` if
        applicable.
        """
        logger.info(
            "integration_test_auth",
            integration_id=config.id,
            auth_type=config.auth_type,
        )

        if self._router is None:
            return {
                "valid": False,
                "message": "No connector router available",
                "expires_at": None,
            }

        try:
            connector = self._router.get(config.provider)
            result: dict[str, Any] = await connector.test_auth(config.endpoint_url)
            return {
                "valid": result.get("valid", False),
                "message": result.get("message", ""),
                "expires_at": result.get("expires_at"),
            }
        except (ValueError, Exception) as e:
            logger.error(
                "auth_test_failed",
                integration_id=config.id,
                error=str(e),
            )
            return {"valid": False, "message": str(e), "expires_at": None}

    async def measure_latency(self, endpoint_url: str) -> dict[str, Any]:
        """Measure round-trip latency to the integration endpoint.

        Returns ``latency_ms``, ``reachable`` (bool), and ``status_code`` if
        applicable.
        """
        logger.info("integration_measure_latency", endpoint_url=endpoint_url)

        if self._router is None:
            return {"latency_ms": -1, "reachable": False, "status_code": None}

        try:
            start = datetime.now(UTC)
            connector = self._router.get("http")
            result: dict[str, Any] = await connector.ping(endpoint_url)
            elapsed_ms = int((datetime.now(UTC) - start).total_seconds() * 1000)
            return {
                "latency_ms": elapsed_ms,
                "reachable": result.get("reachable", True),
                "status_code": result.get("status_code"),
            }
        except Exception as e:
            logger.error(
                "latency_measure_failed",
                endpoint_url=endpoint_url,
                error=str(e),
            )
            return {"latency_ms": -1, "reachable": False, "status_code": None}

    async def get_rate_limit_status(
        self,
        integration_id: str,
    ) -> dict[str, Any]:
        """Return current rate-limit usage for the integration.

        Returns ``requests_used``, ``requests_remaining``, ``reset_at``.
        """
        if self._repository is None:
            return {
                "requests_used": 0,
                "requests_remaining": -1,
                "reset_at": None,
            }

        try:
            raw: dict[str, Any] = await self._repository.get_rate_limit_status(integration_id)
            return {
                "requests_used": raw.get("requests_used", 0),
                "requests_remaining": raw.get("requests_remaining", -1),
                "reset_at": raw.get("reset_at"),
            }
        except Exception as e:
            logger.error(
                "rate_limit_status_failed",
                integration_id=integration_id,
                error=str(e),
            )
            return {
                "requests_used": 0,
                "requests_remaining": -1,
                "reset_at": None,
            }

    async def trigger_sync(
        self,
        integration_id: str,
        direction: IntegrationDirection,
    ) -> SyncEvent | None:
        """Manually trigger a data sync for the integration.

        Returns the resulting SyncEvent, or None on failure.
        """
        logger.info(
            "integration_trigger_sync",
            integration_id=integration_id,
            direction=direction,
        )

        if self._repository is None:
            return None

        try:
            raw: dict[str, Any] = await self._repository.trigger_sync(
                integration_id,
                direction=direction.value,
            )
            return SyncEvent.model_validate(raw)
        except Exception as e:
            logger.error(
                "trigger_sync_failed",
                integration_id=integration_id,
                error=str(e),
            )
            return None

    async def get_error_logs(
        self,
        integration_id: str,
        hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Retrieve error logs for the integration over the given window.

        Returns a list of log-entry dicts with ``timestamp``, ``level``,
        ``message``, and optional ``details``.
        """
        if self._repository is None:
            return []

        since = datetime.now(UTC) - timedelta(hours=hours)
        try:
            logs: list[dict[str, Any]] = await self._repository.get_integration_error_logs(
                integration_id,
                since=since,
            )
            return logs[:200]  # Cap for LLM context
        except Exception as e:
            logger.error(
                "error_logs_failed",
                integration_id=integration_id,
                error=str(e),
            )
            return []

    async def rotate_credentials(
        self,
        integration_id: str,
    ) -> dict[str, Any]:
        """Rotate API keys or tokens for the integration.

        Returns ``rotated`` (bool), ``new_expiry``, and ``message``.
        """
        logger.info(
            "integration_rotate_credentials",
            integration_id=integration_id,
        )

        if self._router is None:
            return {
                "rotated": False,
                "new_expiry": None,
                "message": "No connector router available",
            }

        try:
            if self._repository is None:
                return {
                    "rotated": False,
                    "new_expiry": None,
                    "message": "No repository available for credential storage",
                }

            result: dict[str, Any] = await self._repository.rotate_integration_credentials(
                integration_id
            )
            return {
                "rotated": result.get("rotated", False),
                "new_expiry": result.get("new_expiry"),
                "message": result.get("message", "Credentials rotated"),
            }
        except Exception as e:
            logger.error(
                "credential_rotation_failed",
                integration_id=integration_id,
                error=str(e),
            )
            return {"rotated": False, "new_expiry": None, "message": str(e)}

    async def update_config(
        self,
        integration_id: str,
        updates: dict[str, Any],
    ) -> IntegrationConfig | None:
        """Update integration configuration fields.

        Args:
            integration_id: The integration to update.
            updates: A dict of field names to new values.

        Returns:
            The updated IntegrationConfig, or None on failure.
        """
        logger.info(
            "integration_update_config",
            integration_id=integration_id,
            update_keys=list(updates.keys()),
        )

        if self._repository is None:
            return None

        try:
            raw: dict[str, Any] = await self._repository.update_integration_config(
                integration_id,
                updates,
            )
            return IntegrationConfig.model_validate(raw)
        except Exception as e:
            logger.error(
                "config_update_failed",
                integration_id=integration_id,
                error=str(e),
            )
            return None
