"""Runbook recommender for incident-driven playbook selection."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# ── Enums ────────────────────────────────────────────────────────────────────


class RecommendationReason(StrEnum):
    """Why a runbook was recommended."""

    SYMPTOM_MATCH = "symptom_match"
    HISTORICAL_SUCCESS = "historical_success"
    SERVICE_MATCH = "service_match"
    SIMILAR_INCIDENT = "similar_incident"


class RecommendationStatus(StrEnum):
    """Lifecycle status of a recommendation."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXECUTED = "executed"


# ── Models ───────────────────────────────────────────────────────────────────


class RunbookCandidate(BaseModel):
    """A scored runbook recommendation for an incident."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runbook_id: str = ""
    runbook_name: str = ""
    incident_id: str = ""
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    status: RecommendationStatus = RecommendationStatus.PENDING
    recommended_at: float = Field(default_factory=time.time)


class FeedbackRecord(BaseModel):
    """Outcome feedback for a recommendation."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    candidate_id: str = ""
    outcome: str = ""
    success: bool = False
    execution_time_seconds: float = 0.0
    recorded_at: float = Field(default_factory=time.time)


class RunbookProfile(BaseModel):
    """Profile describing a runbook and its track record."""

    runbook_id: str = ""
    name: str = ""
    symptoms: list[str] = Field(default_factory=list)
    services: list[str] = Field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    avg_execution_time: float = 0.0


# ── Engine ───────────────────────────────────────────────────────────────────


class RunbookRecommender:
    """Recommends runbooks based on symptoms and history."""

    def __init__(
        self,
        max_profiles: int = 500,
        max_candidates: int = 50000,
        min_score: float = 0.3,
    ) -> None:
        self.max_profiles = max_profiles
        self.max_candidates = max_candidates
        self.min_score = min_score

        self._profiles: dict[str, RunbookProfile] = {}
        self._candidates: dict[str, RunbookCandidate] = {}
        self._feedback: dict[str, FeedbackRecord] = {}

        logger.info(
            "runbook_recommender.init",
            max_profiles=max_profiles,
            max_candidates=max_candidates,
            min_score=min_score,
        )

    # ── Profile management ───────────────────────────────────────────

    def register_runbook(
        self,
        runbook_id: str,
        name: str,
        symptoms: list[str] | None = None,
        services: list[str] | None = None,
    ) -> RunbookProfile:
        """Register a runbook profile for recommendation."""
        if len(self._profiles) >= self.max_profiles:
            oldest = next(iter(self._profiles))
            del self._profiles[oldest]

        profile = RunbookProfile(
            runbook_id=runbook_id,
            name=name,
            symptoms=symptoms or [],
            services=services or [],
        )
        self._profiles[runbook_id] = profile
        logger.info(
            "runbook_recommender.register",
            runbook_id=runbook_id,
            name=name,
        )
        return profile

    def get_profile(self, runbook_id: str) -> RunbookProfile | None:
        """Get a runbook profile by ID."""
        return self._profiles.get(runbook_id)

    def list_profiles(self) -> list[RunbookProfile]:
        """List all registered runbook profiles."""
        return list(self._profiles.values())

    # ── Recommendation ───────────────────────────────────────────────

    def recommend(
        self,
        incident_id: str,
        symptoms: list[str],
        service: str | None = None,
        limit: int = 5,
    ) -> list[RunbookCandidate]:
        """Score and recommend runbooks for an incident."""
        candidates: list[RunbookCandidate] = []

        for profile in self._profiles.values():
            score = 0.0
            reasons: list[str] = []

            # Symptom matching: +0.3 per match
            symptom_set = set(profile.symptoms)
            for s in symptoms:
                if s in symptom_set:
                    score += 0.3
                    if RecommendationReason.SYMPTOM_MATCH not in reasons:
                        reasons.append(RecommendationReason.SYMPTOM_MATCH)

            # Service matching: +0.2
            if service and service in profile.services:
                score += 0.2
                reasons.append(RecommendationReason.SERVICE_MATCH)

            # Historical success: +0.1 * success_rate
            total = profile.success_count + profile.failure_count
            if total > 0:
                success_rate = profile.success_count / total
                score += 0.1 * success_rate
                reasons.append(RecommendationReason.HISTORICAL_SUCCESS)

            if score < self.min_score:
                continue

            candidate = RunbookCandidate(
                runbook_id=profile.runbook_id,
                runbook_name=profile.name,
                incident_id=incident_id,
                score=round(score, 4),
                reasons=reasons,
            )
            candidates.append(candidate)

        candidates.sort(key=lambda c: c.score, reverse=True)
        candidates = candidates[:limit]

        for c in candidates:
            if len(self._candidates) >= self.max_candidates:
                oldest = next(iter(self._candidates))
                del self._candidates[oldest]
            self._candidates[c.id] = c

        logger.info(
            "runbook_recommender.recommend",
            incident_id=incident_id,
            candidates=len(candidates),
        )
        return candidates

    # ── Candidate lifecycle ──────────────────────────────────────────

    def accept_recommendation(self, candidate_id: str) -> RunbookCandidate | None:
        """Mark a recommendation as accepted."""
        candidate = self._candidates.get(candidate_id)
        if candidate is None:
            return None
        candidate.status = RecommendationStatus.ACCEPTED
        logger.info("runbook_recommender.accept", candidate_id=candidate_id)
        return candidate

    def reject_recommendation(self, candidate_id: str) -> RunbookCandidate | None:
        """Mark a recommendation as rejected."""
        candidate = self._candidates.get(candidate_id)
        if candidate is None:
            return None
        candidate.status = RecommendationStatus.REJECTED
        logger.info("runbook_recommender.reject", candidate_id=candidate_id)
        return candidate

    def record_feedback(
        self,
        candidate_id: str,
        success: bool,
        outcome: str = "",
        execution_time: float = 0.0,
    ) -> FeedbackRecord:
        """Record execution feedback and update profile stats."""
        candidate = self._candidates.get(candidate_id)
        if candidate is not None:
            candidate.status = RecommendationStatus.EXECUTED
            profile = self._profiles.get(candidate.runbook_id)
            if profile is not None:
                if success:
                    profile.success_count += 1
                else:
                    profile.failure_count += 1
                total = profile.success_count + profile.failure_count
                if total > 0 and execution_time > 0:
                    prev_total = total - 1
                    profile.avg_execution_time = (
                        profile.avg_execution_time * prev_total + execution_time
                    ) / total

        record = FeedbackRecord(
            candidate_id=candidate_id,
            outcome=outcome,
            success=success,
            execution_time_seconds=execution_time,
        )
        self._feedback[record.id] = record
        logger.info(
            "runbook_recommender.feedback",
            candidate_id=candidate_id,
            success=success,
        )
        return record

    def get_candidate(self, candidate_id: str) -> RunbookCandidate | None:
        """Get a recommendation candidate by ID."""
        return self._candidates.get(candidate_id)

    def list_candidates(
        self,
        incident_id: str | None = None,
        status: RecommendationStatus | None = None,
    ) -> list[RunbookCandidate]:
        """List candidates with optional filters."""
        results = list(self._candidates.values())
        if incident_id is not None:
            results = [c for c in results if c.incident_id == incident_id]
        if status is not None:
            results = [c for c in results if c.status == status]
        return results

    # ── Stats ────────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics."""
        total_feedback = len(self._feedback)
        success_feedback = sum(1 for f in self._feedback.values() if f.success)
        return {
            "total_profiles": len(self._profiles),
            "total_candidates": len(self._candidates),
            "total_feedback": total_feedback,
            "success_rate": (
                round(success_feedback / total_feedback, 4) if total_feedback > 0 else 0.0
            ),
            "candidates_by_status": {
                s.value: sum(1 for c in self._candidates.values() if c.status == s)
                for s in RecommendationStatus
            },
        }
