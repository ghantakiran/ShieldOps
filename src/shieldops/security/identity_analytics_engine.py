"""Identity Analytics Engine
behavior profiling, access pattern analysis, privilege anomaly detection."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class IdentityRiskLevel(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    BASELINE = "baseline"


class AccessPattern(StrEnum):
    NORMAL = "normal"
    UNUSUAL_HOURS = "unusual_hours"
    UNUSUAL_LOCATION = "unusual_location"
    PRIVILEGE_SPIKE = "privilege_spike"
    DORMANT_REACTIVATION = "dormant_reactivation"


class IdentityType(StrEnum):
    HUMAN = "human"
    SERVICE_ACCOUNT = "service_account"
    API_KEY = "api_key"
    FEDERATED = "federated"
    MACHINE = "machine"


# --- Models ---


class IdentityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    identity_name: str = ""
    identity_type: IdentityType = IdentityType.HUMAN
    risk_level: IdentityRiskLevel = IdentityRiskLevel.BASELINE
    access_pattern: AccessPattern = AccessPattern.NORMAL
    risk_score: float = 0.0
    privilege_count: int = 0
    failed_auth_count: int = 0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class IdentityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    identity_name: str = ""
    identity_type: IdentityType = IdentityType.HUMAN
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class IdentityAnalyticsReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_risk_score: float = 0.0
    high_risk_identities: int = 0
    by_risk_level: dict[str, int] = Field(default_factory=dict)
    by_access_pattern: dict[str, int] = Field(default_factory=dict)
    by_identity_type: dict[str, int] = Field(default_factory=dict)
    top_risk_identities: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class IdentityAnalyticsEngine:
    """Identity behavior profiling, access pattern analysis, privilege anomaly detection."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 60.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[IdentityRecord] = []
        self._analyses: list[IdentityAnalysis] = []
        logger.info(
            "identity_analytics_engine.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def add_record(
        self,
        identity_name: str,
        identity_type: IdentityType = IdentityType.HUMAN,
        risk_level: IdentityRiskLevel = IdentityRiskLevel.BASELINE,
        access_pattern: AccessPattern = AccessPattern.NORMAL,
        risk_score: float = 0.0,
        privilege_count: int = 0,
        failed_auth_count: int = 0,
        service: str = "",
        team: str = "",
    ) -> IdentityRecord:
        record = IdentityRecord(
            identity_name=identity_name,
            identity_type=identity_type,
            risk_level=risk_level,
            access_pattern=access_pattern,
            risk_score=risk_score,
            privilege_count=privilege_count,
            failed_auth_count=failed_auth_count,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "identity_analytics_engine.record_added",
            record_id=record.id,
            identity_name=identity_name,
            risk_level=risk_level.value,
        )
        return record

    def get_record(self, record_id: str) -> IdentityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        identity_type: IdentityType | None = None,
        risk_level: IdentityRiskLevel | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[IdentityRecord]:
        results = list(self._records)
        if identity_type is not None:
            results = [r for r in results if r.identity_type == identity_type]
        if risk_level is not None:
            results = [r for r in results if r.risk_level == risk_level]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        identity_name: str,
        identity_type: IdentityType = IdentityType.HUMAN,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> IdentityAnalysis:
        analysis = IdentityAnalysis(
            identity_name=identity_name,
            identity_type=identity_type,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "identity_analytics_engine.analysis_added",
            identity_name=identity_name,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def detect_privilege_anomalies(self) -> list[dict[str, Any]]:
        identity_privs: dict[str, list[int]] = {}
        for r in self._records:
            identity_privs.setdefault(r.identity_name, []).append(r.privilege_count)
        anomalies: list[dict[str, Any]] = []
        for identity, counts in identity_privs.items():
            if len(counts) < 2:
                continue
            avg_priv = sum(counts) / len(counts)
            latest = counts[-1]
            if latest > avg_priv * 1.5 and latest > 5:
                anomalies.append(
                    {
                        "identity_name": identity,
                        "current_privileges": latest,
                        "avg_privileges": round(avg_priv, 1),
                        "spike_factor": round(latest / avg_priv, 2) if avg_priv else 0,
                    }
                )
        return sorted(anomalies, key=lambda x: x["spike_factor"], reverse=True)

    def profile_access_patterns(self) -> dict[str, Any]:
        pattern_data: dict[str, int] = {}
        for r in self._records:
            key = r.access_pattern.value
            pattern_data[key] = pattern_data.get(key, 0) + 1
        total = len(self._records) or 1
        anomalous = sum(v for k, v in pattern_data.items() if k != AccessPattern.NORMAL.value)
        return {
            "pattern_distribution": pattern_data,
            "anomalous_pct": round(anomalous / total * 100, 2),
            "total_identities": total,
        }

    def identify_high_risk(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.risk_score >= self._threshold:
                results.append(
                    {
                        "identity_name": r.identity_name,
                        "identity_type": r.identity_type.value,
                        "risk_score": r.risk_score,
                        "risk_level": r.risk_level.value,
                        "access_pattern": r.access_pattern.value,
                        "failed_auths": r.failed_auth_count,
                    }
                )
        return sorted(results, key=lambda x: x["risk_score"], reverse=True)

    def detect_trends(self) -> dict[str, Any]:
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [a.analysis_score for a in self._analyses]
        mid = len(vals) // 2
        first_half = vals[:mid]
        second_half = vals[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing_risk"
        else:
            trend = "decreasing_risk"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def process(self, identity_name: str) -> dict[str, Any]:
        matching = [r for r in self._records if r.identity_name == identity_name]
        if not matching:
            return {"identity_name": identity_name, "status": "no_data"}
        scores = [r.risk_score for r in matching]
        auths = [r.failed_auth_count for r in matching]
        return {
            "identity_name": identity_name,
            "record_count": len(matching),
            "avg_risk_score": round(sum(scores) / len(scores), 2),
            "total_failed_auths": sum(auths),
            "latest_pattern": matching[-1].access_pattern.value,
        }

    def generate_report(self) -> IdentityAnalyticsReport:
        by_risk: dict[str, int] = {}
        by_pat: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for r in self._records:
            by_risk[r.risk_level.value] = by_risk.get(r.risk_level.value, 0) + 1
            by_pat[r.access_pattern.value] = by_pat.get(r.access_pattern.value, 0) + 1
            by_type[r.identity_type.value] = by_type.get(r.identity_type.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.risk_score >= self._threshold)
        scores = [r.risk_score for r in self._records]
        avg_risk = round(sum(scores) / len(scores), 2) if scores else 0.0
        high_risk = self.identify_high_risk()
        top_risk = [h["identity_name"] for h in high_risk[:5]]
        recs: list[str] = []
        if gap_count > 0:
            recs.append(f"{gap_count} identity(ies) at or above risk threshold ({self._threshold})")
        anomalies = self.detect_privilege_anomalies()
        if anomalies:
            recs.append(f"{len(anomalies)} privilege escalation anomaly(ies) detected")
        svc_accts = by_type.get("service_account", 0)
        if svc_accts > 0 and any(
            r.risk_score >= self._threshold
            for r in self._records
            if r.identity_type == IdentityType.SERVICE_ACCOUNT
        ):
            recs.append("High-risk service accounts detected — review privileges")
        if not recs:
            recs.append("Identity analytics posture is healthy")
        return IdentityAnalyticsReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_risk_score=avg_risk,
            high_risk_identities=len(high_risk),
            by_risk_level=by_risk,
            by_access_pattern=by_pat,
            by_identity_type=by_type,
            top_risk_identities=top_risk,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.identity_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "identity_type_distribution": type_dist,
            "unique_identities": len({r.identity_name for r in self._records}),
            "unique_teams": len({r.team for r in self._records}),
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("identity_analytics_engine.cleared")
        return {"status": "cleared"}
