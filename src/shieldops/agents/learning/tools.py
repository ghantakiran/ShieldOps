"""Tool functions for the Learning Agent.

Bridges incident databases, playbook stores, and alerting systems
into the learning workflow.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from shieldops.db.repository import Repository
    from shieldops.playbooks.loader import PlaybookLoader

logger = structlog.get_logger()


class LearningToolkit:
    """Encapsulates external integrations for learning analysis.

    Pluggable incident stores and playbook repositories allow
    production use with real backends and test use with stubs.
    """

    def __init__(
        self,
        incident_store: Any | None = None,
        playbook_store: Any | None = None,
        alert_config_store: Any | None = None,
    ) -> None:
        self._incident_store = incident_store
        self._playbook_store = playbook_store
        self._alert_config_store = alert_config_store

    async def get_incident_outcomes(
        self,
        period: str = "30d",
    ) -> dict[str, Any]:
        """Retrieve resolved incident outcomes for analysis.

        Returns incident records with root cause, resolution, and feedback.
        """
        if self._incident_store:
            try:
                return await self._incident_store.query(period=period)
            except Exception as e:
                logger.warning("incident_store_query_failed", error=str(e))

        # Stub data for when no store is configured
        return {
            "period": period,
            "total_incidents": 28,
            "outcomes": [
                {
                    "incident_id": "inc-001",
                    "alert_type": "high_cpu",
                    "environment": "production",
                    "root_cause": "Memory leak in API service",
                    "resolution_action": "restart_pod",
                    "investigation_duration_ms": 45000,
                    "remediation_duration_ms": 12000,
                    "was_automated": True,
                    "was_correct": True,
                    "feedback": "",
                },
                {
                    "incident_id": "inc-002",
                    "alert_type": "high_cpu",
                    "environment": "production",
                    "root_cause": "Memory leak in API service",
                    "resolution_action": "restart_pod",
                    "investigation_duration_ms": 38000,
                    "remediation_duration_ms": 11000,
                    "was_automated": True,
                    "was_correct": True,
                    "feedback": "Same issue recurring - need permanent fix",
                },
                {
                    "incident_id": "inc-003",
                    "alert_type": "latency_spike",
                    "environment": "production",
                    "root_cause": "Database connection pool exhaustion",
                    "resolution_action": "scale_horizontal",
                    "investigation_duration_ms": 120000,
                    "remediation_duration_ms": 30000,
                    "was_automated": False,
                    "was_correct": True,
                    "feedback": "Should auto-scale connections",
                },
                {
                    "incident_id": "inc-004",
                    "alert_type": "oom_kill",
                    "environment": "staging",
                    "root_cause": "Memory limit too low for batch job",
                    "resolution_action": "increase_resources",
                    "investigation_duration_ms": 25000,
                    "remediation_duration_ms": 8000,
                    "was_automated": True,
                    "was_correct": True,
                    "feedback": "",
                },
                {
                    "incident_id": "inc-005",
                    "alert_type": "disk_full",
                    "environment": "production",
                    "root_cause": "Log rotation not configured",
                    "resolution_action": "cleanup_disk",
                    "investigation_duration_ms": 15000,
                    "remediation_duration_ms": 5000,
                    "was_automated": True,
                    "was_correct": True,
                    "feedback": "",
                },
                {
                    "incident_id": "inc-006",
                    "alert_type": "high_cpu",
                    "environment": "production",
                    "root_cause": "Runaway cron job",
                    "resolution_action": "restart_pod",
                    "investigation_duration_ms": 60000,
                    "remediation_duration_ms": 15000,
                    "was_automated": True,
                    "was_correct": False,
                    "feedback": "Restart didn't fix it - needed to kill the cron",
                },
                {
                    "incident_id": "inc-007",
                    "alert_type": "latency_spike",
                    "environment": "production",
                    "root_cause": "Upstream dependency slow",
                    "resolution_action": "none",
                    "investigation_duration_ms": 90000,
                    "remediation_duration_ms": 0,
                    "was_automated": False,
                    "was_correct": True,
                    "feedback": "External dependency - nothing to remediate internally",
                },
                {
                    "incident_id": "inc-008",
                    "alert_type": "high_error_rate",
                    "environment": "production",
                    "root_cause": "Bad deployment",
                    "resolution_action": "rollback_deployment",
                    "investigation_duration_ms": 30000,
                    "remediation_duration_ms": 20000,
                    "was_automated": True,
                    "was_correct": True,
                    "feedback": "",
                },
            ],
        }

    async def get_current_playbooks(self) -> dict[str, Any]:
        """Get current operational playbooks."""
        if self._playbook_store:
            try:
                return await self._playbook_store.list()
            except Exception as e:
                logger.warning("playbook_store_query_failed", error=str(e))

        return {
            "playbooks": [
                {
                    "playbook_id": "pb-001",
                    "alert_type": "high_cpu",
                    "title": "High CPU Remediation",
                    "steps": [
                        "Check top processes",
                        "Identify resource consumer",
                        "Restart pod if safe",
                    ],
                    "last_updated": (now := datetime.now(UTC)) - timedelta(days=60),
                },
                {
                    "playbook_id": "pb-002",
                    "alert_type": "oom_kill",
                    "title": "OOM Kill Response",
                    "steps": [
                        "Check memory limits",
                        "Review recent deployments",
                        "Increase limits or restart",
                    ],
                    "last_updated": now - timedelta(days=45),
                },
                {
                    "playbook_id": "pb-003",
                    "alert_type": "disk_full",
                    "title": "Disk Full Recovery",
                    "steps": [
                        "Identify large files",
                        "Clean temp/log files",
                        "Expand volume if needed",
                    ],
                    "last_updated": now - timedelta(days=90),
                },
            ],
            "total": 3,
        }

    async def get_alert_thresholds(self) -> dict[str, Any]:
        """Get current alerting thresholds."""
        if self._alert_config_store:
            try:
                return await self._alert_config_store.get_thresholds()
            except Exception as e:
                logger.warning("alert_config_query_failed", error=str(e))

        return {
            "thresholds": [
                {
                    "metric_name": "cpu_usage_percent",
                    "threshold": 80.0,
                    "duration": "5m",
                    "severity": "warning",
                },
                {
                    "metric_name": "cpu_usage_percent",
                    "threshold": 95.0,
                    "duration": "2m",
                    "severity": "critical",
                },
                {
                    "metric_name": "memory_usage_percent",
                    "threshold": 85.0,
                    "duration": "5m",
                    "severity": "warning",
                },
                {
                    "metric_name": "disk_usage_percent",
                    "threshold": 90.0,
                    "duration": "10m",
                    "severity": "warning",
                },
                {
                    "metric_name": "error_rate_percent",
                    "threshold": 5.0,
                    "duration": "5m",
                    "severity": "critical",
                },
                {
                    "metric_name": "p99_latency_ms",
                    "threshold": 500.0,
                    "duration": "5m",
                    "severity": "warning",
                },
                {
                    "metric_name": "p99_latency_ms",
                    "threshold": 2000.0,
                    "duration": "2m",
                    "severity": "critical",
                },
            ],
            "total": 7,
        }

    async def compute_effectiveness_metrics(
        self,
        outcomes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Compute effectiveness metrics from incident outcomes."""
        if not outcomes:
            return {
                "total_incidents": 0,
                "automated_count": 0,
                "automation_rate": 0.0,
                "accuracy": 0.0,
                "avg_investigation_ms": 0,
                "avg_remediation_ms": 0,
                "by_alert_type": {},
            }

        total = len(outcomes)
        automated = [o for o in outcomes if o.get("was_automated")]
        correct_automated = [o for o in automated if o.get("was_correct")]

        by_alert_type: dict[str, dict] = {}
        for o in outcomes:
            at = o.get("alert_type", "unknown")
            if at not in by_alert_type:
                by_alert_type[at] = {
                    "count": 0,
                    "automated": 0,
                    "correct": 0,
                    "total_investigation_ms": 0,
                    "total_remediation_ms": 0,
                }
            by_alert_type[at]["count"] += 1
            if o.get("was_automated"):
                by_alert_type[at]["automated"] += 1
            if o.get("was_correct"):
                by_alert_type[at]["correct"] += 1
            by_alert_type[at]["total_investigation_ms"] += o.get("investigation_duration_ms", 0)
            by_alert_type[at]["total_remediation_ms"] += o.get("remediation_duration_ms", 0)

        # Compute averages per alert type
        for _at, data in by_alert_type.items():
            data["avg_investigation_ms"] = data["total_investigation_ms"] // max(data["count"], 1)
            data["avg_remediation_ms"] = data["total_remediation_ms"] // max(data["count"], 1)

        avg_inv = sum(o.get("investigation_duration_ms", 0) for o in outcomes) // total
        avg_rem = sum(o.get("remediation_duration_ms", 0) for o in outcomes) // total

        return {
            "total_incidents": total,
            "automated_count": len(automated),
            "automation_rate": len(automated) / total * 100,
            "accuracy": len(correct_automated) / max(len(automated), 1) * 100,
            "avg_investigation_ms": avg_inv,
            "avg_remediation_ms": avg_rem,
            "by_alert_type": by_alert_type,
        }


class IncidentStoreAdapter:
    """Adapts Repository into the incident_store interface LearningToolkit expects."""

    def __init__(self, repository: Repository) -> None:
        self._repo = repository

    async def query(self, period: str = "30d") -> dict[str, Any]:
        return await self._repo.query_incident_outcomes(period=period)


class PlaybookStoreAdapter:
    """Adapts PlaybookLoader into the async playbook_store interface LearningToolkit expects."""

    def __init__(self, loader: PlaybookLoader) -> None:
        self._loader = loader

    async def list(self) -> dict[str, Any]:
        playbooks = self._loader.all()
        return {
            "playbooks": [
                {
                    "playbook_id": f"pb-{i:03d}",
                    "alert_type": pb.trigger.alert_type,
                    "title": pb.name,
                    "description": pb.description,
                    "version": pb.version,
                }
                for i, pb in enumerate(playbooks, start=1)
            ],
            "total": len(playbooks),
        }
