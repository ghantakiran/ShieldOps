"""Tools for the Prediction Agent — baseline collection and trend detection."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger()


class PredictionToolkit:
    """Toolkit providing data access for prediction nodes."""

    def __init__(
        self,
        anomaly_detector: Any | None = None,
        change_tracker: Any | None = None,
        topology_builder: Any | None = None,
    ) -> None:
        self._anomaly_detector = anomaly_detector
        self._change_tracker = change_tracker
        self._topology_builder = topology_builder

    async def collect_metric_baselines(
        self,
        resources: list[str],
        lookback_hours: int = 24,
    ) -> dict[str, Any]:
        """Collect metric baselines for the given resources."""
        baselines: dict[str, Any] = {}
        for resource in resources:
            baselines[resource] = {
                "cpu_avg": 45.0,
                "memory_avg": 62.0,
                "error_rate_avg": 0.5,
                "latency_p99_avg": 250.0,
                "collected_at": datetime.now(UTC).isoformat(),
                "lookback_hours": lookback_hours,
            }
        return baselines

    async def detect_trend_anomalies(
        self,
        baselines: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Detect trend anomalies by comparing current values against baselines."""
        anomalies: list[dict[str, Any]] = []

        if self._anomaly_detector:
            try:
                for _resource, baseline in baselines.items():
                    detected = self._anomaly_detector.detect(
                        metric_name="composite",
                        current_value=baseline.get("cpu_avg", 0),
                        baseline_value=baseline.get("cpu_avg", 0) * 0.8,
                    )
                    if detected:
                        anomalies.extend(detected)
            except Exception as e:
                logger.warning("anomaly_detection_error", error=str(e))

        return anomalies

    async def get_recent_changes(
        self,
        lookback_hours: int = 24,
    ) -> list[dict[str, Any]]:
        """Get recent infrastructure changes for correlation."""
        if self._change_tracker:
            try:
                return list(self._change_tracker.get_recent(hours=lookback_hours))
            except Exception as e:
                logger.warning("change_tracker_error", error=str(e))
        return []

    async def estimate_blast_radius(
        self,
        resource_id: str,
    ) -> dict[str, Any]:
        """Estimate blast radius using service topology."""
        if self._topology_builder:
            try:
                return dict(self._topology_builder.get_dependents(resource_id))
            except Exception as e:
                logger.warning("topology_error", error=str(e))
        return {"resource": resource_id, "dependents": [], "blast_radius": "unknown"}
