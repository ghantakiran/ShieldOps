"""Cloud Resource Tagging Compliance
audit tag compliance, detect untagged resources,
rank teams by tagging discipline."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class TagStatus(StrEnum):
    COMPLIANT = "compliant"
    MISSING_REQUIRED = "missing_required"
    INVALID_VALUE = "invalid_value"
    EXCESS = "excess"


class TagCategory(StrEnum):
    COST_CENTER = "cost_center"
    ENVIRONMENT = "environment"
    OWNER = "owner"
    PROJECT = "project"


class ComplianceLevel(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    NONE = "none"


# --- Models ---


class TagComplianceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    resource_name: str = ""
    tag_status: TagStatus = TagStatus.COMPLIANT
    tag_category: TagCategory = TagCategory.COST_CENTER
    compliance_level: ComplianceLevel = ComplianceLevel.PARTIAL
    team_id: str = ""
    missing_tags: int = 0
    total_tags: int = 0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TagComplianceAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    resource_id: str = ""
    compliance_score: float = 0.0
    compliance_level: ComplianceLevel = ComplianceLevel.PARTIAL
    missing_count: int = 0
    is_compliant: bool = False
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class TagComplianceReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_compliance_score: float = 0.0
    by_tag_status: dict[str, int] = Field(default_factory=dict)
    by_tag_category: dict[str, int] = Field(default_factory=dict)
    by_compliance_level: dict[str, int] = Field(default_factory=dict)
    non_compliant_resources: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class CloudResourceTaggingCompliance:
    """Audit tag compliance, detect untagged
    resources, rank teams by tagging discipline."""

    def __init__(self, max_records: int = 200000) -> None:
        self._max_records = max_records
        self._records: list[TagComplianceRecord] = []
        self._analyses: dict[str, TagComplianceAnalysis] = {}
        logger.info(
            "cloud_resource_tagging_compliance.init",
            max_records=max_records,
        )

    def add_record(
        self,
        resource_id: str = "",
        resource_name: str = "",
        tag_status: TagStatus = TagStatus.COMPLIANT,
        tag_category: TagCategory = (TagCategory.COST_CENTER),
        compliance_level: ComplianceLevel = (ComplianceLevel.PARTIAL),
        team_id: str = "",
        missing_tags: int = 0,
        total_tags: int = 0,
        description: str = "",
    ) -> TagComplianceRecord:
        record = TagComplianceRecord(
            resource_id=resource_id,
            resource_name=resource_name,
            tag_status=tag_status,
            tag_category=tag_category,
            compliance_level=compliance_level,
            team_id=team_id,
            missing_tags=missing_tags,
            total_tags=total_tags,
            description=description,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "tag_compliance.record_added",
            record_id=record.id,
            resource_id=resource_id,
        )
        return record

    def process(self, key: str) -> TagComplianceAnalysis | dict[str, Any]:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return {"status": "not_found", "key": key}
        score = (
            round(
                (rec.total_tags - rec.missing_tags) / rec.total_tags * 100,
                2,
            )
            if rec.total_tags > 0
            else 0.0
        )
        is_comp = rec.tag_status == TagStatus.COMPLIANT
        analysis = TagComplianceAnalysis(
            resource_id=rec.resource_id,
            compliance_score=score,
            compliance_level=rec.compliance_level,
            missing_count=rec.missing_tags,
            is_compliant=is_comp,
            description=(f"Resource {rec.resource_id} score {score}"),
        )
        self._analyses[key] = analysis
        return analysis

    def generate_report(
        self,
    ) -> TagComplianceReport:
        by_ts: dict[str, int] = {}
        by_tc: dict[str, int] = {}
        by_cl: dict[str, int] = {}
        scores: list[float] = []
        for r in self._records:
            k = r.tag_status.value
            by_ts[k] = by_ts.get(k, 0) + 1
            k2 = r.tag_category.value
            by_tc[k2] = by_tc.get(k2, 0) + 1
            k3 = r.compliance_level.value
            by_cl[k3] = by_cl.get(k3, 0) + 1
            if r.total_tags > 0:
                s = (r.total_tags - r.missing_tags) / r.total_tags * 100
                scores.append(s)
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0
        non_comp = list(
            {r.resource_id for r in self._records if r.tag_status != TagStatus.COMPLIANT}
        )[:10]
        recs: list[str] = []
        if non_comp:
            recs.append(f"{len(non_comp)} non-compliant resources found")
        if not recs:
            recs.append("All resources are compliant")
        return TagComplianceReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_compliance_score=avg,
            by_tag_status=by_ts,
            by_tag_category=by_tc,
            by_compliance_level=by_cl,
            non_compliant_resources=non_comp,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        ts_dist: dict[str, int] = {}
        for r in self._records:
            k = r.tag_status.value
            ts_dist[k] = ts_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "tag_status_distribution": ts_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records = []
        self._analyses = {}
        logger.info("cloud_resource_tagging_compliance.cleared")
        return {"status": "cleared"}

    # --- domain methods ---

    def audit_tag_compliance(
        self,
    ) -> list[dict[str, Any]]:
        """Audit tag compliance per resource."""
        resource_data: dict[str, dict[str, Any]] = {}
        for r in self._records:
            if r.resource_id not in resource_data:
                resource_data[r.resource_id] = {
                    "resource_id": r.resource_id,
                    "total_tags": r.total_tags,
                    "missing_tags": r.missing_tags,
                    "status": r.tag_status.value,
                    "compliance": (r.compliance_level.value),
                }
        results = list(resource_data.values())
        results.sort(
            key=lambda x: x["missing_tags"],
            reverse=True,
        )
        return results

    def detect_untagged_resources(
        self,
    ) -> list[dict[str, Any]]:
        """Detect resources with missing tags."""
        results: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in self._records:
            if r.missing_tags > 0 and r.resource_id not in seen:
                seen.add(r.resource_id)
                results.append(
                    {
                        "resource_id": r.resource_id,
                        "resource_name": (r.resource_name),
                        "missing_tags": (r.missing_tags),
                        "team_id": r.team_id,
                        "status": (r.tag_status.value),
                    }
                )
        results.sort(
            key=lambda x: x["missing_tags"],
            reverse=True,
        )
        return results

    def rank_teams_by_tagging_discipline(
        self,
    ) -> list[dict[str, Any]]:
        """Rank teams by tagging discipline."""
        team_compliant: dict[str, int] = {}
        team_total: dict[str, int] = {}
        for r in self._records:
            team_total[r.team_id] = team_total.get(r.team_id, 0) + 1
            if r.tag_status == TagStatus.COMPLIANT:
                team_compliant[r.team_id] = team_compliant.get(r.team_id, 0) + 1
        results: list[dict[str, Any]] = []
        for tid, total in team_total.items():
            comp = team_compliant.get(tid, 0)
            rate = round(comp / total * 100, 2)
            results.append(
                {
                    "team_id": tid,
                    "compliance_rate": rate,
                    "compliant_count": comp,
                    "total_count": total,
                    "rank": 0,
                }
            )
        results.sort(
            key=lambda x: x["compliance_rate"],
            reverse=True,
        )
        for i, entry in enumerate(results, 1):
            entry["rank"] = i
        return results
