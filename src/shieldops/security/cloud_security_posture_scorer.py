"""Cloud Security Posture Scorer — cloud misconfig scoring across AWS/GCP/Azure."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CloudProvider(StrEnum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    MULTI_CLOUD = "multi_cloud"
    HYBRID = "hybrid"


class PostureCategory(StrEnum):
    IAM = "iam"
    NETWORK = "network"
    STORAGE = "storage"
    COMPUTE = "compute"
    LOGGING = "logging"


class ComplianceState(StrEnum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    EXEMPT = "exempt"
    UNKNOWN = "unknown"


# --- Models ---


class PostureRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    finding_name: str = ""
    cloud_provider: CloudProvider = CloudProvider.AWS
    posture_category: PostureCategory = PostureCategory.IAM
    compliance_state: ComplianceState = ComplianceState.COMPLIANT
    posture_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class PostureAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    finding_name: str = ""
    cloud_provider: CloudProvider = CloudProvider.AWS
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class PostureReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    low_posture_count: int = 0
    avg_posture_score: float = 0.0
    by_provider: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    by_state: dict[str, int] = Field(default_factory=dict)
    top_low_posture: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class CloudSecurityPostureScorer:
    """Cloud misconfiguration scoring across AWS, GCP, and Azure."""

    def __init__(
        self,
        max_records: int = 200000,
        posture_threshold: float = 80.0,
    ) -> None:
        self._max_records = max_records
        self._posture_threshold = posture_threshold
        self._records: list[PostureRecord] = []
        self._analyses: list[PostureAnalysis] = []
        logger.info(
            "cloud_security_posture_scorer.initialized",
            max_records=max_records,
            posture_threshold=posture_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_finding(
        self,
        finding_name: str,
        cloud_provider: CloudProvider = CloudProvider.AWS,
        posture_category: PostureCategory = PostureCategory.IAM,
        compliance_state: ComplianceState = ComplianceState.COMPLIANT,
        posture_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> PostureRecord:
        record = PostureRecord(
            finding_name=finding_name,
            cloud_provider=cloud_provider,
            posture_category=posture_category,
            compliance_state=compliance_state,
            posture_score=posture_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "cloud_security_posture_scorer.finding_recorded",
            record_id=record.id,
            finding_name=finding_name,
            cloud_provider=cloud_provider.value,
            posture_category=posture_category.value,
        )
        return record

    def get_finding(self, record_id: str) -> PostureRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_findings(
        self,
        cloud_provider: CloudProvider | None = None,
        posture_category: PostureCategory | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[PostureRecord]:
        results = list(self._records)
        if cloud_provider is not None:
            results = [r for r in results if r.cloud_provider == cloud_provider]
        if posture_category is not None:
            results = [r for r in results if r.posture_category == posture_category]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        finding_name: str,
        cloud_provider: CloudProvider = CloudProvider.AWS,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> PostureAnalysis:
        analysis = PostureAnalysis(
            finding_name=finding_name,
            cloud_provider=cloud_provider,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "cloud_security_posture_scorer.analysis_added",
            finding_name=finding_name,
            cloud_provider=cloud_provider.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_provider_distribution(self) -> dict[str, Any]:
        """Group by cloud_provider; return count and avg posture_score."""
        prov_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.cloud_provider.value
            prov_data.setdefault(key, []).append(r.posture_score)
        result: dict[str, Any] = {}
        for prov, scores in prov_data.items():
            result[prov] = {
                "count": len(scores),
                "avg_posture_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_low_posture_findings(self) -> list[dict[str, Any]]:
        """Return records where posture_score < posture_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.posture_score < self._posture_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "finding_name": r.finding_name,
                        "cloud_provider": r.cloud_provider.value,
                        "posture_score": r.posture_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["posture_score"])

    def rank_by_posture_score(self) -> list[dict[str, Any]]:
        """Group by service, avg posture_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.posture_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_posture_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_posture_score"])
        return results

    def detect_posture_trends(self) -> dict[str, Any]:
        """Split-half comparison on analysis_score; delta threshold 5.0."""
        if len(self._analyses) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        vals = [c.analysis_score for c in self._analyses]
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

    def generate_report(self) -> PostureReport:
        by_provider: dict[str, int] = {}
        by_category: dict[str, int] = {}
        by_state: dict[str, int] = {}
        for r in self._records:
            by_provider[r.cloud_provider.value] = by_provider.get(r.cloud_provider.value, 0) + 1
            by_category[r.posture_category.value] = by_category.get(r.posture_category.value, 0) + 1
            by_state[r.compliance_state.value] = by_state.get(r.compliance_state.value, 0) + 1
        low_posture_count = sum(
            1 for r in self._records if r.posture_score < self._posture_threshold
        )
        scores = [r.posture_score for r in self._records]
        avg_posture_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        low_list = self.identify_low_posture_findings()
        top_low_posture = [o["finding_name"] for o in low_list[:5]]
        recs: list[str] = []
        if self._records and low_posture_count > 0:
            recs.append(
                f"{low_posture_count} finding(s) below posture threshold "
                f"({self._posture_threshold})"
            )
        if self._records and avg_posture_score < self._posture_threshold:
            recs.append(
                f"Avg posture score {avg_posture_score} below threshold ({self._posture_threshold})"
            )
        if not recs:
            recs.append("Cloud security posture is healthy")
        return PostureReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            low_posture_count=low_posture_count,
            avg_posture_score=avg_posture_score,
            by_provider=by_provider,
            by_category=by_category,
            by_state=by_state,
            top_low_posture=top_low_posture,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("cloud_security_posture_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        provider_dist: dict[str, int] = {}
        for r in self._records:
            key = r.cloud_provider.value
            provider_dist[key] = provider_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "posture_threshold": self._posture_threshold,
            "provider_distribution": provider_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
