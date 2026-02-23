"""Configuration drift detector.

Compares configuration across environments to detect drift from baselines,
tracks acknowledged/resolved drift items.
"""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────


class DriftSeverity(enum.StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DriftStatus(enum.StrEnum):
    DETECTED = "detected"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    IGNORED = "ignored"


# ── Models ───────────────────────────────────────────────────────────


class ConfigSnapshot(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    environment: str
    service: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    taken_at: float = Field(default_factory=time.time)
    taken_by: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class DriftItem(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    key: str
    expected_value: Any = None
    actual_value: Any = None
    severity: DriftSeverity = DriftSeverity.WARNING
    status: DriftStatus = DriftStatus.DETECTED
    environment: str = ""
    service: str = ""


class DriftReport(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    source_environment: str
    target_environment: str
    service: str = ""
    drifts: list[DriftItem] = Field(default_factory=list)
    total_keys_compared: int = 0
    drift_count: int = 0
    created_at: float = Field(default_factory=time.time)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Detector ─────────────────────────────────────────────────────────


class ConfigDriftDetector:
    """Detect configuration drift across environments.

    Parameters
    ----------
    max_snapshots_per_env:
        Maximum snapshots per environment.
    retention_days:
        Days to retain old snapshots.
    """

    def __init__(
        self,
        max_snapshots_per_env: int = 100,
        retention_days: int = 30,
    ) -> None:
        self._snapshots: dict[str, list[ConfigSnapshot]] = {}
        self._baselines: dict[str, ConfigSnapshot] = {}
        self._reports: dict[str, DriftReport] = {}
        self._drift_items: dict[str, DriftItem] = {}
        self._max_per_env = max_snapshots_per_env
        self._retention_seconds = retention_days * 86400

    def take_snapshot(
        self,
        environment: str,
        config: dict[str, Any],
        service: str = "",
        taken_by: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ConfigSnapshot:
        snapshot = ConfigSnapshot(
            environment=environment,
            service=service,
            config=config,
            taken_by=taken_by,
            metadata=metadata or {},
        )
        key = f"{environment}:{service}"
        if key not in self._snapshots:
            self._snapshots[key] = []
        self._snapshots[key].append(snapshot)
        if len(self._snapshots[key]) > self._max_per_env:
            self._snapshots[key] = self._snapshots[key][-self._max_per_env :]
        logger.info("config_snapshot_taken", environment=environment, service=service)
        return snapshot

    def set_baseline(
        self,
        environment: str,
        config: dict[str, Any],
        service: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ConfigSnapshot:
        snapshot = ConfigSnapshot(
            environment=environment,
            service=service,
            config=config,
            metadata=metadata or {},
        )
        key = f"{environment}:{service}"
        self._baselines[key] = snapshot
        logger.info("baseline_set", environment=environment, service=service)
        return snapshot

    def detect_drift(
        self,
        source_env: str,
        target_env: str,
        service: str = "",
    ) -> DriftReport:
        src_key = f"{source_env}:{service}"
        tgt_key = f"{target_env}:{service}"
        src_snaps = self._snapshots.get(src_key, [])
        tgt_snaps = self._snapshots.get(tgt_key, [])
        src_config = src_snaps[-1].config if src_snaps else {}
        tgt_config = tgt_snaps[-1].config if tgt_snaps else {}
        return self._compare_configs(source_env, target_env, service, src_config, tgt_config)

    def detect_drift_from_baseline(
        self,
        environment: str,
        service: str = "",
    ) -> DriftReport | None:
        key = f"{environment}:{service}"
        baseline = self._baselines.get(key)
        if baseline is None:
            return None
        snaps = self._snapshots.get(key, [])
        current = snaps[-1].config if snaps else {}
        return self._compare_configs("baseline", environment, service, baseline.config, current)

    def _compare_configs(
        self,
        source_env: str,
        target_env: str,
        service: str,
        source: dict[str, Any],
        target: dict[str, Any],
    ) -> DriftReport:
        all_keys = set(source.keys()) | set(target.keys())
        drifts: list[DriftItem] = []
        for key in sorted(all_keys):
            src_val = source.get(key)
            tgt_val = target.get(key)
            if src_val != tgt_val:
                severity = DriftSeverity.WARNING
                if key.startswith("security") or key.startswith("auth"):
                    severity = DriftSeverity.CRITICAL
                elif key.startswith("log") or key.startswith("debug"):
                    severity = DriftSeverity.INFO
                item = DriftItem(
                    key=key,
                    expected_value=src_val,
                    actual_value=tgt_val,
                    severity=severity,
                    environment=target_env,
                    service=service,
                )
                drifts.append(item)
                self._drift_items[item.id] = item

        report = DriftReport(
            source_environment=source_env,
            target_environment=target_env,
            service=service,
            drifts=drifts,
            total_keys_compared=len(all_keys),
            drift_count=len(drifts),
        )
        self._reports[report.id] = report
        logger.info(
            "drift_detected",
            source=source_env,
            target=target_env,
            drifts=len(drifts),
        )
        return report

    def acknowledge_drift(self, drift_id: str) -> DriftItem | None:
        item = self._drift_items.get(drift_id)
        if item is None:
            return None
        item.status = DriftStatus.ACKNOWLEDGED
        return item

    def resolve_drift(self, drift_id: str) -> DriftItem | None:
        item = self._drift_items.get(drift_id)
        if item is None:
            return None
        item.status = DriftStatus.RESOLVED
        return item

    def list_reports(self, limit: int = 50) -> list[DriftReport]:
        reports = sorted(self._reports.values(), key=lambda r: r.created_at, reverse=True)
        return reports[:limit]

    def get_report(self, report_id: str) -> DriftReport | None:
        return self._reports.get(report_id)

    def get_stats(self) -> dict[str, Any]:
        total_drifts = sum(r.drift_count for r in self._reports.values())
        by_severity: dict[str, int] = {}
        for item in self._drift_items.values():
            by_severity[item.severity.value] = by_severity.get(item.severity.value, 0) + 1
        return {
            "total_reports": len(self._reports),
            "total_snapshots": sum(len(v) for v in self._snapshots.values()),
            "total_baselines": len(self._baselines),
            "total_drifts": total_drifts,
            "by_severity": by_severity,
        }
