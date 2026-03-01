"""API Contract Drift Detector — detect breaking contract changes between services."""

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
    FIELD_REMOVED = "field_removed"
    TYPE_CHANGED = "type_changed"
    ENDPOINT_REMOVED = "endpoint_removed"
    SCHEMA_MISMATCH = "schema_mismatch"
    VERSION_CONFLICT = "version_conflict"


class DriftSeverity(StrEnum):
    BREAKING = "breaking"
    MAJOR = "major"
    MINOR = "minor"
    COSMETIC = "cosmetic"
    NONE = "none"


class DriftSource(StrEnum):
    PRODUCER_CHANGE = "producer_change"
    CONSUMER_CHANGE = "consumer_change"
    SCHEMA_EVOLUTION = "schema_evolution"
    DOCUMENTATION_GAP = "documentation_gap"
    DEPLOYMENT_MISMATCH = "deployment_mismatch"


# --- Models ---


class ContractDriftRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_id: str = ""
    drift_type: DriftType = DriftType.FIELD_REMOVED
    drift_severity: DriftSeverity = DriftSeverity.NONE
    drift_source: DriftSource = DriftSource.PRODUCER_CHANGE
    drift_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class DriftDetail(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_id: str = ""
    drift_type: DriftType = DriftType.FIELD_REMOVED
    detail_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class APIContractDriftReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_details: int = 0
    breaking_drifts: int = 0
    avg_drift_score: float = 0.0
    by_drift_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    top_drifting: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class APIContractDriftDetector:
    """Detect breaking contract changes between services, schema drift detection."""

    def __init__(
        self,
        max_records: int = 200000,
        max_breaking_drift_pct: float = 5.0,
    ) -> None:
        self._max_records = max_records
        self._max_breaking_drift_pct = max_breaking_drift_pct
        self._records: list[ContractDriftRecord] = []
        self._details: list[DriftDetail] = []
        logger.info(
            "api_contract_drift.initialized",
            max_records=max_records,
            max_breaking_drift_pct=max_breaking_drift_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_drift(
        self,
        contract_id: str,
        drift_type: DriftType = DriftType.FIELD_REMOVED,
        drift_severity: DriftSeverity = DriftSeverity.NONE,
        drift_source: DriftSource = DriftSource.PRODUCER_CHANGE,
        drift_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> ContractDriftRecord:
        record = ContractDriftRecord(
            contract_id=contract_id,
            drift_type=drift_type,
            drift_severity=drift_severity,
            drift_source=drift_source,
            drift_score=drift_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "api_contract_drift.drift_recorded",
            record_id=record.id,
            contract_id=contract_id,
            drift_type=drift_type.value,
            drift_severity=drift_severity.value,
        )
        return record

    def get_drift(self, record_id: str) -> ContractDriftRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_drifts(
        self,
        drift_type: DriftType | None = None,
        severity: DriftSeverity | None = None,
        service: str | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ContractDriftRecord]:
        results = list(self._records)
        if drift_type is not None:
            results = [r for r in results if r.drift_type == drift_type]
        if severity is not None:
            results = [r for r in results if r.drift_severity == severity]
        if service is not None:
            results = [r for r in results if r.service == service]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_detail(
        self,
        contract_id: str,
        drift_type: DriftType = DriftType.FIELD_REMOVED,
        detail_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> DriftDetail:
        detail = DriftDetail(
            contract_id=contract_id,
            drift_type=drift_type,
            detail_score=detail_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._details.append(detail)
        if len(self._details) > self._max_records:
            self._details = self._details[-self._max_records :]
        logger.info(
            "api_contract_drift.detail_added",
            contract_id=contract_id,
            drift_type=drift_type.value,
            detail_score=detail_score,
        )
        return detail

    # -- domain operations --------------------------------------------------

    def analyze_drift_patterns(self) -> dict[str, Any]:
        """Group by drift_type; return count and avg drift_score."""
        type_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.drift_type.value
            type_data.setdefault(key, []).append(r.drift_score)
        result: dict[str, Any] = {}
        for dtype, scores in type_data.items():
            result[dtype] = {
                "count": len(scores),
                "avg_drift_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_breaking_drifts(self) -> list[dict[str, Any]]:
        """Return records where severity is BREAKING."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.drift_severity == DriftSeverity.BREAKING:
                results.append(
                    {
                        "record_id": r.id,
                        "contract_id": r.contract_id,
                        "drift_type": r.drift_type.value,
                        "drift_source": r.drift_source.value,
                        "drift_score": r.drift_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return results

    def rank_by_drift_score(self) -> list[dict[str, Any]]:
        """Group by service, avg drift_score, sort descending."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.drift_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_drift_score": round(sum(scores) / len(scores), 2),
                    "record_count": len(scores),
                }
            )
        results.sort(key=lambda x: x["avg_drift_score"], reverse=True)
        return results

    def detect_drift_trends(self) -> dict[str, Any]:
        """Split-half comparison on detail_score; delta threshold 5.0."""
        if len(self._details) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [d.detail_score for d in self._details]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> APIContractDriftReport:
        by_drift_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for r in self._records:
            by_drift_type[r.drift_type.value] = by_drift_type.get(r.drift_type.value, 0) + 1
            by_severity[r.drift_severity.value] = by_severity.get(r.drift_severity.value, 0) + 1
            by_source[r.drift_source.value] = by_source.get(r.drift_source.value, 0) + 1
        breaking_drifts = sum(
            1 for r in self._records if r.drift_severity == DriftSeverity.BREAKING
        )
        avg_drift_score = (
            round(sum(r.drift_score for r in self._records) / len(self._records), 2)
            if self._records
            else 0.0
        )
        rankings = self.rank_by_drift_score()
        top_drifting = [rk["service"] for rk in rankings[:5]]
        recs: list[str] = []
        if breaking_drifts > 0:
            recs.append(
                f"{breaking_drifts} breaking drift(s) detected — review contract compatibility"
            )
        if self._records:
            breaking_pct = round(breaking_drifts / len(self._records) * 100, 2)
            if breaking_pct > self._max_breaking_drift_pct:
                recs.append(
                    f"Breaking drift rate {breaking_pct}% exceeds "
                    f"threshold ({self._max_breaking_drift_pct}%)"
                )
        if not recs:
            recs.append("API contract drift levels are acceptable")
        return APIContractDriftReport(
            total_records=len(self._records),
            total_details=len(self._details),
            breaking_drifts=breaking_drifts,
            avg_drift_score=avg_drift_score,
            by_drift_type=by_drift_type,
            by_severity=by_severity,
            by_source=by_source,
            top_drifting=top_drifting,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._details.clear()
        logger.info("api_contract_drift.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        type_dist: dict[str, int] = {}
        for r in self._records:
            key = r.drift_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_details": len(self._details),
            "max_breaking_drift_pct": self._max_breaking_drift_pct,
            "drift_type_distribution": type_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
