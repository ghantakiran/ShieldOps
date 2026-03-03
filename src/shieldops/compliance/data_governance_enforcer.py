"""Data Governance Enforcer — enforce data classification and governance policies."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class DataClassification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"  # noqa: S105


class GovernanceAction(StrEnum):
    CLASSIFY = "classify"
    ENCRYPT = "encrypt"
    MASK = "mask"
    RETAIN = "retain"
    DELETE = "delete"


class GovernanceStatus(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    REMEDIATION = "remediation"
    EXCEPTION = "exception"
    UNKNOWN = "unknown"


# --- Models ---


class GovernanceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data_asset: str = ""
    data_classification: DataClassification = DataClassification.PUBLIC
    governance_action: GovernanceAction = GovernanceAction.CLASSIFY
    governance_status: GovernanceStatus = GovernanceStatus.COMPLIANT
    governance_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class GovernanceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    data_asset: str = ""
    data_classification: DataClassification = DataClassification.PUBLIC
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class DataGovernanceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_governance_score: float = 0.0
    by_classification: dict[str, int] = Field(default_factory=dict)
    by_action: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class DataGovernanceEnforcer:
    """Enforce data governance policies, track classification, identify governance gaps."""

    def __init__(
        self,
        max_records: int = 200000,
        threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._threshold = threshold
        self._records: list[GovernanceRecord] = []
        self._analyses: list[GovernanceAnalysis] = []
        logger.info(
            "data_governance_enforcer.initialized",
            max_records=max_records,
            threshold=threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_governance(
        self,
        data_asset: str,
        data_classification: DataClassification = DataClassification.PUBLIC,
        governance_action: GovernanceAction = GovernanceAction.CLASSIFY,
        governance_status: GovernanceStatus = GovernanceStatus.COMPLIANT,
        governance_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> GovernanceRecord:
        record = GovernanceRecord(
            data_asset=data_asset,
            data_classification=data_classification,
            governance_action=governance_action,
            governance_status=governance_status,
            governance_score=governance_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "data_governance_enforcer.governance_recorded",
            record_id=record.id,
            data_asset=data_asset,
            data_classification=data_classification.value,
            governance_action=governance_action.value,
        )
        return record

    def get_record(self, record_id: str) -> GovernanceRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_records(
        self,
        data_classification: DataClassification | None = None,
        governance_status: GovernanceStatus | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[GovernanceRecord]:
        results = list(self._records)
        if data_classification is not None:
            results = [r for r in results if r.data_classification == data_classification]
        if governance_status is not None:
            results = [r for r in results if r.governance_status == governance_status]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        data_asset: str,
        data_classification: DataClassification = DataClassification.PUBLIC,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> GovernanceAnalysis:
        analysis = GovernanceAnalysis(
            data_asset=data_asset,
            data_classification=data_classification,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "data_governance_enforcer.analysis_added",
            data_asset=data_asset,
            data_classification=data_classification.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_distribution(self) -> dict[str, Any]:
        """Group by data_classification; return count and avg governance_score."""
        class_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.data_classification.value
            class_data.setdefault(key, []).append(r.governance_score)
        result: dict[str, Any] = {}
        for classification, scores in class_data.items():
            result[classification] = {
                "count": len(scores),
                "avg_governance_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_gaps(self) -> list[dict[str, Any]]:
        """Return records where governance_score < threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.governance_score < self._threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "data_asset": r.data_asset,
                        "data_classification": r.data_classification.value,
                        "governance_score": r.governance_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["governance_score"])

    def rank_by_score(self) -> list[dict[str, Any]]:
        """Group by service, avg governance_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.governance_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_governance_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_governance_score"])
        return results

    def detect_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
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
            trend = "improving"
        else:
            trend = "degrading"
        return {
            "trend": trend,
            "delta": delta,
            "avg_first_half": round(avg_first, 2),
            "avg_second_half": round(avg_second, 2),
        }

    # -- report / stats -----------------------------------------------------

    def generate_report(self) -> DataGovernanceReport:
        by_classification: dict[str, int] = {}
        by_action: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for r in self._records:
            by_classification[r.data_classification.value] = (
                by_classification.get(r.data_classification.value, 0) + 1
            )
            by_action[r.governance_action.value] = by_action.get(r.governance_action.value, 0) + 1
            by_status[r.governance_status.value] = by_status.get(r.governance_status.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.governance_score < self._threshold)
        scores = [r.governance_score for r in self._records]
        avg_governance_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_gaps()
        top_gaps = [o["data_asset"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(f"{gap_count} data asset(s) below governance threshold ({self._threshold})")
        if self._records and avg_governance_score < self._threshold:
            recs.append(
                f"Avg governance score {avg_governance_score} below threshold ({self._threshold})"
            )
        if not recs:
            recs.append("Data governance is healthy")
        return DataGovernanceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_governance_score=avg_governance_score,
            by_classification=by_classification,
            by_action=by_action,
            by_status=by_status,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("data_governance_enforcer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        class_dist: dict[str, int] = {}
        for r in self._records:
            key = r.data_classification.value
            class_dist[key] = class_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "threshold": self._threshold,
            "classification_distribution": class_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
