"""Config Drift Analyzer — detect configuration drift across environments."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DriftType(StrEnum):
    VALUE_CHANGE = "value_change"
    MISSING_KEY = "missing_key"
    EXTRA_KEY = "extra_key"
    TYPE_MISMATCH = "type_mismatch"
    FORMAT_CHANGE = "format_change"


class DriftSeverity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    INFORMATIONAL = "informational"


class DriftSource(StrEnum):
    MANUAL_EDIT = "manual_edit"
    DEPLOYMENT = "deployment"
    HOTFIX = "hotfix"
    MIGRATION = "migration"
    UNKNOWN = "unknown"


# --- Models ---


class DriftRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    config_name: str = ""
    drift_type: DriftType = DriftType.VALUE_CHANGE
    severity: DriftSeverity = DriftSeverity.MODERATE
    source: DriftSource = DriftSource.UNKNOWN
    deviation_pct: float = 0.0
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class DriftRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = ""
    drift_type: DriftType = DriftType.VALUE_CHANGE
    severity: DriftSeverity = DriftSeverity.MODERATE
    max_deviation_pct: float = 5.0
    auto_remediate: bool = False
    created_at: float = Field(default_factory=time.time)


class DriftAnalyzerReport(BaseModel):
    total_drifts: int = 0
    total_rules: int = 0
    clean_rate_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    critical_drift_count: int = 0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ConfigDriftAnalyzer:
    """Detect configuration drift across environments."""

    def __init__(
        self,
        max_records: int = 200000,
        max_deviation_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_deviation_pct = max_deviation_pct
        self._records: list[DriftRecord] = []
        self._policies: list[DriftRule] = []
        logger.info(
            "drift_analyzer.initialized",
            max_records=max_records,
            max_deviation_pct=max_deviation_pct,
        )

    # -- record / get / list -----------------------------------------

    def record_drift(
        self,
        config_name: str,
        drift_type: DriftType = DriftType.VALUE_CHANGE,
        severity: DriftSeverity = DriftSeverity.MODERATE,
        source: DriftSource = DriftSource.UNKNOWN,
        deviation_pct: float = 0.0,
        details: str = "",
    ) -> DriftRecord:
        record = DriftRecord(
            config_name=config_name,
            drift_type=drift_type,
            severity=severity,
            source=source,
            deviation_pct=deviation_pct,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "drift_analyzer.drift_recorded",
            record_id=record.id,
            config_name=config_name,
            drift_type=drift_type.value,
            severity=severity.value,
        )
        return record

    def get_drift(self, record_id: str) -> DriftRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_drifts(
        self,
        config_name: str | None = None,
        drift_type: DriftType | None = None,
        limit: int = 50,
    ) -> list[DriftRecord]:
        results = list(self._records)
        if config_name is not None:
            results = [r for r in results if r.config_name == config_name]
        if drift_type is not None:
            results = [r for r in results if r.drift_type == drift_type]
        return results[-limit:]

    def add_rule(
        self,
        rule_name: str,
        drift_type: DriftType = DriftType.VALUE_CHANGE,
        severity: DriftSeverity = DriftSeverity.MODERATE,
        max_deviation_pct: float = 5.0,
        auto_remediate: bool = False,
    ) -> DriftRule:
        rule = DriftRule(
            rule_name=rule_name,
            drift_type=drift_type,
            severity=severity,
            max_deviation_pct=max_deviation_pct,
            auto_remediate=auto_remediate,
        )
        self._policies.append(rule)
        if len(self._policies) > self._max_records:
            self._policies = self._policies[-self._max_records :]
        logger.info(
            "drift_analyzer.rule_added",
            rule_name=rule_name,
            drift_type=drift_type.value,
            severity=severity.value,
        )
        return rule

    # -- domain operations -------------------------------------------

    def analyze_drift_status(self, config_name: str) -> dict[str, Any]:
        """Analyze drift status for a config."""
        records = [r for r in self._records if r.config_name == config_name]
        if not records:
            return {
                "config_name": config_name,
                "status": "no_data",
            }
        clean_count = sum(
            1
            for r in records
            if r.severity
            in (
                DriftSeverity.LOW,
                DriftSeverity.INFORMATIONAL,
            )
        )
        clean_rate = round(clean_count / len(records) * 100, 2)
        avg_deviation = round(
            sum(r.deviation_pct for r in records) / len(records),
            2,
        )
        return {
            "config_name": config_name,
            "drift_count": len(records),
            "clean_count": clean_count,
            "clean_rate": clean_rate,
            "avg_deviation": avg_deviation,
            "meets_threshold": (avg_deviation <= self._max_deviation_pct),
        }

    def identify_critical_drifts(
        self,
    ) -> list[dict[str, Any]]:
        """Find configs with repeated critical drifts."""
        crit_counts: dict[str, int] = {}
        for r in self._records:
            if r.severity in (
                DriftSeverity.CRITICAL,
                DriftSeverity.HIGH,
            ):
                crit_counts[r.config_name] = crit_counts.get(r.config_name, 0) + 1
        results: list[dict[str, Any]] = []
        for cfg, count in crit_counts.items():
            if count > 1:
                results.append(
                    {
                        "config_name": cfg,
                        "critical_count": count,
                    }
                )
        results.sort(
            key=lambda x: x["critical_count"],
            reverse=True,
        )
        return results

    def rank_by_deviation(
        self,
    ) -> list[dict[str, Any]]:
        """Rank configs by avg deviation desc."""
        totals: dict[str, float] = {}
        counts: dict[str, int] = {}
        for r in self._records:
            totals[r.config_name] = totals.get(r.config_name, 0.0) + r.deviation_pct
            counts[r.config_name] = counts.get(r.config_name, 0) + 1
        results: list[dict[str, Any]] = []
        for cfg, total in totals.items():
            avg = round(total / counts[cfg], 2)
            results.append(
                {
                    "config_name": cfg,
                    "avg_deviation_pct": avg,
                }
            )
        results.sort(
            key=lambda x: x["avg_deviation_pct"],
            reverse=True,
        )
        return results

    def detect_drift_patterns(
        self,
    ) -> list[dict[str, Any]]:
        """Detect configs with >3 non-LOW/non-INFO."""
        non_clean: dict[str, int] = {}
        for r in self._records:
            if r.severity not in (
                DriftSeverity.LOW,
                DriftSeverity.INFORMATIONAL,
            ):
                non_clean[r.config_name] = non_clean.get(r.config_name, 0) + 1
        results: list[dict[str, Any]] = []
        for cfg, count in non_clean.items():
            if count > 3:
                results.append(
                    {
                        "config_name": cfg,
                        "non_clean_count": count,
                        "pattern_detected": True,
                    }
                )
        results.sort(
            key=lambda x: x["non_clean_count"],
            reverse=True,
        )
        return results

    # -- report / stats ----------------------------------------------

    def generate_report(self) -> DriftAnalyzerReport:
        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        for r in self._records:
            by_type[r.drift_type.value] = by_type.get(r.drift_type.value, 0) + 1
            by_severity[r.severity.value] = by_severity.get(r.severity.value, 0) + 1
        clean_count = sum(
            1
            for r in self._records
            if r.severity
            in (
                DriftSeverity.LOW,
                DriftSeverity.INFORMATIONAL,
            )
        )
        clean_rate = (
            round(
                clean_count / len(self._records) * 100,
                2,
            )
            if self._records
            else 0.0
        )
        critical_drifts = sum(1 for d in self.identify_critical_drifts())
        recs: list[str] = []
        if clean_rate < 100.0 and self._records:
            recs.append(f"Clean rate {clean_rate}% is below 100% threshold")
        if critical_drifts > 0:
            recs.append(f"{critical_drifts} config(s) with critical drifts")
        patterns = len(self.detect_drift_patterns())
        if patterns > 0:
            recs.append(f"{patterns} config(s) with drift patterns detected")
        if not recs:
            recs.append("Configuration drift is healthy across all environments")
        return DriftAnalyzerReport(
            total_drifts=len(self._records),
            total_rules=len(self._policies),
            clean_rate_pct=clean_rate,
            by_type=by_type,
            by_severity=by_severity,
            critical_drift_count=critical_drifts,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._policies.clear()
        logger.info("drift_analyzer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.drift_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_drifts": len(self._records),
            "total_rules": len(self._policies),
            "max_deviation_pct": (self._max_deviation_pct),
            "drift_type_distribution": type_dist,
            "unique_configs": len({r.config_name for r in self._records}),
        }
