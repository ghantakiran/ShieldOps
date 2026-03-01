"""Compliance Evidence Consolidator — consolidate evidence for audit preparation."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class EvidenceStatus(StrEnum):
    COLLECTED = "collected"
    VERIFIED = "verified"
    CONSOLIDATED = "consolidated"
    EXPIRED = "expired"
    MISSING = "missing"


class EvidenceSource(StrEnum):
    AUTOMATED = "automated"
    MANUAL = "manual"
    THIRD_PARTY = "third_party"
    INTERNAL_AUDIT = "internal_audit"
    CONTINUOUS_MONITORING = "continuous_monitoring"


class ConsolidationLevel(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    INSUFFICIENT = "insufficient"
    NONE = "none"


# --- Models ---


class ConsolidationRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    framework: str = ""
    evidence_status: EvidenceStatus = EvidenceStatus.COLLECTED
    source: EvidenceSource = EvidenceSource.AUTOMATED
    consolidation_level: ConsolidationLevel = ConsolidationLevel.PARTIAL
    completeness_pct: float = 0.0
    team: str = ""
    details: str = ""
    created_at: float = Field(default_factory=time.time)


class ConsolidationRule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    framework_pattern: str = ""
    evidence_status: EvidenceStatus = EvidenceStatus.COLLECTED
    source: EvidenceSource = EvidenceSource.AUTOMATED
    min_completeness_pct: float = 0.0
    reason: str = ""
    created_at: float = Field(default_factory=time.time)


class EvidenceConsolidationReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_rules: int = 0
    missing_count: int = 0
    avg_completeness_pct: float = 0.0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    by_level: dict[str, int] = Field(default_factory=dict)
    incomplete_frameworks: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class ComplianceEvidenceConsolidator:
    """Consolidate evidence from multiple sources for audit preparation."""

    def __init__(
        self,
        max_records: int = 200000,
        min_completeness_pct: float = 90.0,
    ) -> None:
        self._max_records = max_records
        self._min_completeness_pct = min_completeness_pct
        self._records: list[ConsolidationRecord] = []
        self._rules: list[ConsolidationRule] = []
        logger.info(
            "evidence_consolidator.initialized",
            max_records=max_records,
            min_completeness_pct=min_completeness_pct,
        )

    # -- record / get / list ------------------------------------------------

    def record_consolidation(
        self,
        framework: str,
        evidence_status: EvidenceStatus = EvidenceStatus.COLLECTED,
        source: EvidenceSource = EvidenceSource.AUTOMATED,
        consolidation_level: ConsolidationLevel = (ConsolidationLevel.PARTIAL),
        completeness_pct: float = 0.0,
        team: str = "",
        details: str = "",
    ) -> ConsolidationRecord:
        record = ConsolidationRecord(
            framework=framework,
            evidence_status=evidence_status,
            source=source,
            consolidation_level=consolidation_level,
            completeness_pct=completeness_pct,
            team=team,
            details=details,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "evidence_consolidator.consolidation_recorded",
            record_id=record.id,
            framework=framework,
            evidence_status=evidence_status.value,
            source=source.value,
        )
        return record

    def get_consolidation(self, record_id: str) -> ConsolidationRecord | None:
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_consolidations(
        self,
        status: EvidenceStatus | None = None,
        source: EvidenceSource | None = None,
        team: str | None = None,
        limit: int = 50,
    ) -> list[ConsolidationRecord]:
        results = list(self._records)
        if status is not None:
            results = [r for r in results if r.evidence_status == status]
        if source is not None:
            results = [r for r in results if r.source == source]
        if team is not None:
            results = [r for r in results if r.team == team]
        return results[-limit:]

    def add_rule(
        self,
        framework_pattern: str,
        evidence_status: EvidenceStatus = EvidenceStatus.COLLECTED,
        source: EvidenceSource = EvidenceSource.AUTOMATED,
        min_completeness_pct: float = 0.0,
        reason: str = "",
    ) -> ConsolidationRule:
        rule = ConsolidationRule(
            framework_pattern=framework_pattern,
            evidence_status=evidence_status,
            source=source,
            min_completeness_pct=min_completeness_pct,
            reason=reason,
        )
        self._rules.append(rule)
        if len(self._rules) > self._max_records:
            self._rules = self._rules[-self._max_records :]
        logger.info(
            "evidence_consolidator.rule_added",
            framework_pattern=framework_pattern,
            evidence_status=evidence_status.value,
            min_completeness_pct=min_completeness_pct,
        )
        return rule

    # -- domain operations --------------------------------------------------

    def analyze_consolidation_coverage(
        self,
    ) -> dict[str, Any]:
        """Group by status; return count and avg completeness."""
        status_data: dict[str, list[float]] = {}
        for r in self._records:
            key = r.evidence_status.value
            status_data.setdefault(key, []).append(r.completeness_pct)
        result: dict[str, Any] = {}
        for status, pcts in status_data.items():
            result[status] = {
                "count": len(pcts),
                "avg_completeness": round(sum(pcts) / len(pcts), 2),
            }
        return result

    def identify_missing_evidence(
        self,
    ) -> list[dict[str, Any]]:
        """Return records where status is MISSING."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.evidence_status == EvidenceStatus.MISSING:
                results.append(
                    {
                        "record_id": r.id,
                        "framework": r.framework,
                        "evidence_status": (r.evidence_status.value),
                        "source": r.source.value,
                        "completeness_pct": r.completeness_pct,
                        "team": r.team,
                    }
                )
        results.sort(
            key=lambda x: x["completeness_pct"],
            reverse=False,
        )
        return results

    def rank_by_completeness(self) -> list[dict[str, Any]]:
        """Group by framework, avg completeness, sort asc."""
        fw_scores: dict[str, list[float]] = {}
        for r in self._records:
            fw_scores.setdefault(r.framework, []).append(r.completeness_pct)
        results: list[dict[str, Any]] = []
        for fw, pcts in fw_scores.items():
            results.append(
                {
                    "framework": fw,
                    "avg_completeness": round(sum(pcts) / len(pcts), 2),
                    "record_count": len(pcts),
                }
            )
        results.sort(key=lambda x: x["avg_completeness"])
        return results

    def detect_consolidation_trends(
        self,
    ) -> dict[str, Any]:
        """Split-half comparison on completeness; delta threshold 5.0."""
        if len(self._records) < 2:
            return {"trend": "insufficient_data", "delta": 0.0}
        scores = [r.completeness_pct for r in self._records]
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]
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

    def generate_report(self) -> EvidenceConsolidationReport:
        by_status: dict[str, int] = {}
        by_source: dict[str, int] = {}
        by_level: dict[str, int] = {}
        for r in self._records:
            by_status[r.evidence_status.value] = by_status.get(r.evidence_status.value, 0) + 1
            by_source[r.source.value] = by_source.get(r.source.value, 0) + 1
            by_level[r.consolidation_level.value] = by_level.get(r.consolidation_level.value, 0) + 1
        missing_count = sum(1 for r in self._records if r.evidence_status == EvidenceStatus.MISSING)
        avg_completeness = (
            round(
                sum(r.completeness_pct for r in self._records) / len(self._records),
                2,
            )
            if self._records
            else 0.0
        )
        missing = self.identify_missing_evidence()
        incomplete_frameworks = [m["framework"] for m in missing]
        recs: list[str] = []
        if missing:
            recs.append(f"{len(missing)} missing evidence item(s) — collect immediately")
        low_comp = sum(1 for r in self._records if r.completeness_pct < self._min_completeness_pct)
        if low_comp > 0:
            recs.append(
                f"{low_comp} record(s) below completeness threshold ({self._min_completeness_pct}%)"
            )
        if not recs:
            recs.append("Evidence completeness levels are healthy")
        return EvidenceConsolidationReport(
            total_records=len(self._records),
            total_rules=len(self._rules),
            missing_count=missing_count,
            avg_completeness_pct=avg_completeness,
            by_status=by_status,
            by_source=by_source,
            by_level=by_level,
            incomplete_frameworks=incomplete_frameworks,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._rules.clear()
        logger.info("evidence_consolidator.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        status_dist: dict[str, int] = {}
        for r in self._records:
            key = r.evidence_status.value
            status_dist[key] = status_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_rules": len(self._rules),
            "min_completeness_pct": self._min_completeness_pct,
            "status_distribution": status_dist,
            "unique_teams": len({r.team for r in self._records}),
            "unique_frameworks": len({r.framework for r in self._records}),
        }
