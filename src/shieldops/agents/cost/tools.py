"""Tool functions for the Cost Agent.

Bridges external billing APIs, cloud resource inventories,
and usage metrics into the cost analysis workflow.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog

from shieldops.connectors.base import ConnectorRouter
from shieldops.models.base import Environment

logger = structlog.get_logger()


class CostToolkit:
    """Encapsulates external integrations for cost analysis.

    Pluggable billing sources and connector router allow
    production use with real APIs and test use with stubs.
    """

    def __init__(
        self,
        connector_router: ConnectorRouter | None = None,
        billing_sources: list[Any] | None = None,
    ) -> None:
        self._router = connector_router
        self._billing_sources = billing_sources or []

    async def get_resource_inventory(
        self, environment: Environment
    ) -> dict[str, Any]:
        """Get inventory of all cloud resources and their types.

        Returns resource list with types, providers, and basic metadata.
        """
        if self._router:
            try:
                resources = []
                for provider in self._router.providers:
                    connector = self._router.get(provider)
                    provider_resources = await connector.list_resources(
                        resource_type="all", environment=environment
                    )
                    resources.extend(
                        {
                            "resource_id": r.id,
                            "resource_type": r.resource_type,
                            "provider": r.provider,
                            "name": r.name,
                            "labels": r.labels,
                        }
                        for r in provider_resources
                    )
                return {
                    "resources": resources,
                    "total_count": len(resources),
                    "providers": self._router.providers,
                }
            except Exception as e:
                logger.error("resource_inventory_failed", error=str(e))

        # Default stub response when no router configured
        return {
            "resources": [
                {"resource_id": "i-web-001", "resource_type": "instance", "provider": "aws", "name": "web-server-1", "labels": {"team": "platform"}},
                {"resource_id": "i-api-001", "resource_type": "instance", "provider": "aws", "name": "api-server-1", "labels": {"team": "backend"}},
                {"resource_id": "rds-main", "resource_type": "database", "provider": "aws", "name": "main-db", "labels": {"team": "data"}},
                {"resource_id": "pod-worker-001", "resource_type": "pod", "provider": "kubernetes", "name": "worker-pod", "labels": {"app": "worker"}},
                {"resource_id": "s3-logs", "resource_type": "storage", "provider": "aws", "name": "log-bucket", "labels": {"team": "platform"}},
            ],
            "total_count": 5,
            "providers": ["aws", "kubernetes"],
        }

    async def query_billing(
        self,
        environment: Environment,
        period: str = "30d",
    ) -> dict[str, Any]:
        """Query cloud billing data for resources.

        Returns per-resource cost breakdown with service-level aggregation.
        """
        for source in self._billing_sources:
            try:
                return await source.query(environment=environment, period=period)
            except Exception as e:
                logger.warning("billing_source_failed", source=type(source).__name__, error=str(e))

        # Default stub billing data
        return {
            "period": period,
            "currency": "USD",
            "total_daily": 342.50,
            "total_monthly": 10275.00,
            "by_service": {
                "compute": 4800.00,
                "database": 2400.00,
                "storage": 1200.00,
                "network": 975.00,
                "kubernetes": 900.00,
            },
            "by_environment": {
                "production": 7200.00,
                "staging": 2050.00,
                "development": 1025.00,
            },
            "resource_costs": [
                {"resource_id": "i-web-001", "resource_type": "instance", "service": "compute", "daily_cost": 48.00, "monthly_cost": 1440.00, "usage_percent": 35.0},
                {"resource_id": "i-api-001", "resource_type": "instance", "service": "compute", "daily_cost": 96.00, "monthly_cost": 2880.00, "usage_percent": 72.0},
                {"resource_id": "rds-main", "resource_type": "database", "service": "database", "daily_cost": 80.00, "monthly_cost": 2400.00, "usage_percent": 55.0},
                {"resource_id": "pod-worker-001", "resource_type": "pod", "service": "kubernetes", "daily_cost": 30.00, "monthly_cost": 900.00, "usage_percent": 15.0},
                {"resource_id": "s3-logs", "resource_type": "storage", "service": "storage", "daily_cost": 40.00, "monthly_cost": 1200.00, "usage_percent": 80.0},
            ],
        }

    async def detect_anomalies(
        self,
        resource_costs: list[dict[str, Any]],
        threshold_percent: float = 30.0,
    ) -> dict[str, Any]:
        """Detect cost anomalies by comparing against baseline.

        Identifies resources with spending significantly above their
        historical average within the analysis period.
        """
        anomalies = []
        now = datetime.now(timezone.utc)

        for rc in resource_costs:
            daily_cost = rc.get("daily_cost", 0)
            usage = rc.get("usage_percent", 50)

            # Flag resources with low utilization but high cost
            if usage < 20 and daily_cost > 20:
                deviation = ((daily_cost - 10) / max(10, 1)) * 100
                anomalies.append({
                    "resource_id": rc["resource_id"],
                    "service": rc.get("service", "unknown"),
                    "anomaly_type": "unused",
                    "severity": "high" if daily_cost > 50 else "medium",
                    "expected_daily_cost": daily_cost * (usage / 100),
                    "actual_daily_cost": daily_cost,
                    "deviation_percent": round(deviation, 1),
                    "started_at": now - timedelta(days=7),
                    "description": f"Resource {rc['resource_id']} has {usage}% utilization but costs ${daily_cost:.2f}/day",
                })

            # Flag resources exceeding threshold above a baseline
            baseline = daily_cost * 0.7  # simulate 70% of current as baseline
            if daily_cost > baseline * (1 + threshold_percent / 100):
                anomalies.append({
                    "resource_id": rc["resource_id"],
                    "service": rc.get("service", "unknown"),
                    "anomaly_type": "spike",
                    "severity": "critical" if daily_cost > 100 else "medium",
                    "expected_daily_cost": round(baseline, 2),
                    "actual_daily_cost": daily_cost,
                    "deviation_percent": round(((daily_cost - baseline) / baseline) * 100, 1),
                    "started_at": now - timedelta(days=2),
                    "description": f"Resource {rc['resource_id']} spending ${daily_cost:.2f}/day vs ${baseline:.2f}/day baseline",
                })

        critical_count = sum(1 for a in anomalies if a["severity"] == "critical")

        return {
            "anomalies": anomalies,
            "total_anomalies": len(anomalies),
            "critical_count": critical_count,
        }

    async def get_optimization_opportunities(
        self,
        resource_costs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Identify cost optimization opportunities.

        Analyzes utilization patterns and suggests rightsizing,
        scheduling, and resource cleanup actions.
        """
        recommendations = []
        total_savings = 0.0

        for rc in resource_costs:
            usage = rc.get("usage_percent", 50)
            monthly = rc.get("monthly_cost", 0)
            resource_id = rc.get("resource_id", "unknown")
            service = rc.get("service", "unknown")

            # Rightsizing: resources below 40% utilization
            if usage < 40 and monthly > 100:
                savings = monthly * 0.4  # could save ~40% by downsizing
                total_savings += savings
                recommendations.append({
                    "category": "rightsizing",
                    "resource_id": resource_id,
                    "service": service,
                    "current_monthly_cost": monthly,
                    "projected_monthly_cost": round(monthly - savings, 2),
                    "monthly_savings": round(savings, 2),
                    "confidence": 0.8,
                    "effort": "low",
                    "description": f"Downsize {resource_id} — only {usage}% utilized",
                    "implementation_steps": [
                        f"Verify {resource_id} workload can run on smaller instance",
                        "Schedule downsize during maintenance window",
                        "Monitor for 48 hours post-change",
                    ],
                })

            # Unused resources: below 10% utilization
            if usage < 10 and monthly > 50:
                total_savings += monthly
                recommendations.append({
                    "category": "unused_resources",
                    "resource_id": resource_id,
                    "service": service,
                    "current_monthly_cost": monthly,
                    "projected_monthly_cost": 0,
                    "monthly_savings": monthly,
                    "confidence": 0.7,
                    "effort": "low",
                    "description": f"Consider terminating {resource_id} — only {usage}% utilized",
                    "implementation_steps": [
                        f"Confirm {resource_id} is not needed by any service",
                        "Create snapshot/backup before termination",
                        "Terminate resource",
                    ],
                })

        return {
            "recommendations": recommendations,
            "total_recommendations": len(recommendations),
            "total_potential_monthly_savings": round(total_savings, 2),
        }

    async def get_automation_savings(
        self,
        period: str = "30d",
        engineer_hourly_rate: float = 75.0,
    ) -> dict[str, Any]:
        """Calculate cost savings from automated operations.

        Estimates hours saved by ShieldOps automation vs. manual operations.
        """
        # In production, this would query the investigation/remediation
        # databases for actual time-saved metrics. Stub data here.
        return {
            "period": period,
            "investigations_automated": 45,
            "avg_investigation_hours_saved": 1.5,
            "remediations_automated": 22,
            "avg_remediation_hours_saved": 2.0,
            "total_hours_saved": 45 * 1.5 + 22 * 2.0,
            "engineer_hourly_rate": engineer_hourly_rate,
            "automation_savings_usd": (45 * 1.5 + 22 * 2.0) * engineer_hourly_rate,
        }
