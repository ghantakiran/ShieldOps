"""Knowledge Gap Detector — identify operational knowledge gaps."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class GapType(StrEnum):
    MISSING_RUNBOOK = "missing_runbook"
    OUTDATED_DOC = "outdated_doc"
    UNDOCUMENTED_SERVICE = "undocumented_service"
    TRIBAL_KNOWLEDGE = "tribal_knowledge"
    NO_TROUBLESHOOTING_GUIDE = "no_troubleshooting_guide"


class GapPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class KnowledgeArea(StrEnum):
    INCIDENT_RESPONSE = "incident_response"
    DEPLOYMENT = "deployment"
    ARCHITECTURE = "architecture"
    SECURITY = "security"
    OPERATIONS = "operations"


# --- Models ---


class KnowledgeGap(BaseModel):
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
    )
    service_name: str = ""
    gap_type: GapType = GapType.MISSING_RUNBOOK
    area: KnowledgeArea = KnowledgeArea.INCIDENT_RESPONSE
    priority: GapPriority = GapPriority.MEDIUM
    description: str = ""
    single_expert: str = ""
    doc_age_days: int = 0
    is_resolved: bool = False
    created_at: float = Field(default_factory=time.time)


class KnowledgeCoverage(BaseModel):
    service_name: str = ""
    area: KnowledgeArea = KnowledgeArea.INCIDENT_RESPONSE
    coverage_pct: float = 0.0
    gap_count: int = 0
    critical_gaps: int = 0
    last_reviewed_at: float = Field(
        default_factory=time.time,
    )
    created_at: float = Field(default_factory=time.time)


class KnowledgeReport(BaseModel):
    total_gaps: int = 0
    resolved_gaps: int = 0
    coverage_pct: float = 0.0
    by_type: dict[str, int] = Field(
        default_factory=dict,
    )
    by_priority: dict[str, int] = Field(
        default_factory=dict,
    )
    by_area: dict[str, int] = Field(
        default_factory=dict,
    )
    tribal_knowledge_risks: list[str] = Field(
        default_factory=list,
    )
    recommendations: list[str] = Field(
        default_factory=list,
    )
    generated_at: float = Field(default_factory=time.time)


# --- Detector ---


class KnowledgeGapDetector:
    """Identify gaps in operational knowledge."""

    def __init__(
        self,
        max_gaps: int = 100000,
        stale_doc_threshold_days: int = 180,
    ) -> None:
        self._max_gaps = max_gaps
        self._stale_doc_threshold_days = stale_doc_threshold_days
        self._items: list[KnowledgeGap] = []
        logger.info(
            "knowledge_gap.initialized",
            max_gaps=max_gaps,
            stale_doc_threshold_days=(stale_doc_threshold_days),
        )

    # -- record / get / list --

    def record_gap(
        self,
        service_name: str = "",
        gap_type: GapType = GapType.MISSING_RUNBOOK,
        area: KnowledgeArea = (KnowledgeArea.INCIDENT_RESPONSE),
        priority: GapPriority = GapPriority.MEDIUM,
        description: str = "",
        single_expert: str = "",
        doc_age_days: int = 0,
        **kw: Any,
    ) -> KnowledgeGap:
        """Record a knowledge gap."""
        gap = KnowledgeGap(
            service_name=service_name,
            gap_type=gap_type,
            area=area,
            priority=priority,
            description=description,
            single_expert=single_expert,
            doc_age_days=doc_age_days,
            **kw,
        )
        self._items.append(gap)
        if len(self._items) > self._max_gaps:
            self._items.pop(0)
        logger.info(
            "knowledge_gap.recorded",
            gap_id=gap.id,
            service_name=service_name,
            gap_type=gap_type,
        )
        return gap

    def get_gap(
        self,
        gap_id: str,
    ) -> KnowledgeGap | None:
        """Get a single gap by ID."""
        for item in self._items:
            if item.id == gap_id:
                return item
        return None

    def list_gaps(
        self,
        service_name: str | None = None,
        gap_type: GapType | None = None,
        limit: int = 50,
    ) -> list[KnowledgeGap]:
        """List gaps with optional filters."""
        results = list(self._items)
        if service_name is not None:
            results = [r for r in results if r.service_name == service_name]
        if gap_type is not None:
            results = [r for r in results if r.gap_type == gap_type]
        return results[-limit:]

    # -- domain operations --

    def resolve_gap(
        self,
        gap_id: str,
    ) -> KnowledgeGap | None:
        """Mark a knowledge gap as resolved."""
        gap = self.get_gap(gap_id)
        if gap is None:
            return None
        gap.is_resolved = True
        logger.info(
            "knowledge_gap.resolved",
            gap_id=gap_id,
        )
        return gap

    def calculate_coverage(
        self,
        service_name: str | None = None,
    ) -> KnowledgeCoverage:
        """Calculate knowledge coverage."""
        gaps = list(self._items)
        svc = service_name or "all"
        if service_name is not None:
            gaps = [g for g in gaps if g.service_name == service_name]
        total = len(gaps)
        resolved = sum(1 for g in gaps if g.is_resolved)
        critical = sum(1 for g in gaps if g.priority == GapPriority.CRITICAL and not g.is_resolved)
        coverage = 100.0
        if total > 0:
            coverage = round(resolved / total * 100, 2)
        return KnowledgeCoverage(
            service_name=svc,
            coverage_pct=coverage,
            gap_count=total,
            critical_gaps=critical,
        )

    def detect_tribal_knowledge_risks(
        self,
    ) -> list[dict[str, Any]]:
        """Detect services with tribal knowledge risk."""
        risks: list[dict[str, Any]] = []
        for g in self._items:
            if g.gap_type == GapType.TRIBAL_KNOWLEDGE and not g.is_resolved:
                risks.append(
                    {
                        "gap_id": g.id,
                        "service_name": g.service_name,
                        "single_expert": g.single_expert,
                        "priority": g.priority.value,
                    }
                )
        risks.sort(
            key=lambda x: {
                "critical": 0,
                "high": 1,
                "medium": 2,
                "low": 3,
                "informational": 4,
            }.get(x.get("priority", ""), 4),
        )
        return risks

    def identify_stale_documentation(
        self,
        max_age_days: int = 180,
    ) -> list[dict[str, Any]]:
        """Find gaps with stale documentation."""
        stale: list[dict[str, Any]] = []
        for g in self._items:
            if g.doc_age_days > max_age_days and not g.is_resolved:
                stale.append(
                    {
                        "gap_id": g.id,
                        "service_name": g.service_name,
                        "doc_age_days": g.doc_age_days,
                        "gap_type": g.gap_type.value,
                    }
                )
        stale.sort(
            key=lambda x: x.get("doc_age_days", 0),
            reverse=True,
        )
        return stale

    def rank_by_priority(
        self,
    ) -> list[dict[str, Any]]:
        """Rank unresolved gaps by priority."""
        priority_order = {
            GapPriority.CRITICAL: 0,
            GapPriority.HIGH: 1,
            GapPriority.MEDIUM: 2,
            GapPriority.LOW: 3,
            GapPriority.INFORMATIONAL: 4,
        }
        unresolved = [g for g in self._items if not g.is_resolved]
        unresolved.sort(
            key=lambda g: priority_order.get(g.priority, 4),
        )
        return [
            {
                "gap_id": g.id,
                "service_name": g.service_name,
                "gap_type": g.gap_type.value,
                "priority": g.priority.value,
                "description": g.description,
            }
            for g in unresolved
        ]

    # -- report --

    def generate_knowledge_report(
        self,
    ) -> KnowledgeReport:
        """Generate a comprehensive knowledge report."""
        by_type: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        by_area: dict[str, int] = {}
        resolved = 0
        for g in self._items:
            t = g.gap_type.value
            by_type[t] = by_type.get(t, 0) + 1
            p = g.priority.value
            by_priority[p] = by_priority.get(p, 0) + 1
            a = g.area.value
            by_area[a] = by_area.get(a, 0) + 1
            if g.is_resolved:
                resolved += 1
        tribal = self.detect_tribal_knowledge_risks()
        tribal_ids = [r.get("gap_id", "") for r in tribal]
        total = len(self._items)
        coverage_pct = 100.0
        if total > 0:
            coverage_pct = round(resolved / total * 100, 2)
        recs = self._build_recommendations(
            total,
            resolved,
            len(tribal_ids),
        )
        return KnowledgeReport(
            total_gaps=total,
            resolved_gaps=resolved,
            coverage_pct=coverage_pct,
            by_type=by_type,
            by_priority=by_priority,
            by_area=by_area,
            tribal_knowledge_risks=tribal_ids,
            recommendations=recs,
        )

    # -- housekeeping --

    def clear_data(self) -> int:
        """Clear all data. Returns records cleared."""
        count = len(self._items)
        self._items.clear()
        logger.info(
            "knowledge_gap.cleared",
            count=count,
        )
        return count

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        type_dist: dict[str, int] = {}
        for g in self._items:
            key = g.gap_type.value
            type_dist[key] = type_dist.get(key, 0) + 1
        return {
            "total_gaps": len(self._items),
            "max_gaps": self._max_gaps,
            "stale_doc_threshold_days": (self._stale_doc_threshold_days),
            "type_distribution": type_dist,
        }

    # -- internal helpers --

    def _build_recommendations(
        self,
        total: int,
        resolved: int,
        tribal_risks: int,
    ) -> list[str]:
        recs: list[str] = []
        if tribal_risks > 0:
            recs.append(f"{tribal_risks} tribal knowledge risk(s) detected")
        if total == 0:
            recs.append("No knowledge gaps tracked")
        if total > 0 and resolved < total:
            pending = total - resolved
            recs.append(f"{pending} knowledge gap(s) still unresolved")
        if not recs:
            recs.append("Knowledge coverage within acceptable limits")
        return recs
