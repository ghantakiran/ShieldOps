"""Tests for shieldops.analytics.toil_tracker — ToilMeasurementTracker."""

from __future__ import annotations

from shieldops.analytics.toil_tracker import (
    AutomationCandidate,
    AutomationPotential,
    ToilCategory,
    ToilEntry,
    ToilMeasurementTracker,
    ToilSummary,
    ToilTrend,
)


def _engine(**kw) -> ToilMeasurementTracker:
    return ToilMeasurementTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_category_manual_deployment(self):
        assert ToilCategory.MANUAL_DEPLOYMENT == "manual_deployment"

    def test_category_incident_triage(self):
        assert ToilCategory.INCIDENT_TRIAGE == "incident_triage"

    def test_category_config_update(self):
        assert ToilCategory.CONFIG_UPDATE == "config_update"

    def test_category_certificate_renewal(self):
        assert ToilCategory.CERTIFICATE_RENEWAL == "certificate_renewal"

    def test_category_access_provisioning(self):
        assert ToilCategory.ACCESS_PROVISIONING == "access_provisioning"

    def test_potential_fully(self):
        assert AutomationPotential.FULLY_AUTOMATABLE == "fully_automatable"

    def test_potential_partially(self):
        assert AutomationPotential.PARTIALLY_AUTOMATABLE == "partially_automatable"

    def test_potential_judgment(self):
        assert AutomationPotential.REQUIRES_JUDGMENT == "requires_judgment"

    def test_potential_not(self):
        assert AutomationPotential.NOT_AUTOMATABLE == "not_automatable"

    def test_trend_decreasing(self):
        assert ToilTrend.DECREASING == "decreasing"

    def test_trend_stable(self):
        assert ToilTrend.STABLE == "stable"

    def test_trend_increasing(self):
        assert ToilTrend.INCREASING == "increasing"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_toil_entry_defaults(self):
        e = ToilEntry(team="platform")
        assert e.id
        assert e.team == "platform"
        assert e.category == ToilCategory.MANUAL_DEPLOYMENT
        assert e.duration_minutes == 0.0
        assert e.automated is False

    def test_summary_defaults(self):
        s = ToilSummary(team="platform")
        assert s.total_entries == 0
        assert s.trend == ToilTrend.STABLE

    def test_candidate_defaults(self):
        c = AutomationCandidate(category=ToilCategory.MANUAL_DEPLOYMENT)
        assert c.occurrences == 0
        assert c.potential == AutomationPotential.FULLY_AUTOMATABLE


# ---------------------------------------------------------------------------
# record_toil
# ---------------------------------------------------------------------------


class TestRecordToil:
    def test_basic_record(self):
        eng = _engine()
        entry = eng.record_toil("platform", duration_minutes=30.0)
        assert entry.team == "platform"
        assert entry.duration_minutes == 30.0

    def test_unique_ids(self):
        eng = _engine()
        e1 = eng.record_toil("team-a")
        e2 = eng.record_toil("team-b")
        assert e1.id != e2.id

    def test_evicts_at_max(self):
        eng = _engine(max_entries=3)
        for i in range(5):
            eng.record_toil(f"team-{i}")
        assert len(eng._entries) == 3

    def test_with_custom_fields(self):
        eng = _engine()
        entry = eng.record_toil(
            "platform",
            category=ToilCategory.INCIDENT_TRIAGE,
            duration_minutes=60.0,
            engineer="alice",
        )
        assert entry.category == ToilCategory.INCIDENT_TRIAGE
        assert entry.engineer == "alice"


# ---------------------------------------------------------------------------
# get_entry / list_entries
# ---------------------------------------------------------------------------


class TestGetEntry:
    def test_found(self):
        eng = _engine()
        entry = eng.record_toil("platform")
        assert eng.get_entry(entry.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_entry("nonexistent") is None


class TestListEntries:
    def test_list_all(self):
        eng = _engine()
        eng.record_toil("team-a")
        eng.record_toil("team-b")
        assert len(eng.list_entries()) == 2

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_toil("team-a")
        eng.record_toil("team-b")
        results = eng.list_entries(team="team-a")
        assert len(results) == 1

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_toil("team-a", category=ToilCategory.MANUAL_DEPLOYMENT)
        eng.record_toil("team-a", category=ToilCategory.INCIDENT_TRIAGE)
        results = eng.list_entries(category=ToilCategory.INCIDENT_TRIAGE)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# compute_summary
# ---------------------------------------------------------------------------


class TestComputeSummary:
    def test_basic_summary(self):
        eng = _engine()
        eng.record_toil("platform", duration_minutes=30.0)
        eng.record_toil("platform", duration_minutes=60.0)
        summary = eng.compute_summary("platform")
        assert summary.total_entries == 2
        assert summary.total_minutes == 90.0
        assert summary.avg_duration_minutes == 45.0

    def test_empty_summary(self):
        eng = _engine()
        summary = eng.compute_summary("no-team")
        assert summary.total_entries == 0
        assert summary.trend == ToilTrend.STABLE

    def test_increasing_trend(self):
        eng = _engine()
        # First half: low duration
        for _ in range(4):
            eng.record_toil("platform", duration_minutes=10.0)
        # Second half: high duration
        for _ in range(4):
            eng.record_toil("platform", duration_minutes=100.0)
        summary = eng.compute_summary("platform")
        assert summary.trend == ToilTrend.INCREASING


# ---------------------------------------------------------------------------
# identify_automation_candidates
# ---------------------------------------------------------------------------


class TestAutomationCandidates:
    def test_candidates_found(self):
        eng = _engine(automation_min_occurrences=3)
        for _ in range(5):
            eng.record_toil(
                "platform",
                category=ToilCategory.MANUAL_DEPLOYMENT,
                duration_minutes=30.0,
            )
        candidates = eng.identify_automation_candidates()
        assert len(candidates) >= 1
        assert candidates[0].category == ToilCategory.MANUAL_DEPLOYMENT

    def test_below_threshold(self):
        eng = _engine(automation_min_occurrences=10)
        for _ in range(3):
            eng.record_toil("platform", category=ToilCategory.MANUAL_DEPLOYMENT)
        candidates = eng.identify_automation_candidates()
        assert len(candidates) == 0

    def test_automated_excluded(self):
        eng = _engine(automation_min_occurrences=3)
        for _ in range(5):
            eng.record_toil(
                "platform",
                category=ToilCategory.MANUAL_DEPLOYMENT,
                automated=True,
            )
        candidates = eng.identify_automation_candidates()
        assert len(candidates) == 0


# ---------------------------------------------------------------------------
# trend / ranking / savings / clear / stats
# ---------------------------------------------------------------------------


class TestToilTrend:
    def test_get_trend(self):
        eng = _engine()
        eng.record_toil("platform", duration_minutes=10.0)
        trend = eng.get_toil_trend("platform")
        assert trend == ToilTrend.STABLE


class TestTeamRanking:
    def test_ranking(self):
        eng = _engine()
        eng.record_toil("team-a", duration_minutes=100.0)
        eng.record_toil("team-b", duration_minutes=50.0)
        ranking = eng.get_team_ranking()
        assert len(ranking) == 2
        assert ranking[0]["team"] == "team-a"


class TestSavings:
    def test_compute_savings(self):
        eng = _engine(automation_min_occurrences=2)
        for _ in range(5):
            eng.record_toil(
                "team-a",
                category=ToilCategory.MANUAL_DEPLOYMENT,
                duration_minutes=30.0,
            )
        savings = eng.compute_automation_savings()
        assert savings["potential_savings_minutes"] > 0


class TestClearEntries:
    def test_clear(self):
        eng = _engine()
        eng.record_toil("team-a")
        count = eng.clear_entries()
        assert count == 1
        assert len(eng._entries) == 0


class TestGetStats:
    def test_empty_stats(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_entries"] == 0

    def test_populated_stats(self):
        eng = _engine()
        eng.record_toil(
            "team-a",
            category=ToilCategory.MANUAL_DEPLOYMENT,
            duration_minutes=30.0,
        )
        eng.record_toil(
            "team-b",
            category=ToilCategory.INCIDENT_TRIAGE,
            duration_minutes=60.0,
        )
        stats = eng.get_stats()
        assert stats["total_entries"] == 2
        assert stats["unique_teams"] == 2
        assert stats["total_minutes"] == 90.0
