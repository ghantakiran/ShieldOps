"""Resilience Score Calculator — per-service scoring from redundancy, MTTR, blast radius."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger()


# --- Enums ---


class ResilienceGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class RedundancyLevel(StrEnum):
    NONE = "none"
    SINGLE = "single"
    ACTIVE_PASSIVE = "active_passive"
    ACTIVE_ACTIVE = "active_active"
    MULTI_REGION = "multi_region"


class RecoveryCapability(StrEnum):
    MANUAL = "manual"
    SEMI_AUTOMATED = "semi_automated"
    FULLY_AUTOMATED = "fully_automated"
    SELF_HEALING = "self_healing"
    CHAOS_TESTED = "chaos_tested"


# --- Models ---


class ServiceResilienceProfile(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_name: str = ""
    redundancy_level: RedundancyLevel = RedundancyLevel.NONE
    recovery_capability: RecoveryCapability = RecoveryCapability.MANUAL
    mttr_minutes: float = 0.0
    blast_radius_pct: float = 0.0
    has_circuit_breaker: bool = False
    has_fallback: bool = False
    last_incident_days_ago: int = 0
    created_at: float = Field(default_factory=time.time)


class ResilienceScore(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    service_id: str = ""
    service_name: str = ""
    overall_score: float = 0.0
    grade: ResilienceGrade = ResilienceGrade.CRITICAL
    redundancy_score: float = 0.0
    recovery_score: float = 0.0
    blast_radius_score: float = 0.0
    protection_score: float = 0.0
    recommendations: list[str] = Field(default_factory=list)
    calculated_at: float = Field(default_factory=time.time)


class ResilienceReport(BaseModel):
    total_profiles: int = 0
    avg_score: float = 0.0
    grade_distribution: dict[str, int] = Field(default_factory=dict)
    weakest_services: list[str] = Field(default_factory=list)
    top_recommendations: list[str] = Field(default_factory=list)
    generated_at: float = Field(default_factory=time.time)


# --- Engine ---


class ResilienceScoreCalculator:
    """Per-service resilience scoring from redundancy, MTTR, blast radius, and protections."""

    # Scoring maps for sub-score calculations
    _REDUNDANCY_SCORES: dict[RedundancyLevel, float] = {
        RedundancyLevel.NONE: 0.0,
        RedundancyLevel.SINGLE: 25.0,
        RedundancyLevel.ACTIVE_PASSIVE: 50.0,
        RedundancyLevel.ACTIVE_ACTIVE: 75.0,
        RedundancyLevel.MULTI_REGION: 100.0,
    }

    _RECOVERY_SCORES: dict[RecoveryCapability, float] = {
        RecoveryCapability.MANUAL: 0.0,
        RecoveryCapability.SEMI_AUTOMATED: 25.0,
        RecoveryCapability.FULLY_AUTOMATED: 50.0,
        RecoveryCapability.SELF_HEALING: 75.0,
        RecoveryCapability.CHAOS_TESTED: 100.0,
    }

    def __init__(
        self,
        max_profiles: int = 50000,
        minimum_score_threshold: float = 60.0,
    ) -> None:
        self._max_profiles = max_profiles
        self._minimum_score_threshold = minimum_score_threshold
        self._profiles: list[ServiceResilienceProfile] = []
        self._scores: list[ResilienceScore] = []
        logger.info(
            "resilience_scorer.initialized",
            max_profiles=max_profiles,
            minimum_score_threshold=minimum_score_threshold,
        )

    def register_profile(
        self,
        service_name: str,
        redundancy_level: RedundancyLevel = RedundancyLevel.NONE,
        recovery_capability: RecoveryCapability = RecoveryCapability.MANUAL,
        mttr_minutes: float = 0.0,
        blast_radius_pct: float = 0.0,
        has_circuit_breaker: bool = False,
        has_fallback: bool = False,
        last_incident_days_ago: int = 0,
    ) -> ServiceResilienceProfile:
        profile = ServiceResilienceProfile(
            service_name=service_name,
            redundancy_level=redundancy_level,
            recovery_capability=recovery_capability,
            mttr_minutes=mttr_minutes,
            blast_radius_pct=blast_radius_pct,
            has_circuit_breaker=has_circuit_breaker,
            has_fallback=has_fallback,
            last_incident_days_ago=last_incident_days_ago,
        )
        self._profiles.append(profile)
        if len(self._profiles) > self._max_profiles:
            self._profiles = self._profiles[-self._max_profiles :]
        logger.info(
            "resilience_scorer.profile_registered",
            profile_id=profile.id,
            service_name=service_name,
            redundancy_level=redundancy_level,
            recovery_capability=recovery_capability,
        )
        return profile

    def get_profile(self, profile_id: str) -> ServiceResilienceProfile | None:
        for p in self._profiles:
            if p.id == profile_id:
                return p
        return None

    def list_profiles(
        self,
        redundancy_level: RedundancyLevel | None = None,
        recovery_capability: RecoveryCapability | None = None,
        limit: int = 100,
    ) -> list[ServiceResilienceProfile]:
        results = list(self._profiles)
        if redundancy_level is not None:
            results = [p for p in results if p.redundancy_level == redundancy_level]
        if recovery_capability is not None:
            results = [p for p in results if p.recovery_capability == recovery_capability]
        return results[-limit:]

    def _compute_protection_score(self, profile: ServiceResilienceProfile) -> float:
        """Calculate protection sub-score from circuit breaker, fallback, and incident recency."""
        score = 0.0

        # Circuit breaker: 40 points
        if profile.has_circuit_breaker:
            score += 40.0

        # Fallback mechanism: 40 points
        if profile.has_fallback:
            score += 40.0

        # Incident recency bonus: up to 20 points
        # More days since last incident = better stability
        if profile.last_incident_days_ago >= 90:
            score += 20.0
        elif profile.last_incident_days_ago >= 60:
            score += 15.0
        elif profile.last_incident_days_ago >= 30:
            score += 10.0
        elif profile.last_incident_days_ago >= 7:
            score += 5.0

        return min(score, 100.0)

    def _determine_grade(self, overall_score: float) -> ResilienceGrade:
        """Map overall score to resilience grade."""
        if overall_score >= 90:
            return ResilienceGrade.EXCELLENT
        elif overall_score >= 75:
            return ResilienceGrade.GOOD
        elif overall_score >= 60:
            return ResilienceGrade.FAIR
        elif overall_score >= 40:
            return ResilienceGrade.POOR
        else:
            return ResilienceGrade.CRITICAL

    def _generate_recommendations(
        self,
        profile: ServiceResilienceProfile,
        redundancy_score: float,
        recovery_score: float,
        blast_radius_score: float,
        protection_score: float,
    ) -> list[str]:
        """Generate improvement recommendations based on low sub-scores."""
        recs: list[str] = []

        if redundancy_score < 50:
            recs.append(
                f"Upgrade redundancy for '{profile.service_name}' — "
                f"current level '{profile.redundancy_level.value}' scores {redundancy_score}/100"
            )
        if recovery_score < 50:
            recs.append(
                f"Improve recovery automation for '{profile.service_name}' — "
                f"capability '{profile.recovery_capability.value}' scores {recovery_score}/100"
            )
        if blast_radius_score < 50:
            recs.append(
                f"Reduce blast radius for '{profile.service_name}' — "
                f"currently {profile.blast_radius_pct:.1f}% of infrastructure affected"
            )
        if not profile.has_circuit_breaker:
            recs.append(
                f"Add circuit breaker to '{profile.service_name}' to prevent cascade failures"
            )
        if not profile.has_fallback:
            recs.append(f"Implement fallback mechanism for '{profile.service_name}'")
        if profile.mttr_minutes > 60:
            recs.append(
                f"Reduce MTTR for '{profile.service_name}' — "
                f"currently {profile.mttr_minutes:.0f} minutes, target < 60 minutes"
            )

        return recs

    def calculate_score(self, profile_id: str) -> ResilienceScore:
        profile = self.get_profile(profile_id)
        if profile is None:
            return ResilienceScore(service_id=profile_id)

        # Sub-scores (each weighted 25%)
        redundancy_score = self._REDUNDANCY_SCORES.get(profile.redundancy_level, 0.0)
        recovery_score = self._RECOVERY_SCORES.get(profile.recovery_capability, 0.0)
        blast_radius_score = max(0.0, 100.0 - profile.blast_radius_pct)
        protection_score = self._compute_protection_score(profile)

        # Weighted overall score
        overall = (
            redundancy_score * 0.25
            + recovery_score * 0.25
            + blast_radius_score * 0.25
            + protection_score * 0.25
        )
        overall = round(overall, 2)

        grade = self._determine_grade(overall)
        recommendations = self._generate_recommendations(
            profile, redundancy_score, recovery_score, blast_radius_score, protection_score
        )

        score = ResilienceScore(
            service_id=profile.id,
            service_name=profile.service_name,
            overall_score=overall,
            grade=grade,
            redundancy_score=redundancy_score,
            recovery_score=recovery_score,
            blast_radius_score=blast_radius_score,
            protection_score=protection_score,
            recommendations=recommendations,
        )
        self._scores.append(score)
        if len(self._scores) > self._max_profiles:
            self._scores = self._scores[-self._max_profiles :]

        logger.info(
            "resilience_scorer.score_calculated",
            profile_id=profile_id,
            service_name=profile.service_name,
            overall_score=overall,
            grade=grade,
        )
        return score

    def calculate_all_scores(self) -> list[ResilienceScore]:
        """Calculate resilience scores for all registered profiles."""
        all_scores: list[ResilienceScore] = []
        for profile in self._profiles:
            score = self.calculate_score(profile.id)
            all_scores.append(score)
        logger.info(
            "resilience_scorer.all_scores_calculated",
            profile_count=len(all_scores),
        )
        return all_scores

    def identify_weakest_links(self) -> list[ResilienceScore]:
        """Return scores below the minimum threshold, sorted ascending by score."""
        all_scores = self.calculate_all_scores()
        weak = [s for s in all_scores if s.overall_score < self._minimum_score_threshold]
        weak.sort(key=lambda s: s.overall_score)
        logger.info(
            "resilience_scorer.weakest_links_identified",
            weak_count=len(weak),
            threshold=self._minimum_score_threshold,
        )
        return weak

    def compare_services(self, service_ids: list[str]) -> list[ResilienceScore]:
        """Calculate and return scores for a specific set of profile IDs."""
        compared: list[ResilienceScore] = []
        for sid in service_ids:
            score = self.calculate_score(sid)
            compared.append(score)
        compared.sort(key=lambda s: s.overall_score, reverse=True)
        return compared

    def recommend_improvements(self, profile_id: str) -> list[str]:
        """Generate improvement recommendations for a specific profile."""
        profile = self.get_profile(profile_id)
        if profile is None:
            return []

        redundancy_score = self._REDUNDANCY_SCORES.get(profile.redundancy_level, 0.0)
        recovery_score = self._RECOVERY_SCORES.get(profile.recovery_capability, 0.0)
        blast_radius_score = max(0.0, 100.0 - profile.blast_radius_pct)
        protection_score = self._compute_protection_score(profile)

        return self._generate_recommendations(
            profile, redundancy_score, recovery_score, blast_radius_score, protection_score
        )

    def generate_resilience_report(self) -> ResilienceReport:
        total = len(self._profiles)
        if total == 0:
            return ResilienceReport()

        all_scores = self.calculate_all_scores()

        # Average score
        avg = sum(s.overall_score for s in all_scores) / len(all_scores) if all_scores else 0.0

        # Grade distribution
        grade_dist: dict[str, int] = {}
        for s in all_scores:
            key = s.grade.value
            grade_dist[key] = grade_dist.get(key, 0) + 1

        # Weakest services (below threshold, sorted ascending)
        weak = sorted(
            [s for s in all_scores if s.overall_score < self._minimum_score_threshold],
            key=lambda s: s.overall_score,
        )
        weakest_names = [s.service_name for s in weak[:10]]

        # Aggregate top recommendations (deduplicated, most common first)
        rec_counts: dict[str, int] = {}
        for s in all_scores:
            for r in s.recommendations:
                rec_counts[r] = rec_counts.get(r, 0) + 1
        top_recs = sorted(rec_counts.keys(), key=lambda r: rec_counts[r], reverse=True)[:10]

        report = ResilienceReport(
            total_profiles=total,
            avg_score=round(avg, 2),
            grade_distribution=grade_dist,
            weakest_services=weakest_names,
            top_recommendations=top_recs,
        )
        logger.info(
            "resilience_scorer.report_generated",
            total_profiles=total,
            avg_score=round(avg, 2),
            weak_count=len(weak),
        )
        return report

    def clear_data(self) -> None:
        self._profiles.clear()
        self._scores.clear()
        logger.info("resilience_scorer.data_cleared")

    def get_stats(self) -> dict[str, Any]:
        service_names = {p.service_name for p in self._profiles}
        redundancy_levels = {p.redundancy_level.value for p in self._profiles}
        recovery_capabilities = {p.recovery_capability.value for p in self._profiles}
        return {
            "total_profiles": len(self._profiles),
            "total_scores": len(self._scores),
            "unique_service_names": len(service_names),
            "redundancy_levels": sorted(redundancy_levels),
            "recovery_capabilities": sorted(recovery_capabilities),
        }
