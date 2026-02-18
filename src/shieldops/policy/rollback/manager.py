"""RollbackManager — orchestrates rollback operations for agent actions.

Matches the defensive style of RemediationToolkit.rollback(): never raises,
returns FAILED ActionResult on error, writes audit trail best-effort.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from shieldops.connectors.base import ConnectorRouter
from shieldops.models.base import (
    ActionResult,
    AuditEntry,
    ExecutionStatus,
    RiskLevel,
    Snapshot,
)

if TYPE_CHECKING:
    from shieldops.db.repository import Repository

logger = structlog.get_logger()


class RollbackManager:
    """Orchestrates rollback operations with audit logging.

    Usage:
        manager = RollbackManager(connector_router=router, repository=repo)
        result = await manager.execute_rollback(snapshot, reason="validation_failed")
    """

    def __init__(
        self,
        connector_router: ConnectorRouter | None = None,
        repository: "Repository | None" = None,
    ) -> None:
        self._router = connector_router
        self._repository = repository

    async def execute_rollback(
        self,
        snapshot: Snapshot,
        reason: str = "",
        provider: str = "kubernetes",
    ) -> ActionResult:
        """Rollback to a previous snapshot.

        Never raises — returns FAILED ActionResult on error.
        """
        now = datetime.now(UTC)

        if self._router is None:
            result = ActionResult(
                action_id=f"rollback-{snapshot.id}",
                status=ExecutionStatus.FAILED,
                message="No connector router configured",
                started_at=now,
            )
            await self._write_rollback_audit(snapshot, result, reason)
            return result

        try:
            connector = self._router.get(provider)
            result = await connector.rollback(snapshot.id)
            logger.info(
                "rollback_executed",
                snapshot_id=snapshot.id,
                resource_id=snapshot.resource_id,
                status=result.status,
                reason=reason,
            )
        except Exception as e:
            logger.error(
                "rollback_failed",
                snapshot_id=snapshot.id,
                error=str(e),
            )
            result = ActionResult(
                action_id=f"rollback-{snapshot.id}",
                status=ExecutionStatus.FAILED,
                message=str(e),
                started_at=now,
                error=str(e),
            )

        await self._write_rollback_audit(snapshot, result, reason)
        return result

    async def validate_rollback(
        self,
        resource_id: str,
        provider: str = "kubernetes",
    ) -> bool:
        """Check resource health after rollback.

        Returns True if healthy, False on error or unhealthy.
        """
        if self._router is None:
            return False

        try:
            connector = self._router.get(provider)
            health = await connector.get_health(resource_id)
            return health.healthy
        except Exception as e:
            logger.error(
                "rollback_validation_failed",
                resource_id=resource_id,
                error=str(e),
            )
            return False

    async def _write_rollback_audit(
        self,
        snapshot: Snapshot,
        result: ActionResult,
        reason: str,
    ) -> None:
        """Write an audit entry for a rollback operation (best-effort)."""
        if self._repository is None:
            return
        try:
            entry = AuditEntry(
                id=f"aud-rollback-{snapshot.id}",
                timestamp=datetime.now(UTC),
                agent_type="rollback",
                action="rollback",
                target_resource=snapshot.resource_id,
                environment="production",
                risk_level=RiskLevel.HIGH,
                policy_evaluation="allowed",
                outcome=result.status,
                reasoning=reason or "rollback requested",
                actor="system",
            )
            await self._repository.append_audit_log(entry)
        except Exception as e:
            logger.warning(
                "rollback_audit_write_failed",
                snapshot_id=snapshot.id,
                error=str(e),
            )
