"""Incident Handoff Tracker — track handoff quality between responders during incidents."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class HandoffType(StrEnum):
    SHIFT_CHANGE = "shift_change"
    ESCALATION = "escalation"
    CROSS_TEAM = "cross_team"
    SPECIALIZATION = "specialization"
    MANAGEMENT = "management"


class HandoffQuality(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    ADEQUATE = "adequate"
    POOR = "poor"
    FAILED = "failed"


class InformationCompleteness(StrEnum):
    FULL_CONTEXT = "full_context"
    MOSTLY_COMPLETE = "mostly_complete"
    PARTIAL = "partial"
    MINIMAL = "minimal"
    NO_CONTEXT = "no_context"


# --- Models ---


class HandoffRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str = ""
    from_responder: str = ""
    to_responder: str = ""
    handoff_type: HandoffType = HandoffType.SHIFT_CHANGE
    quality: HandoffQuality = HandoffQuality.ADEQUATE
    completeness: InformationCompleteness = InformationCompleteness.PARTIAL
    delay_minutes: float = 0.0
    notes_provided: bool = False
    runbook_attached: bool = False
    quality_score: float = 0.5
    created_at: float = Field(default_factory=time.time)


class HandoffPattern(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pattern_name: str = ""
    handoff_type: HandoffType = HandoffType.SHIFT_CHANGE
    frequency: int = 0
    avg_quality_score: float = 0.0
    common_issues: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class HandoffReport(BaseModel):
    total_handoffs: int = 0
    avg_quality_score: float = 0.0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_quality: dict[str, int] = Field(default_factory=dict)
    problem_pairs: list[str] = Field(default_factory=list)
    avg_delay_minutes: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Tracker ---


class IncidentHandoffTracker:
    """Track handoff quality between responders during incidents."""

    def __init__(
        self,
        max_records: int = 200000,
        quality_threshold: float = 0.7,
    ) -> None:
        self._max_records = max_records
        self._quality_threshold = quality_threshold
        self._records: list[HandoffRecord] = []
        self._patterns: list[HandoffPattern] = []
        logger.info(
            "handoff_tracker.initialized",
            max_records=max_records,
            quality_threshold=quality_threshold,
        )

    # -- record / get / list -----------------------------------------

    def record_handoff(
        self,
        incident_id: str,
        from_responder: str,
        to_responder: str,
        handoff_type: HandoffType = HandoffType.SHIFT_CHANGE,
        delay_minutes: float = 0.0,
        notes_provided: bool = False,
        runbook_attached: bool = False,
    ) -> HandoffRecord:
        """Record a handoff and auto-compute quality metrics."""
        score = self._compute_quality_score(
            delay_minutes,
            notes_provided,
            runbook_attached,
        )
        quality = self._score_to_quality(score)
        completeness = self._score_to_completeness(score)
        record = HandoffRecord(
            incident_id=incident_id,
            from_responder=from_responder,
            to_responder=to_responder,
            handoff_type=handoff_type,
            quality=quality,
            completeness=completeness,
            delay_minutes=delay_minutes,
            notes_provided=notes_provided,
            runbook_attached=runbook_attached,
            quality_score=score,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "handoff_tracker.handoff_recorded",
            record_id=record.id,
            incident_id=incident_id,
            quality=quality.value,
        )
        return record

    def get_handoff(self, record_id: str) -> HandoffRecord | None:
        """Get a single handoff record by ID."""
        for r in self._records:
            if r.id == record_id:
                return r
        return None

    def list_handoffs(
        self,
        incident_id: str | None = None,
        handoff_type: HandoffType | None = None,
        limit: int = 50,
    ) -> list[HandoffRecord]:
        """List handoff records with optional filters."""
        results = list(self._records)
        if incident_id is not None:
            results = [r for r in results if r.incident_id == incident_id]
        if handoff_type is not None:
            results = [r for r in results if r.handoff_type == handoff_type]
        return results[-limit:]

    # -- domain operations -------------------------------------------

    def assess_quality(self, record_id: str) -> dict[str, Any]:
        """Re-assess quality for a specific handoff record."""
        rec = self.get_handoff(record_id)
        if rec is None:
            return {"record_id": record_id, "error": "Record not found"}
        score = self._compute_quality_score(
            rec.delay_minutes,
            rec.notes_provided,
            rec.runbook_attached,
        )
        quality = self._score_to_quality(score)
        completeness = self._score_to_completeness(score)
        rec.quality_score = score
        rec.quality = quality
        rec.completeness = completeness
        logger.info(
            "handoff_tracker.quality_assessed",
            record_id=record_id,
            score=score,
            quality=quality.value,
        )
        return {
            "record_id": record_id,
            "quality_score": score,
            "quality": quality.value,
            "completeness": completeness.value,
            "meets_threshold": score >= self._quality_threshold,
        }

    def detect_patterns(self) -> list[HandoffPattern]:
        """Analyze all records for patterns by handoff type."""
        by_type: dict[str, list[HandoffRecord]] = {}
        for r in self._records:
            by_type.setdefault(r.handoff_type.value, []).append(r)
        new_patterns: list[HandoffPattern] = []
        for type_val, records in sorted(by_type.items()):
            scores = [r.quality_score for r in records]
            avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
            issues: list[str] = []
            low_quality = [r for r in records if r.quality_score < self._quality_threshold]
            if low_quality:
                issues.append(f"{len(low_quality)} below quality threshold")
            no_notes = [r for r in records if not r.notes_provided]
            if no_notes:
                issues.append(f"{len(no_notes)} without notes")
            no_runbook = [r for r in records if not r.runbook_attached]
            if no_runbook:
                issues.append(f"{len(no_runbook)} without runbook")
            pattern = HandoffPattern(
                pattern_name=type_val,
                handoff_type=HandoffType(type_val),
                frequency=len(records),
                avg_quality_score=avg_score,
                common_issues=issues,
            )
            new_patterns.append(pattern)
        self._patterns = new_patterns
        logger.info(
            "handoff_tracker.patterns_detected",
            count=len(new_patterns),
        )
        return new_patterns

    def identify_problem_pairs(self) -> list[dict[str, Any]]:
        """Find responder pairs with consistently low quality."""
        pair_scores: dict[str, list[float]] = {}
        for r in self._records:
            key = f"{r.from_responder}->{r.to_responder}"
            pair_scores.setdefault(key, []).append(r.quality_score)
        results: list[dict[str, Any]] = []
        for pair, scores in pair_scores.items():
            avg = round(sum(scores) / len(scores), 4)
            if avg < self._quality_threshold and len(scores) >= 2:
                results.append(
                    {
                        "pair": pair,
                        "handoff_count": len(scores),
                        "avg_quality_score": avg,
                        "below_threshold": True,
                    }
                )
        results.sort(key=lambda x: x["avg_quality_score"])
        return results

    def calculate_avg_delay(self) -> dict[str, Any]:
        """Calculate average delay by handoff type."""
        by_type: dict[str, list[float]] = {}
        for r in self._records:
            by_type.setdefault(r.handoff_type.value, []).append(r.delay_minutes)
        result: dict[str, float] = {}
        for type_val, delays in by_type.items():
            result[type_val] = round(sum(delays) / len(delays), 2) if delays else 0.0
        all_delays = [r.delay_minutes for r in self._records]
        overall = round(sum(all_delays) / len(all_delays), 2) if all_delays else 0.0
        return {
            "overall_avg_delay_minutes": overall,
            "by_type": result,
            "total_handoffs": len(self._records),
        }

    def rank_by_information_loss(self) -> list[dict[str, Any]]:
        """Rank handoffs by information loss (low completeness)."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            results.append(
                {
                    "record_id": r.id,
                    "incident_id": r.incident_id,
                    "from_responder": r.from_responder,
                    "to_responder": r.to_responder,
                    "completeness": r.completeness.value,
                    "quality_score": r.quality_score,
                    "notes_provided": r.notes_provided,
                    "runbook_attached": r.runbook_attached,
                }
            )
        # Sort by quality_score ascending (worst first)
        results.sort(key=lambda x: x["quality_score"])
        return results

    # -- report / stats ----------------------------------------------

    def generate_handoff_report(self) -> HandoffReport:
        """Generate a comprehensive handoff quality report."""
        by_type: dict[str, int] = {}
        by_quality: dict[str, int] = {}
        scores: list[float] = []
        delays: list[float] = []
        for r in self._records:
            by_type[r.handoff_type.value] = by_type.get(r.handoff_type.value, 0) + 1
            by_quality[r.quality.value] = by_quality.get(r.quality.value, 0) + 1
            scores.append(r.quality_score)
            delays.append(r.delay_minutes)
        avg_score = round(sum(scores) / len(scores), 4) if scores else 0.0
        avg_delay = round(sum(delays) / len(delays), 2) if delays else 0.0
        problem_pairs = self.identify_problem_pairs()
        pair_names = [p["pair"] for p in problem_pairs[:5]]
        recs = self._build_recommendations(by_quality, avg_score, problem_pairs)
        return HandoffReport(
            total_handoffs=len(self._records),
            avg_quality_score=avg_score,
            by_type=by_type,
            by_quality=by_quality,
            problem_pairs=pair_names,
            avg_delay_minutes=avg_delay,
            recommendations=recs,
        )

    def clear_data(self) -> dict[str, str]:
        """Clear all stored records and patterns."""
        self._records.clear()
        self._patterns.clear()
        logger.info("handoff_tracker.cleared")
        return {"status": "cleared"}

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        quality_dist: dict[str, int] = {}
        for r in self._records:
            key = r.quality.value
            quality_dist[key] = quality_dist.get(key, 0) + 1
        return {
            "total_records": len(self._records),
            "total_patterns": len(self._patterns),
            "quality_threshold": self._quality_threshold,
            "quality_distribution": quality_dist,
            "unique_responders": len(
                {r.from_responder for r in self._records} | {r.to_responder for r in self._records}
            ),
        }

    # -- internal helpers --------------------------------------------

    def _compute_quality_score(
        self,
        delay_minutes: float,
        notes_provided: bool,
        runbook_attached: bool,
    ) -> float:
        """Compute quality score from handoff attributes."""
        score = 0.5
        if notes_provided:
            score += 0.2
        if runbook_attached:
            score += 0.15
        if delay_minutes < 5:
            score += 0.15
        elif delay_minutes < 15:
            score += 0.1
        elif delay_minutes < 30:
            score += 0.05
        else:
            score -= 0.1
        return round(min(max(score, 0.0), 1.0), 4)

    def _score_to_quality(self, score: float) -> HandoffQuality:
        """Map quality score to quality enum."""
        if score >= 0.9:
            return HandoffQuality.EXCELLENT
        if score >= 0.7:
            return HandoffQuality.GOOD
        if score >= 0.5:
            return HandoffQuality.ADEQUATE
        if score >= 0.3:
            return HandoffQuality.POOR
        return HandoffQuality.FAILED

    def _score_to_completeness(self, score: float) -> InformationCompleteness:
        """Map quality score to completeness enum."""
        if score >= 0.9:
            return InformationCompleteness.FULL_CONTEXT
        if score >= 0.7:
            return InformationCompleteness.MOSTLY_COMPLETE
        if score >= 0.5:
            return InformationCompleteness.PARTIAL
        if score >= 0.3:
            return InformationCompleteness.MINIMAL
        return InformationCompleteness.NO_CONTEXT

    def _build_recommendations(
        self,
        by_quality: dict[str, int],
        avg_score: float,
        problem_pairs: list[dict[str, Any]],
    ) -> list[str]:
        """Build recommendations from handoff analysis."""
        recs: list[str] = []
        poor = by_quality.get(HandoffQuality.POOR.value, 0)
        failed = by_quality.get(HandoffQuality.FAILED.value, 0)
        if failed > 0:
            recs.append(f"{failed} handoff(s) failed — implement mandatory checklists")
        if poor > 0:
            recs.append(f"{poor} poor-quality handoff(s) — provide handoff training")
        if problem_pairs:
            recs.append(f"{len(problem_pairs)} responder pair(s) with consistently low quality")
        if avg_score < self._quality_threshold:
            recs.append(
                f"Average quality score {avg_score:.2f} below {self._quality_threshold} threshold"
            )
        if not recs:
            recs.append("Handoff quality is within acceptable standards")
        return recs
