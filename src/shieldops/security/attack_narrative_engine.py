"""Attack Narrative Engine
construct attack stories, identify narrative gaps,
score story confidence."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class NarrativePhase(StrEnum):
    INITIAL_ACCESS = "initial_access"
    EXECUTION = "execution"
    PERSISTENCE = "persistence"
    EXFILTRATION = "exfiltration"


class EvidenceStrength(StrEnum):
    CONCLUSIVE = "conclusive"
    STRONG = "strong"
    MODERATE = "moderate"
    CIRCUMSTANTIAL = "circumstantial"


class StoryCompleteness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FRAGMENTARY = "fragmentary"
    UNKNOWN = "unknown"


# --- Models ---


class NarrativeRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    narrative_id: str = ""
    phase: NarrativePhase = NarrativePhase.INITIAL_ACCESS
    evidence: EvidenceStrength = EvidenceStrength.MODERATE
    completeness: StoryCompleteness = StoryCompleteness.PARTIAL
    confidence_score: float = 0.0
    event_count: int = 0
    service: str = ""
    team: str = ""
    created_at: float = Field(default_factory=time.time)


class NarrativeAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    narrative_id: str = ""
    phase: NarrativePhase = NarrativePhase.INITIAL_ACCESS
    analysis_score: float = 0.0
    gap_count: int = 0
    story_confidence: float = 0.0
    description: str = ""
    created_at: float = Field(default_factory=time.time)


class NarrativeReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    total_records: int = 0
    total_analyses: int = 0
    avg_confidence: float = 0.0
    avg_events: float = 0.0
    by_phase: dict[str, int] = Field(default_factory=dict)
    by_evidence: dict[str, int] = Field(default_factory=dict)
    by_completeness: dict[str, int] = Field(default_factory=dict)
    incomplete_narratives: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)
    created_at: float = Field(default_factory=time.time)


# --- Engine ---


class AttackNarrativeEngine:
    """Construct attack stories, identify narrative
    gaps, score story confidence."""

    def __init__(
        self,
        max_records: int = 200000,
        confidence_threshold: float = 0.7,
    ) -> None:
        self._max_records = max_records
        self._confidence_threshold = confidence_threshold
        self._records: list[NarrativeRecord] = []
        self._analyses: list[NarrativeAnalysis] = []
        logger.info(
            "attack_narrative_engine.initialized",
            max_records=max_records,
            confidence_threshold=confidence_threshold,
        )

    def add_record(
        self,
        narrative_id: str,
        phase: NarrativePhase = (NarrativePhase.INITIAL_ACCESS),
        evidence: EvidenceStrength = (EvidenceStrength.MODERATE),
        completeness: StoryCompleteness = (StoryCompleteness.PARTIAL),
        confidence_score: float = 0.0,
        event_count: int = 0,
        service: str = "",
        team: str = "",
    ) -> NarrativeRecord:
        record = NarrativeRecord(
            narrative_id=narrative_id,
            phase=phase,
            evidence=evidence,
            completeness=completeness,
            confidence_score=confidence_score,
            event_count=event_count,
            service=service,
            team=team,
        )
        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records :]
        logger.info(
            "attack_narrative_engine.record_added",
            record_id=record.id,
            narrative_id=narrative_id,
        )
        return record

    def process(self, key: str) -> NarrativeAnalysis | None:
        rec = None
        for r in self._records:
            if r.id == key:
                rec = r
                break
        if rec is None:
            return None
        ev_weight = {
            "conclusive": 1.0,
            "strong": 0.8,
            "moderate": 0.6,
            "circumstantial": 0.3,
        }
        w = ev_weight.get(rec.evidence.value, 0.5)
        score = round(rec.confidence_score * w * 100, 2)
        gap = (
            0
            if rec.completeness == StoryCompleteness.COMPLETE
            else 1
            if rec.completeness == StoryCompleteness.PARTIAL
            else 2
        )
        analysis = NarrativeAnalysis(
            narrative_id=rec.narrative_id,
            phase=rec.phase,
            analysis_score=score,
            gap_count=gap,
            story_confidence=round(rec.confidence_score * w, 4),
            description=(f"Narrative {rec.narrative_id} confidence {score:.1f}%"),
        )
        self._analyses.append(analysis)
        if len(self._analyses) > self._max_records:
            self._analyses = self._analyses[-self._max_records :]
        return analysis

    def generate_report(self) -> NarrativeReport:
        by_ph: dict[str, int] = {}
        by_ev: dict[str, int] = {}
        by_cm: dict[str, int] = {}
        confs: list[float] = []
        evts: list[int] = []
        for r in self._records:
            p = r.phase.value
            by_ph[p] = by_ph.get(p, 0) + 1
            e = r.evidence.value
            by_ev[e] = by_ev.get(e, 0) + 1
            c = r.completeness.value
            by_cm[c] = by_cm.get(c, 0) + 1
            confs.append(r.confidence_score)
            evts.append(r.event_count)
        avg_c = round(sum(confs) / len(confs), 4) if confs else 0.0
        avg_e = round(sum(evts) / len(evts), 2) if evts else 0.0
        incomplete = [
            r.narrative_id for r in self._records if r.completeness != StoryCompleteness.COMPLETE
        ][:5]
        recs: list[str] = []
        if incomplete:
            recs.append(f"{len(incomplete)} narratives incomplete")
        if not recs:
            recs.append("Attack narratives complete")
        return NarrativeReport(
            total_records=len(self._records),
            total_analyses=len(self._analyses),
            avg_confidence=avg_c,
            avg_events=avg_e,
            by_phase=by_ph,
            by_evidence=by_ev,
            by_completeness=by_cm,
            incomplete_narratives=incomplete,
            recommendations=recs,
        )

    def get_stats(self) -> dict[str, Any]:
        ph_dist: dict[str, int] = {}
        for r in self._records:
            k = r.phase.value
            ph_dist[k] = ph_dist.get(k, 0) + 1
        return {
            "total_records": len(self._records),
            "total_analyses": len(self._analyses),
            "confidence_threshold": (self._confidence_threshold),
            "phase_distribution": ph_dist,
        }

    def clear_data(self) -> dict[str, str]:
        self._records.clear()
        self._analyses.clear()
        logger.info("attack_narrative_engine.cleared")
        return {"status": "cleared"}

    # -- domain methods ---

    def construct_attack_story(
        self,
    ) -> list[dict[str, Any]]:
        """Construct attack story grouped by phase."""
        phase_data: dict[str, list[dict[str, Any]]] = {}
        for r in self._records:
            k = r.phase.value
            phase_data.setdefault(k, []).append(
                {
                    "narrative_id": r.narrative_id,
                    "evidence": r.evidence.value,
                    "completeness": r.completeness.value,
                    "confidence": r.confidence_score,
                    "events": r.event_count,
                }
            )
        results: list[dict[str, Any]] = []
        phase_order = [
            "initial_access",
            "execution",
            "persistence",
            "exfiltration",
        ]
        for ph in phase_order:
            if ph in phase_data:
                items = phase_data[ph]
                avg_conf = round(
                    sum(i["confidence"] for i in items) / len(items),
                    4,
                )
                results.append(
                    {
                        "phase": ph,
                        "event_count": len(items),
                        "avg_confidence": avg_conf,
                        "entries": items[:10],
                    }
                )
        return results

    def identify_narrative_gaps(
        self,
    ) -> list[dict[str, Any]]:
        """Identify narrative gaps: low confidence
        or incomplete stories."""
        results: list[dict[str, Any]] = []
        for r in self._records:
            if r.confidence_score < self._confidence_threshold or r.completeness in (
                StoryCompleteness.FRAGMENTARY,
                StoryCompleteness.UNKNOWN,
            ):
                results.append(
                    {
                        "narrative_id": r.narrative_id,
                        "phase": r.phase.value,
                        "confidence": r.confidence_score,
                        "completeness": (r.completeness.value),
                        "evidence": r.evidence.value,
                    }
                )
        results.sort(
            key=lambda x: x["confidence"],
        )
        return results

    def score_story_confidence(
        self,
    ) -> dict[str, Any]:
        """Score overall story confidence
        by evidence strength."""
        if not self._records:
            return {
                "overall_confidence": 0.0,
                "by_evidence": {},
            }
        ev_scores: dict[str, list[float]] = {}
        for r in self._records:
            k = r.evidence.value
            ev_scores.setdefault(k, []).append(r.confidence_score)
        by_ev: dict[str, float] = {}
        for e, scores in ev_scores.items():
            by_ev[e] = round(sum(scores) / len(scores), 4)
        all_s = [r.confidence_score for r in self._records]
        return {
            "overall_confidence": round(sum(all_s) / len(all_s), 4),
            "by_evidence": by_ev,
        }
