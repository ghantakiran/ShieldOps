"""Access Anomaly Detector — detect anomalous access patterns."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class AnomalyType(StrEnum):
    UNUSUAL_TIME = "unusual_time"
    IMPOSSIBLE_TRAVEL = "impossible_travel"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    BULK_ACCESS = "bulk_access"
    DORMANT_REACTIVATION = "dormant_reactivation"


class ThreatLevel(StrEnum):
    BENIGN = "benign"
    SUSPICIOUS = "suspicious"
    ELEVATED = "elevated"
    HIGH_RISK = "high_risk"
    CONFIRMED_THREAT = "confirmed_threat"


class AccessContext(StrEnum):
    CORPORATE_NETWORK = "corporate_network"
    VPN = "vpn"
    PUBLIC_INTERNET = "public_internet"
    CLOUD_CONSOLE = "cloud_console"
    API_KEY = "api_key"


# --- Models ---


class AccessAnomalyRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    anomaly_type: AnomalyType = AnomalyType.UNUSUAL_TIME
    threat_level: ThreatLevel = ThreatLevel.SUSPICIOUS
    context: AccessContext = AccessContext.CORPORATE_NETWORK
    source_ip: str = ""
    location: str = ""
    resource_accessed: str = ""
    threat_score: float = 0.0
    investigated: bool = False
    false_positive: bool = False
    created_at: float = Field(default_factory=time.time)


class AccessBaseline(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    usual_hours: list[int] = Field(default_factory=lambda: list(range(8, 18)))
    usual_locations: list[str] = Field(default_factory=list)
    usual_contexts: list[str] = Field(default_factory=list)
    avg_daily_accesses: float = 0.0
    last_active_at: float = 0.0
    created_at: float = Field(default_factory=time.time)


class AccessAnomalyReport(BaseModel):
    total_anomalies: int = 0
    high_risk_count: int = 0
    investigated_count: int = 0
    false_positive_rate_pct: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_threat_level: dict[str, int] = Field(default_factory=dict)
    high_risk_users: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AccessAnomalyDetector:
    """Detect anomalous access patterns."""

    def __init__(
        self,
        max_records: int = 200000,
        threat_threshold: float = 0.7,
    ) -> None:
        self._max_records = max_records
        self._threat_threshold = threat_threshold
        self._records: list[AccessAnomalyRecord] = []
        self._baselines: dict[str, AccessBaseline] = {}
        logger.info(
            "access_anomaly.initialized",
            max_records=max_records,
            threat_threshold=threat_threshold,
        )

    # -- internal helpers ------------------------------------------------

    def _score_to_threat_level(self, score: float) -> ThreatLevel:
        if score < 0.3:
            return ThreatLevel.BENIGN
        if score < 0.5:
            return ThreatLevel.SUSPICIOUS
        if score < 0.7:
            return ThreatLevel.ELEVATED
        if score < 0.9:
            return ThreatLevel.HIGH_RISK
        return ThreatLevel.CONFIRMED_THREAT

    # -- record / get / list ---------------------------------------------

    def record_anomaly(
        self,
        user_id: str,
        anomaly_type: AnomalyType,
        context: AccessContext = AccessContext.CORPORATE_NETWORK,
        source_ip: str = "",
        location: str = "",
        resource_accessed: str = "",
        threat_score: float = 0.5,
    ) -> AccessAnomalyRecord:
        threat_level = self._score_to_threat_level(threat_score)
        record = AccessAnomalyRecord(
            user_id=user_id,
            anomaly_type=anomaly_type,
            threat_level=threat_level,
            context=context,
            source_ip=source_ip,
            location=location,
            resource_accessed=resource_accessed,
            threat_score=threat_score,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "access_anomaly.anomaly_recorded",
            record_id=record.id,
            user_id=user_id,
            anomaly_type=anomaly_type.value,
            threat_level=threat_level.value,
        )
        return record

    def get_anomaly(self, record_id: str) -> AccessAnomalyRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_anomalies(
        self,
        user_id: str | None = None,
        anomaly_type: AnomalyType | None = None,
        limit: int = 50,
    ) -> list[AccessAnomalyRecord]:
        results = list(self._records)
        if user_id is not None:
            results = [r for r in results if r.user_id == user_id]
        if anomaly_type is not None:
            results = [r for r in results if r.anomaly_type == anomaly_type]
        return results[-limit:]

    # -- domain operations -----------------------------------------------

    def assess_threat_level(self, record_id: str) -> dict[str, Any]:
        """Re-assess threat level for a specific anomaly."""
        record = self.get_anomaly(record_id)
        if record is None:
            return {"found": False, "record_id": record_id}
        previous = record.threat_level.value
        new_level = self._score_to_threat_level(record.threat_score)
        # Adjust score upward if user has multiple anomalies
        user_anomalies = [r for r in self._records if r.user_id == record.user_id]
        if len(user_anomalies) >= 3:
            adjusted_score = min(record.threat_score + 0.1, 1.0)
            new_level = self._score_to_threat_level(adjusted_score)
        record.threat_level = new_level
        logger.info(
            "access_anomaly.threat_assessed",
            record_id=record_id,
            previous=previous,
            new_level=new_level.value,
        )
        return {
            "found": True,
            "record_id": record_id,
            "user_id": record.user_id,
            "previous_level": previous,
            "new_level": new_level.value,
            "threat_score": record.threat_score,
            "user_anomaly_count": len(user_anomalies),
        }

    def create_baseline(
        self,
        user_id: str,
        usual_hours: list[int] | None = None,
        usual_locations: list[str] | None = None,
        usual_contexts: list[str] | None = None,
        avg_daily_accesses: float = 0.0,
    ) -> AccessBaseline:
        baseline = AccessBaseline(
            user_id=user_id,
            usual_hours=usual_hours if usual_hours is not None else list(range(8, 18)),
            usual_locations=usual_locations or [],
            usual_contexts=usual_contexts or [],
            avg_daily_accesses=avg_daily_accesses,
            last_active_at=time.time(),
        )
        self._baselines[user_id] = baseline
        logger.info(
            "access_anomaly.baseline_created",
            baseline_id=baseline.id,
            user_id=user_id,
        )
        return baseline

    def detect_impossible_travel(
        self,
        user_id: str,
        location_a: str,
        location_b: str,
        time_diff_minutes: float,
    ) -> dict[str, Any]:
        """Flag if locations are far but time too short (<120 min)."""
        is_impossible = location_a != location_b and time_diff_minutes < 120
        threat_score = 0.0
        if is_impossible:
            # Higher score for shorter time differences
            threat_score = round(min(1.0, 1.0 - (time_diff_minutes / 120)), 4)
            self.record_anomaly(
                user_id=user_id,
                anomaly_type=AnomalyType.IMPOSSIBLE_TRAVEL,
                location=f"{location_a} -> {location_b}",
                threat_score=threat_score,
            )
        logger.info(
            "access_anomaly.impossible_travel_checked",
            user_id=user_id,
            is_impossible=is_impossible,
        )
        return {
            "user_id": user_id,
            "location_a": location_a,
            "location_b": location_b,
            "time_diff_minutes": time_diff_minutes,
            "is_impossible": is_impossible,
            "threat_score": threat_score,
        }

    def identify_high_risk_users(self) -> list[dict[str, Any]]:
        """Users with highest threat exposure."""
        user_scores: dict[str, list[float]] = {}
        user_counts: dict[str, int] = {}
        for r in self._records:
            user_scores.setdefault(r.user_id, []).append(r.threat_score)
            user_counts[r.user_id] = user_counts.get(r.user_id, 0) + 1
        results: list[dict[str, Any]] = []
        for uid, scores in user_scores.items():
            max_score = max(scores)
            avg_score = round(sum(scores) / len(scores), 4)
            if max_score >= self._threat_threshold:
                results.append(
                    {
                        "user_id": uid,
                        "anomaly_count": user_counts[uid],
                        "max_threat_score": max_score,
                        "avg_threat_score": avg_score,
                        "threat_level": self._score_to_threat_level(max_score).value,
                    }
                )
        results.sort(key=lambda x: x["max_threat_score"], reverse=True)
        return results

    def mark_investigated(
        self,
        record_id: str,
        false_positive: bool = False,
    ) -> dict[str, Any]:
        record = self.get_anomaly(record_id)
        if record is None:
            return {"found": False, "record_id": record_id}
        record.investigated = True
        record.false_positive = false_positive
        logger.info(
            "access_anomaly.marked_investigated",
            record_id=record_id,
            false_positive=false_positive,
        )
        return {
            "found": True,
            "record_id": record_id,
            "user_id": record.user_id,
            "investigated": True,
            "false_positive": false_positive,
        }

    # -- report / stats --------------------------------------------------

    def generate_anomaly_report(self) -> AccessAnomalyReport:
        by_type: dict[str, int] = {}
        by_threat_level: dict[str, int] = {}
        for r in self._records:
            by_type[r.anomaly_type.value] = by_type.get(r.anomaly_type.value, 0) + 1
            by_threat_level[r.threat_level.value] = by_threat_level.get(r.threat_level.value, 0) + 1
        high_risk_count = sum(
            1
            for r in self._records
            if r.threat_level in (ThreatLevel.HIGH_RISK, ThreatLevel.CONFIRMED_THREAT)
        )
        investigated_count = sum(1 for r in self._records if r.investigated)
        false_positives = sum(1 for r in self._records if r.investigated and r.false_positive)
        fp_rate = (
            round(false_positives / investigated_count * 100, 2) if investigated_count > 0 else 0.0
        )
        high_risk_users = self.identify_high_risk_users()
        hr_user_ids = [u["user_id"] for u in high_risk_users[:5]]
        recs: list[str] = []
        if high_risk_count > 0:
            recs.append(f"{high_risk_count} high-risk anomaly(ies) detected")
        uninvestigated = len(self._records) - investigated_count
        if uninvestigated > 0:
            recs.append(f"{uninvestigated} anomaly(ies) pending investigation")
        if fp_rate > 50:
            recs.append("High false positive rate — consider tuning detection rules")
        impossible_travel = by_type.get(AnomalyType.IMPOSSIBLE_TRAVEL.value, 0)
        if impossible_travel > 0:
            recs.append(f"{impossible_travel} impossible travel event(s) — verify user locations")
        if not recs:
            recs.append("No significant access anomalies detected")
        return AccessAnomalyReport(
            total_anomalies=len(self._records),
            high_risk_count=high_risk_count,
            investigated_count=investigated_count,
            false_positive_rate_pct=fp_rate,
            by_type=by_type,
            by_threat_level=by_threat_level,
            high_risk_users=hr_user_ids,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._baselines.clear()
        logger.info("access_anomaly.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.anomaly_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_anomalies": len(self._records),
            "total_baselines": len(self._baselines),
            "threat_threshold": self._threat_threshold,
            "type_distribution": type_dist,
            "unique_users": len({r.user_id for r in self._records}),
            "investigated": sum(1 for r in self._records if r.investigated),
        }
