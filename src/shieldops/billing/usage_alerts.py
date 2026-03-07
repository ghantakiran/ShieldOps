"""Usage alert management — monitors org limits and dispatches alerts.

Provides threshold checking (80 % warning, 100 % exceeded, 150 %
anomalous), alert persistence, and notification dispatch.
"""

from __future__ import annotations

from typing import Any

import structlog

from shieldops.billing.usage_models import UsageAlert
from shieldops.billing.usage_tracker import UsageTracker

logger = structlog.get_logger()


class UsageAlertManager:
    """Manages usage-based billing alerts for all organisations.

    Alerts are stored in memory.  ``send_alert`` dispatches via
    configured channels (webhook, email placeholder).
    """

    def __init__(
        self,
        tracker: UsageTracker,
        webhook_url: str | None = None,
    ) -> None:
        """Initialise the alert manager.

        Args:
            tracker: ``UsageTracker`` to query for limit checks.
            webhook_url: Optional webhook URL for alert delivery.
        """
        self._tracker = tracker
        self._webhook_url = webhook_url

        # alert_id (str) -> UsageAlert
        self._alerts: dict[str, UsageAlert] = {}
        # org_id -> set of active alert ids
        self._org_alerts: dict[str, set[str]] = {}

    # ------------------------------------------------------------------
    # Bulk check
    # ------------------------------------------------------------------

    async def check_all_orgs(self) -> list[UsageAlert]:
        """Iterate all registered orgs and check usage limits.

        Returns:
            List of newly created alerts.
        """
        new_alerts: list[UsageAlert] = []

        # Get all org_ids the tracker knows about
        async with self._tracker._lock:
            org_ids = list(self._tracker._org_limits.keys())

        for org_id in org_ids:
            alert = await self._tracker.check_usage_limits(org_id)
            if alert is not None and not self._has_active_alert(org_id, alert.alert_type):
                self._store_alert(alert)
                await self.send_alert(alert)
                new_alerts.append(alert)

        logger.info(
            "usage_alert_check_complete",
            orgs_checked=len(org_ids),
            alerts_created=len(new_alerts),
        )
        return new_alerts

    # ------------------------------------------------------------------
    # Alert dispatch
    # ------------------------------------------------------------------

    async def send_alert(self, alert: UsageAlert) -> None:
        """Send an alert via configured notification channels.

        Currently supports:
          - Webhook POST (if ``webhook_url`` is configured)
          - Email (placeholder — logs the alert)

        Args:
            alert: The ``UsageAlert`` to dispatch.
        """
        payload = {
            "alert_id": str(alert.alert_id),
            "org_id": alert.org_id,
            "alert_type": alert.alert_type.value,
            "threshold_pct": alert.threshold_pct,
            "current_usage": alert.current_usage,
            "limit": alert.limit,
            "message": alert.message,
            "created_at": alert.created_at.isoformat(),
        }

        # Webhook delivery
        if self._webhook_url:
            await self._post_webhook(payload)

        # Email placeholder
        logger.info(
            "usage_alert_sent",
            org_id=alert.org_id,
            alert_type=alert.alert_type.value,
            message=alert.message,
        )

    # ------------------------------------------------------------------
    # Query / lifecycle
    # ------------------------------------------------------------------

    def get_alerts(
        self,
        org_id: str,
        resolved: bool = False,
    ) -> list[UsageAlert]:
        """Return alerts for an organisation.

        Args:
            org_id: Organisation identifier.
            resolved: If ``True``, return only resolved alerts.
                      If ``False`` (default), return only active alerts.

        Returns:
            List of matching ``UsageAlert`` instances.
        """
        alert_ids = self._org_alerts.get(org_id, set())
        results: list[UsageAlert] = []
        for aid in alert_ids:
            alert = self._alerts.get(aid)
            if alert is not None and alert.resolved == resolved:
                results.append(alert)
        results.sort(key=lambda a: a.created_at, reverse=True)
        return results

    def dismiss_alert(self, alert_id: str) -> bool:
        """Mark an alert as resolved.

        Args:
            alert_id: The UUID string of the alert to dismiss.

        Returns:
            ``True`` if the alert was found and dismissed,
            ``False`` otherwise.
        """
        alert = self._alerts.get(alert_id)
        if alert is None:
            return False
        alert.resolved = True
        logger.info(
            "usage_alert_dismissed",
            alert_id=alert_id,
            org_id=alert.org_id,
        )
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _store_alert(self, alert: UsageAlert) -> None:
        """Persist an alert in the in-memory store."""
        key = str(alert.alert_id)
        self._alerts[key] = alert
        self._org_alerts.setdefault(alert.org_id, set()).add(key)

    def _has_active_alert(self, org_id: str, alert_type: str) -> bool:
        """Check if an active (unresolved) alert of the same type exists."""
        for aid in self._org_alerts.get(org_id, set()):
            alert = self._alerts.get(aid)
            if alert is not None and not alert.resolved and alert.alert_type == alert_type:
                return True
        return False

    async def _post_webhook(self, payload: dict[str, Any]) -> None:
        """POST alert payload to the configured webhook URL."""
        try:
            import httpx  # type: ignore[import-not-found]

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self._webhook_url, json=payload)  # type: ignore[arg-type]
                resp.raise_for_status()
            logger.debug(
                "usage_alert_webhook_sent",
                url=self._webhook_url,
                status=resp.status_code,
            )
        except Exception:
            logger.exception(
                "usage_alert_webhook_failed",
                url=self._webhook_url,
            )
