"""Alert Correlation Cascade Engine
build cascade tree, identify root cause alerts,
quantify cascade blast radius."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class CascadeRole(StrEnum):
    ROOT_CAUSE = "root_cause"
    PROPAGATOR = "propagator"
    SYMPTOM = "symptom"
    INDEPENDENT = "independent"


class CorrelationMethod(StrEnum):
    TEMPORAL = "temporal"
    TOPOLOGICAL = "topological"
    CAUSAL = "causal"
    STATISTICAL = "statistical"


class CascadeDepth(StrEnum):
    SHALLOW = "shallow"
    MODERATE = "moderate"
    DEEP = "deep"
    EXTREME = "extreme"


# --- Models ---


class AlertCorrelationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str = ""
    cascade_role: CascadeRole = CascadeRole.INDEPENDENT
    correlation_method: CorrelationMethod = CorrelationMethod.TEMPORAL
    cascade_depth: CascadeDepth = CascadeDepth.SHALLOW
    parent_alert_id: str = ""
    cascade_id: str = ""
    impact_score: float = 0.0
    source: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertCorrelationAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    alert_id: str = ""
    cascade_role: CascadeRole = CascadeRole.INDEPENDENT
    blast_radius: int = 0
    depth_level: int = 0
    correlation_score: float = 0.0
    is_root_cause: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class AlertCorrelationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_blast_radius: float = 0.0
    by_cascade_role: dict[str, int] = Field(default_factory=dict)
    by_correlation_method: dict[str, int] = Field(default_factory=dict)
    by_cascade_depth: dict[str, int] = Field(default_factory=dict)
    root_cause_alerts: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class AlertCorrelationCascadeEngine:
    """Build cascade tree, identify root cause alerts,
    quantify cascade blast radius."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[AlertCorrelationRecord] = []
        self._analyses: dict[str, AlertCorrelationAnalysis] = {}
        logger.info(
            "alert_correlation_cascade.init",
            max_records=max_records,
        )

    def add_record(
        self,
        alert_id: str = "",
        cascade_role: CascadeRole = (CascadeRole.INDEPENDENT),
        correlation_method: CorrelationMethod = (CorrelationMethod.TEMPORAL),
        cascade_depth: CascadeDepth = (CascadeDepth.SHALLOW),
        parent_alert_id: str = "",
        cascade_id: str = "",
        impact_score: float = 0.0,
        source: str = "",
    ) -> AlertCorrelationRecord:
        record = AlertCorrelationRecord(
            alert_id=alert_id,
            cascade_role=cascade_role,
            correlation_method=correlation_method,
            cascade_depth=cascade_depth,
            parent_alert_id=parent_alert_id,
            cascade_id=cascade_id,
            impact_score=impact_score,
            source=source,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "alert_correlation.record_added",
            record_id=record.id,
            alert_id=alert_id,
        )
        return record

    def process(self, key: str) -> AlertCorrelationAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        cascade_members = [r for r in self._records if r.cascade_id == rec.cascade_id]
        blast = len(cascade_members)
        is_root = rec.cascade_role == CascadeRole.ROOT_CAUSE
        depth_map = {
            CascadeDepth.SHALLOW: 1,
            CascadeDepth.MODERATE: 2,
            CascadeDepth.DEEP: 3,
            CascadeDepth.EXTREME: 4,
        }
        depth = depth_map.get(rec.cascade_depth, 1)
        analysis = AlertCorrelationAnalysis(
            alert_id=rec.alert_id,
            cascade_role=rec.cascade_role,
            blast_radius=blast,
            depth_level=depth,
            correlation_score=round(rec.impact_score, 2),
            is_root_cause=is_root,
            description=(f"Alert {rec.alert_id} blast radius {blast}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> AlertCorrelationReport:
        by_cr: dict[str, int] = {}
        by_cm: dict[str, int] = {}
        by_cd: dict[str, int] = {}
        impacts: list[float] = []
        for r in self._records:
            k = r.cascade_role.value
            by_cr[k] = by_cr.get(k, 0) + 1
            k2 = r.correlation_method.value
            by_cm[k2] = by_cm.get(k2, 0) + 1
            k3 = r.cascade_depth.value
            by_cd[k3] = by_cd.get(k3, 0) + 1
            impacts.append(r.impact_score)
        avg = round(sum(impacts) / len(impacts), 2) if impacts else 0.0
        roots = list(
            {r.alert_id for r in self._records if r.cascade_role == CascadeRole.ROOT_CAUSE}
        )[:10]
        recs: list[str] = []
        if roots:
            recs.append(f"{len(roots)} root cause alerts")
        if not recs:
            recs.append("No cascade patterns found")
        return AlertCorrelationReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_blast_radius=avg,
            by_cascade_role=by_cr,
            by_correlation_method=by_cm,
            by_cascade_depth=by_cd,
            root_cause_alerts=roots,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        cr_dist: dict[str, int] = {}
        for r in self._records:
            k = r.cascade_role.value
            cr_dist[k] = cr_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "cascade_role_distribution": cr_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("alert_correlation_cascade.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def build_cascade_tree(
        self,
    ) -> list[dict[str, Any]]:
        """Build cascade tree from records."""
        cascade_groups: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            if not r.cascade_id:
                continue
            cascade_groups.setdefault(r.cascade_id, []).append(
                {
                    "alert_id": r.alert_id,
                    "role": r.cascade_role.value,
                    "parent": r.parent_alert_id,
                    "depth": r.cascade_depth.value,
                }
            )
        results: list[dict[str, Any]] = []
        for cid, members in cascade_groups.items():
            roots = [m for m in members if m["role"] == "root_cause"]
            results.append(
                {
                    "cascade_id": cid,
                    "member_count": len(members),
                    "root_causes": len(roots),
                    "members": members[:20],
                }
            )
        results.sort(
            key=lambda x: x["member_count"],
            reverse=True,
        )
        return results

    def identify_root_cause_alerts(
        self,
    ) -> list[dict[str, Any]]:
        """Identify root cause alerts."""
        root_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.cascade_role != CascadeRole.ROOT_CAUSE:
                continue
            if r.alert_id not in root_data:
                root_data[r.alert_id] = {
                    "cascades": set(),
                    "impact_total": 0.0,
                    "count": 0,
                }
            root_data[r.alert_id]["cascades"].add(r.cascade_id)
            root_data[r.alert_id]["impact_total"] += r.impact_score
            root_data[r.alert_id]["count"] += 1
        results: list[dict[str, Any]] = []
        for aid, data in root_data.items():
            results.append(
                {
                    "alert_id": aid,
                    "cascade_count": len(data["cascades"]),
                    "total_impact": round(data["impact_total"], 2),
                    "occurrence_count": (data["count"]),
                }
            )
        results.sort(
            key=lambda x: x["total_impact"],
            reverse=True,
        )
        return results

    def quantify_cascade_blast_radius(
        self,
    ) -> list[dict[str, Any]]:
        """Quantify cascade blast radius."""
        cascade_members: dict[str, list[str]] = {}
        cascade_impacts: dict[str, list[float]] = {}
        for r in self._records:
            if not r.cascade_id:
                continue
            cascade_members.setdefault(r.cascade_id, []).append(r.alert_id)
            cascade_impacts.setdefault(r.cascade_id, []).append(r.impact_score)
        results: list[dict[str, Any]] = []
        for cid, members in cascade_members.items():
            impacts = cascade_impacts[cid]
            total_impact = sum(impacts)
            results.append(
                {
                    "cascade_id": cid,
                    "blast_radius": len(members),
                    "total_impact": round(total_impact, 2),
                    "avg_impact": round(
                        total_impact / len(members),
                        2,
                    ),
                    "unique_alerts": len(set(members)),
                }
            )
        results.sort(
            key=lambda x: x["blast_radius"],
            reverse=True,
        )
        return results
