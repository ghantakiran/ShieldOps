"""Tests for shieldops.playbooks.runbook_recommender — RunbookRecommender."""

from __future__ import annotations

import pytest

from shieldops.playbooks.runbook_recommender import (
    FeedbackRecord,
    RecommendationReason,
    RecommendationStatus,
    RunbookCandidate,
    RunbookProfile,
    RunbookRecommender,
)


def _recommender(**kw) -> RunbookRecommender:
    return RunbookRecommender(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # RecommendationReason (4 values)

    def test_reason_symptom_match(self):
        assert RecommendationReason.SYMPTOM_MATCH == "symptom_match"

    def test_reason_historical_success(self):
        assert RecommendationReason.HISTORICAL_SUCCESS == "historical_success"

    def test_reason_service_match(self):
        assert RecommendationReason.SERVICE_MATCH == "service_match"

    def test_reason_similar_incident(self):
        assert RecommendationReason.SIMILAR_INCIDENT == "similar_incident"

    # RecommendationStatus (4 values)

    def test_status_pending(self):
        assert RecommendationStatus.PENDING == "pending"

    def test_status_accepted(self):
        assert RecommendationStatus.ACCEPTED == "accepted"

    def test_status_rejected(self):
        assert RecommendationStatus.REJECTED == "rejected"

    def test_status_executed(self):
        assert RecommendationStatus.EXECUTED == "executed"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_runbook_candidate_defaults(self):
        c = RunbookCandidate()
        assert c.id
        assert c.runbook_id == ""
        assert c.runbook_name == ""
        assert c.incident_id == ""
        assert c.score == 0.0
        assert c.reasons == []
        assert c.status == RecommendationStatus.PENDING
        assert c.recommended_at > 0

    def test_feedback_record_defaults(self):
        f = FeedbackRecord()
        assert f.id
        assert f.candidate_id == ""
        assert f.outcome == ""
        assert f.success is False
        assert f.execution_time_seconds == 0.0
        assert f.recorded_at > 0

    def test_runbook_profile_defaults(self):
        p = RunbookProfile()
        assert p.runbook_id == ""
        assert p.name == ""
        assert p.symptoms == []
        assert p.services == []
        assert p.success_count == 0
        assert p.failure_count == 0
        assert p.avg_execution_time == 0.0


# ---------------------------------------------------------------------------
# register_runbook
# ---------------------------------------------------------------------------


class TestRegisterRunbook:
    def test_basic_register(self):
        r = _recommender()
        p = r.register_runbook("rb-1", "Restart Service")
        assert p.runbook_id == "rb-1"
        assert p.name == "Restart Service"
        assert p.symptoms == []
        assert p.services == []

    def test_register_with_symptoms_and_services(self):
        r = _recommender()
        p = r.register_runbook(
            "rb-2",
            "Scale Out",
            symptoms=["high_cpu", "slow_response"],
            services=["web", "api"],
        )
        assert p.symptoms == ["high_cpu", "slow_response"]
        assert p.services == ["web", "api"]

    def test_evicts_at_max_profiles(self):
        r = _recommender(max_profiles=2)
        r.register_runbook("rb-1", "First")
        r.register_runbook("rb-2", "Second")
        r.register_runbook("rb-3", "Third")
        assert len(r._profiles) == 2
        assert r.get_profile("rb-1") is None
        assert r.get_profile("rb-3") is not None

    def test_list_profiles(self):
        r = _recommender()
        r.register_runbook("rb-1", "First")
        r.register_runbook("rb-2", "Second")
        assert len(r.list_profiles()) == 2


# ---------------------------------------------------------------------------
# recommend
# ---------------------------------------------------------------------------


class TestRecommend:
    def test_no_profiles_returns_empty(self):
        r = _recommender()
        result = r.recommend("inc-1", ["high_cpu"])
        assert result == []

    def test_symptom_match_scores_point_three_per_match(self):
        r = _recommender(min_score=0.0)
        r.register_runbook(
            "rb-1",
            "Fix CPU",
            symptoms=["high_cpu", "oom"],
        )
        result = r.recommend("inc-1", ["high_cpu", "oom"])
        assert len(result) == 1
        assert result[0].score == pytest.approx(0.6, abs=0.01)

    def test_service_match_scores_point_two(self):
        r = _recommender(min_score=0.0)
        r.register_runbook(
            "rb-1",
            "Fix Web",
            services=["web"],
        )
        result = r.recommend("inc-1", [], service="web")
        assert len(result) == 1
        assert result[0].score == pytest.approx(0.2, abs=0.01)

    def test_historical_success_adds_score(self):
        r = _recommender(min_score=0.0)
        r.register_runbook("rb-1", "Fix All")
        profile = r.get_profile("rb-1")
        profile.success_count = 8
        profile.failure_count = 2
        result = r.recommend("inc-1", [])
        assert len(result) == 1
        # 0.1 * (8/10) = 0.08
        assert result[0].score == pytest.approx(0.08, abs=0.01)

    def test_below_min_score_filtered_out(self):
        r = _recommender(min_score=0.5)
        r.register_runbook(
            "rb-1",
            "Low Match",
            symptoms=["high_cpu"],
        )
        result = r.recommend("inc-1", ["high_cpu"])
        # 0.3 < 0.5 threshold
        assert result == []

    def test_limit_respected(self):
        r = _recommender(min_score=0.0)
        for i in range(5):
            r.register_runbook(
                f"rb-{i}",
                f"Runbook {i}",
                symptoms=["high_cpu"],
            )
        result = r.recommend("inc-1", ["high_cpu"], limit=2)
        assert len(result) == 2

    def test_sorted_by_score_desc(self):
        r = _recommender(min_score=0.0)
        r.register_runbook(
            "rb-1",
            "One Match",
            symptoms=["high_cpu"],
        )
        r.register_runbook(
            "rb-2",
            "Two Matches",
            symptoms=["high_cpu", "oom"],
        )
        result = r.recommend("inc-1", ["high_cpu", "oom"])
        assert result[0].runbook_id == "rb-2"
        assert result[1].runbook_id == "rb-1"
        assert result[0].score > result[1].score

    def test_reasons_include_symptom_match(self):
        r = _recommender(min_score=0.0)
        r.register_runbook(
            "rb-1",
            "Fix",
            symptoms=["high_cpu"],
        )
        result = r.recommend("inc-1", ["high_cpu"])
        assert RecommendationReason.SYMPTOM_MATCH in result[0].reasons

    def test_reasons_include_service_match(self):
        r = _recommender(min_score=0.0)
        r.register_runbook(
            "rb-1",
            "Fix",
            services=["api"],
        )
        result = r.recommend("inc-1", [], service="api")
        assert RecommendationReason.SERVICE_MATCH in result[0].reasons


# ---------------------------------------------------------------------------
# record_feedback
# ---------------------------------------------------------------------------


class TestFeedback:
    def test_success_updates_profile_success_count(self):
        r = _recommender(min_score=0.0)
        r.register_runbook("rb-1", "Fix", symptoms=["x"])
        candidates = r.recommend("inc-1", ["x"])
        r.record_feedback(candidates[0].id, success=True)
        profile = r.get_profile("rb-1")
        assert profile.success_count == 1

    def test_failure_updates_failure_count(self):
        r = _recommender(min_score=0.0)
        r.register_runbook("rb-1", "Fix", symptoms=["x"])
        candidates = r.recommend("inc-1", ["x"])
        r.record_feedback(candidates[0].id, success=False)
        profile = r.get_profile("rb-1")
        assert profile.failure_count == 1

    def test_updates_avg_execution_time(self):
        r = _recommender(min_score=0.0)
        r.register_runbook("rb-1", "Fix", symptoms=["x"])
        c1 = r.recommend("inc-1", ["x"])
        r.record_feedback(c1[0].id, success=True, execution_time=10.0)
        c2 = r.recommend("inc-2", ["x"])
        r.record_feedback(c2[0].id, success=True, execution_time=20.0)
        profile = r.get_profile("rb-1")
        assert profile.avg_execution_time == pytest.approx(15.0, abs=0.01)

    def test_feedback_sets_executed_status(self):
        r = _recommender(min_score=0.0)
        r.register_runbook("rb-1", "Fix", symptoms=["x"])
        candidates = r.recommend("inc-1", ["x"])
        r.record_feedback(candidates[0].id, success=True)
        c = r.get_candidate(candidates[0].id)
        assert c.status == RecommendationStatus.EXECUTED


# ---------------------------------------------------------------------------
# accept / reject
# ---------------------------------------------------------------------------


class TestAcceptReject:
    def test_accept_sets_accepted(self):
        r = _recommender(min_score=0.0)
        r.register_runbook("rb-1", "Fix", symptoms=["x"])
        candidates = r.recommend("inc-1", ["x"])
        result = r.accept_recommendation(candidates[0].id)
        assert result is not None
        assert result.status == RecommendationStatus.ACCEPTED

    def test_reject_sets_rejected(self):
        r = _recommender(min_score=0.0)
        r.register_runbook("rb-1", "Fix", symptoms=["x"])
        candidates = r.recommend("inc-1", ["x"])
        result = r.reject_recommendation(candidates[0].id)
        assert result is not None
        assert result.status == RecommendationStatus.REJECTED

    def test_accept_not_found_returns_none(self):
        r = _recommender()
        assert r.accept_recommendation("nonexistent") is None

    def test_reject_not_found_returns_none(self):
        r = _recommender()
        assert r.reject_recommendation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_candidates
# ---------------------------------------------------------------------------


class TestListCandidates:
    def test_filter_by_incident_id(self):
        r = _recommender(min_score=0.0)
        r.register_runbook("rb-1", "Fix", symptoms=["x"])
        r.recommend("inc-1", ["x"])
        r.recommend("inc-2", ["x"])
        results = r.list_candidates(incident_id="inc-1")
        assert len(results) == 1
        assert results[0].incident_id == "inc-1"

    def test_filter_by_status(self):
        r = _recommender(min_score=0.0)
        r.register_runbook("rb-1", "Fix", symptoms=["x"])
        candidates = r.recommend("inc-1", ["x"])
        r.accept_recommendation(candidates[0].id)
        r.recommend("inc-2", ["x"])
        accepted = r.list_candidates(status=RecommendationStatus.ACCEPTED)
        pending = r.list_candidates(status=RecommendationStatus.PENDING)
        assert len(accepted) == 1
        assert len(pending) == 1

    def test_list_all(self):
        r = _recommender(min_score=0.0)
        r.register_runbook("rb-1", "Fix", symptoms=["x"])
        r.recommend("inc-1", ["x"])
        r.recommend("inc-2", ["x"])
        assert len(r.list_candidates()) == 2


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty_stats(self):
        r = _recommender()
        stats = r.get_stats()
        assert stats["total_profiles"] == 0
        assert stats["total_candidates"] == 0
        assert stats["total_feedback"] == 0
        assert stats["success_rate"] == 0.0

    def test_populated_stats_with_success_rate(self):
        r = _recommender(min_score=0.0)
        r.register_runbook("rb-1", "Fix", symptoms=["x"])
        c1 = r.recommend("inc-1", ["x"])
        c2 = r.recommend("inc-2", ["x"])
        r.record_feedback(c1[0].id, success=True)
        r.record_feedback(c2[0].id, success=False)
        stats = r.get_stats()
        assert stats["total_profiles"] == 1
        assert stats["total_candidates"] == 2
        assert stats["total_feedback"] == 2
        assert stats["success_rate"] == pytest.approx(0.5, abs=0.01)

    def test_candidates_by_status(self):
        r = _recommender(min_score=0.0)
        r.register_runbook("rb-1", "Fix", symptoms=["x"])
        candidates = r.recommend("inc-1", ["x"])
        r.accept_recommendation(candidates[0].id)
        stats = r.get_stats()
        by_status = stats["candidates_by_status"]
        assert by_status["accepted"] == 1
        assert by_status["pending"] == 0
