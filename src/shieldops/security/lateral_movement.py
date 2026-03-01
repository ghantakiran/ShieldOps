"""Lateral Movement Detector — track movements, hops, and chains."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MovementType(StrEnum):
    CREDENTIAL_HOPPING = "credential_hopping"
    SERVICE_PIVOTING = "service_pivoting"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_STAGING = "data_staging"
    NETWORK_SCANNING = "network_scanning"


class DetectionConfidence(StrEnum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    SPECULATIVE = "speculative"
    FALSE_POSITIVE = "false_positive"


class MovementStage(StrEnum):
    INITIAL_ACCESS = "initial_access"
    DISCOVERY = "discovery"
    LATERAL_MOVE = "lateral_move"
    COLLECTION = "collection"
    EXFILTRATION = "exfiltration"


# --- Models ---


class MovementRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    movement_type: MovementType = MovementType.CREDENTIAL_HOPPING
    detection_confidence: DetectionConfidence = DetectionConfidence.LOW
    movement_stage: MovementStage = MovementStage.INITIAL_ACCESS
    risk_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class MovementHop(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    movement_type: MovementType = MovementType.CREDENTIAL_HOPPING
    source_host: str = ""
    destination_host: str = ""
    hop_count: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class LateralMovementReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_hops: int = 0
    high_risk_movements: int = 0
    avg_risk_score: float = 0.0
    by_movement_type: dict[str, int] = Field(default_factory=dict)
    by_confidence: dict[str, int] = Field(default_factory=dict)
    by_stage: dict[str, int] = Field(default_factory=dict)
    top_services: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class LateralMovementDetector:
    """Track lateral movement, identify patterns, and detect chains."""

    def __init__(
        self,
        max_records: int = 200000,
        min_detection_confidence_pct: float = 70.0,
    ) -> None:
        self._max_records = max_records
        self._min_detection_confidence_pct = min_detection_confidence_pct
        self._records: list[MovementRecord] = []
        self._hops: list[MovementHop] = []
        logger.info(
            "lateral_movement.initialized",
            max_records=max_records,
            min_detection_confidence_pct=min_detection_confidence_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_movement(
        self,
        incident_id: str,
        movement_type: MovementType = MovementType.CREDENTIAL_HOPPING,
        detection_confidence: DetectionConfidence = DetectionConfidence.LOW,
        movement_stage: MovementStage = MovementStage.INITIAL_ACCESS,
        risk_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> MovementRecord:
        record = MovementRecord(
            incident_id=incident_id,
            movement_type=movement_type,
            detection_confidence=detection_confidence,
            movement_stage=movement_stage,
            risk_score=risk_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "lateral_movement.movement_recorded",
            record_id=record.id,
            incident_id=incident_id,
            movement_type=movement_type.value,
            detection_confidence=detection_confidence.value,
        )
        return record

    def get_movement(self, record_id: str) -> MovementRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_movements(
        self,
        movement_type: MovementType | None = None,
        confidence: DetectionConfidence | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MovementRecord]:
        results = list(self._records)
        if movement_type is not None:
            results = [r for r in results if r.movement_type == movement_type]
        if confidence is not None:
            results = [r for r in results if r.detection_confidence == confidence]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_hop(
        self,
        incident_id: str,
        movement_type: MovementType = MovementType.CREDENTIAL_HOPPING,
        source_host: str = "",
        destination_host: str = "",
        hop_count: int = 0,
        description: str = "",
    ) -> MovementHop:
        hop = MovementHop(
            incident_id=incident_id,
            movement_type=movement_type,
            source_host=source_host,
            destination_host=destination_host,
            hop_count=hop_count,
            description=description,
        )
        self._hops.append(hop)
        if len(self._hops) > self._max_records:
            self._hops = self._hops[-self._max_records :]
        logger.info(
            "lateral_movement.hop_added",
            incident_id=incident_id,
            movement_type=movement_type.value,
            hop_count=hop_count,
        )
        return hop

    # -- domain operations --------------------------------------------------

    def analyze_movement_patterns(self) -> dict[str, Any]:
        """Group by movement_type; return count and avg risk score per type."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.movement_type.value
            type_data.setdefault(key, []).append(r.risk_score)
        result: dict[str, Any] = {}
        for movement_type, scores in type_data.items():
            result[movement_type] = {
                "count": len(scores),
                "avg_risk_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_high_risk_movements(self) -> list[dict[str, Any]]:
        """Return records where detection_confidence is HIGH."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.detection_confidence == DetectionConfidence.HIGH:
                results.append(
                    {
                        "record_id": r.id,
                        "incident_id": r.incident_id,
                        "movement_type": r.movement_type.value,
                        "detection_confidence": r.detection_confidence.value,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_risk_score(self) -> list[dict[str, Any]]:
        """Group by service, total records, sort descending by avg risk score."""
        service_data: dict[str, list[float]] = {}
        for r in self._records:
            service_data.setdefault(r.service, []).append(r.risk_score)
        results: list[dict[str, Any]] = []
        for service, scores in service_data.items():
            results.append(
                {
                    "service": service,
                    "movement_count": len(scores),
                    "avg_risk_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_risk_score"], reverse=True)
        return results

    def detect_movement_chains(self) -> dict[str, Any]:
        """Split-half on hop_count; delta threshold 5.0."""
        if len(self._hops) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        values = [h.hop_count for h in self._hops]
        mid = len(values) // 2
        first_half = values[:mid]
        second_half = values[mid:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        delta = round(avg_second - avg_first, 2)
        if abs(delta) < 5.0:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> LateralMovementReport:
        by_movement_type: dict[str, int] = {}
        by_confidence: dict[str, int] = {}
        by_stage: dict[str, int] = {}
        for r in self._records:
            by_movement_type[r.movement_type.value] = (
                by_movement_type.get(r.movement_type.value, 0) + 1
            )
            by_confidence[r.detection_confidence.value] = (
                by_confidence.get(r.detection_confidence.value, 0) + 1
            )
            by_stage[r.movement_stage.value] = by_stage.get(r.movement_stage.value, 0) + 1
        high_risk_count = sum(
            1 for r in self._records if r.detection_confidence == DetectionConfidence.HIGH
        )
        scores = [r.risk_score for r in self._records]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        rankings = self.rank_by_risk_score()
        top_services = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        high_risk_rate = (
            round(high_risk_count / len(self._records) * 100, 2) if self._records else 0.0
        )
        if high_risk_rate > self._min_detection_confidence_pct:
            recs.append(
                f"High-confidence detection rate {high_risk_rate}% exceeds "
                f"threshold ({self._min_detection_confidence_pct}%)"
            )
        if high_risk_count > 0:
            recs.append(
                f"{high_risk_count} high-risk movement(s) detected — investigate immediately"
            )
        if not recs:
            recs.append("Lateral movement risk levels are acceptable")
        return LateralMovementReport(
            total_records=len(self._records),
            total_hops=len(self._hops),
            high_risk_movements=high_risk_count,
            avg_risk_score=avg_score,
            by_movement_type=by_movement_type,
            by_confidence=by_confidence,
            by_stage=by_stage,
            top_services=top_services,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._hops.clear()
        logger.info("lateral_movement.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.movement_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_hops": len(self._hops),
            "min_detection_confidence_pct": self._min_detection_confidence_pct,
            "movement_type_distribution": type_dist,
            "unique_services": len({r.service for r in self._records}),
            "unique_incidents": len({r.incident_id for r in self._records}),
        }
