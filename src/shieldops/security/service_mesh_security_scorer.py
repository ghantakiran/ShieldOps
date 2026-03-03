"""Service Mesh Security Scorer — score service mesh security posture and configuration."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class MeshComponent(StrEnum):
    MTLS = "mtls"
    AUTHORIZATION = "authorization"
    RATE_LIMITING = "rate_limiting"
    OBSERVABILITY = "observability"
    ENCRYPTION = "encryption"


class SecurityPosture(StrEnum):
    HARDENED = "hardened"
    SECURE = "secure"
    PARTIAL = "partial"
    WEAK = "weak"
    INSECURE = "insecure"


class MeshType(StrEnum):
    ISTIO = "istio"
    LINKERD = "linkerd"
    CONSUL = "consul"
    ENVOY = "envoy"
    CUSTOM = "custom"


# --- Models ---


class MeshSecurityRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mesh_id: str = ""
    mesh_component: MeshComponent = MeshComponent.MTLS
    security_posture: SecurityPosture = SecurityPosture.HARDENED
    mesh_type: MeshType = MeshType.ISTIO
    security_score: float = 0.0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class MeshSecurityAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mesh_id: str = ""
    mesh_component: MeshComponent = MeshComponent.MTLS
    analysis_score: float = 0.0
    threshold: float = 0.0
    breached: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class ServiceMeshSecurityReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    gap_count: int = 0
    avg_security_score: float = 0.0
    by_component: dict[str, int] = Field(default_factory=dict)
    by_posture: dict[str, int] = Field(default_factory=dict)
    by_mesh_type: dict[str, int] = Field(default_factory=dict)
    top_gaps: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ServiceMeshSecurityScorer:
    """Score service mesh security posture, mTLS coverage, and authorization policies."""

    def __init__(
        self,
        max_records: int = 200000,
        security_gap_threshold: float = 50.0,
    ) -> None:
        self._max_records = max_records
        self._security_gap_threshold = security_gap_threshold
        self._records: list[MeshSecurityRecord] = []
        self._analyses: list[MeshSecurityAnalysis] = []
        logger.info(
            "service_mesh_security_scorer.initialized",
            max_records=max_records,
            security_gap_threshold=security_gap_threshold,
        )

    # -- record / get / list ------------------------------------------------

    def record_mesh(
        self,
        mesh_id: str,
        mesh_component: MeshComponent = MeshComponent.MTLS,
        security_posture: SecurityPosture = SecurityPosture.HARDENED,
        mesh_type: MeshType = MeshType.ISTIO,
        security_score: float = 0.0,
        service: str = "",
        team: str = "",
    ) -> MeshSecurityRecord:
        record = MeshSecurityRecord(
            mesh_id=mesh_id,
            mesh_component=mesh_component,
            security_posture=security_posture,
            mesh_type=mesh_type,
            security_score=security_score,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "service_mesh_security_scorer.mesh_recorded",
            record_id=record.id,
            mesh_id=mesh_id,
            mesh_component=mesh_component.value,
            security_posture=security_posture.value,
        )
        return record

    def get_mesh(self, record_id: str) -> MeshSecurityRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_meshes(
        self,
        mesh_component: MeshComponent | None = None,
        security_posture: SecurityPosture | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[MeshSecurityRecord]:
        results = list(self._records)
        if mesh_component is not None:
            results = [r for r in results if r.mesh_component == mesh_component]
        if security_posture is not None:
            results = [r for r in results if r.security_posture == security_posture]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_analysis(
        self,
        mesh_id: str,
        mesh_component: MeshComponent = MeshComponent.MTLS,
        analysis_score: float = 0.0,
        threshold: float = 0.0,
        breached: bool = False,
        description: str = "",
    ) -> MeshSecurityAnalysis:
        analysis = MeshSecurityAnalysis(
            mesh_id=mesh_id,
            mesh_component=mesh_component,
            analysis_score=analysis_score,
            threshold=threshold,
            breached=breached,
            description=description,
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        logger.info(
            "service_mesh_security_scorer.analysis_added",
            mesh_id=mesh_id,
            mesh_component=mesh_component.value,
            analysis_score=analysis_score,
        )
        return analysis

    # -- domain operations --------------------------------------------------

    def analyze_component_distribution(self) -> dict[str, Any]:
        """Group by mesh_component; return count and avg security_score."""
        component_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.mesh_component.value
            component_data.setdefault(key, []).append(r.security_score)
        result: dict[str, Any] = {}
        for component, scores in component_data.items():
            result[component] = {
                "count": len(scores),
                "avg_security_score": round(sum(scores) / len(scores), 2),
            }
        return result

    def identify_security_gaps(self) -> list[dict[str, Any]]:
        """Return records where security_score < security_gap_threshold."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.security_score < self._security_gap_threshold:
                results.append(
                    {
                        "record_id": r.id,
                        "mesh_id": r.mesh_id,
                        "mesh_component": r.mesh_component.value,
                        "security_score": r.security_score,
                        "service": r.service,
                        "team": r.team,
                    }
                )
        return sorted(results, key=lambda x: x["security_score"])

    def rank_by_security(self) -> list[dict[str, Any]]:
        """Group by service, avg security_score, sort ascending (lowest first)."""
        svc_scores: dict[str, list[float]] = {}
        for r in self._records:
            svc_scores.setdefault(r.service, []).append(r.security_score)
        results: list[dict[str, Any]] = []
        for svc, scores in svc_scores.items():
            results.append(
                {
                    "service": svc,
                    "avg_security_score": round(sum(scores) / len(scores), 2),
                }
            )
        results.sort(key=lambda x: x["avg_security_score"])
        return results

    def detect_security_trends(self) -> dict[str, Any]:
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

    def generate_report(self) -> ServiceMeshSecurityReport:
        by_component: dict[str, int] = {}
        by_posture: dict[str, int] = {}
        by_mesh_type: dict[str, int] = {}
        for r in self._records:
            by_component[r.mesh_component.value] = by_component.get(r.mesh_component.value, 0) + 1
            by_posture[r.security_posture.value] = by_posture.get(r.security_posture.value, 0) + 1
            by_mesh_type[r.mesh_type.value] = by_mesh_type.get(r.mesh_type.value, 0) + 1
        gap_count = sum(1 for r in self._records if r.security_score < self._security_gap_threshold)
        scores = [r.security_score for r in self._records]
        avg_security_score = round(sum(scores) / len(scores), 2) if scores else 0.0
        gap_list = self.identify_security_gaps()
        top_gaps = [o["mesh_id"] for o in gap_list[:5]]
        recs: list[str] = []
        if self._records and gap_count > 0:
            recs.append(
                f"{gap_count} mesh(es) below security threshold ({self._security_gap_threshold})"
            )
        if self._records and avg_security_score < self._security_gap_threshold:
            recs.append(
                f"Avg security score {avg_security_score} below threshold "
                f"({self._security_gap_threshold})"
            )
        if not recs:
            recs.append("Service mesh security posture is healthy")
        return ServiceMeshSecurityReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            gap_count=gap_count,
            avg_security_score=avg_security_score,
            by_component=by_component,
            by_posture=by_posture,
            by_mesh_type=by_mesh_type,
            top_gaps=top_gaps,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("service_mesh_security_scorer.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        component_dist: dict[str, int] = {}
        for r in self._records:
            key = r.mesh_component.value
            component_dist[key] = component_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "security_gap_threshold": self._security_gap_threshold,
            "component_distribution": component_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_services": len({r.service for r in self._records}),
        }
