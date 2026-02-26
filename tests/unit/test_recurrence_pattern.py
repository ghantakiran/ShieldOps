"""Tests for shieldops.incidents.recurrence_pattern — RecurrencePatternDetector."""

from __future__ import annotations

from shieldops.incidents.recurrence_pattern import (
    PatternStrength,
    RecurrenceCluster,
    RecurrenceFrequency,
    RecurrencePatternDetector,
    RecurrencePatternReport,
    RecurrenceRecord,
    RecurrenceType,
)


def _engine(**kw) -> RecurrencePatternDetector:
    return RecurrencePatternDetector(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # RecurrenceType (5)
    def test_type_time_based(self):
        assert RecurrenceType.TIME_BASED == "time_based"

    def test_type_event_based(self):
        assert RecurrenceType.EVENT_BASED == "event_based"

    def test_type_seasonal(self):
        assert RecurrenceType.SEASONAL == "seasonal"

    def test_type_deployment(self):
        assert RecurrenceType.DEPLOYMENT_CORRELATED == "deployment_correlated"

    def test_type_load(self):
        assert RecurrenceType.LOAD_CORRELATED == "load_correlated"

    # RecurrenceFrequency (5)
    def test_freq_hourly(self):
        assert RecurrenceFrequency.HOURLY == "hourly"

    def test_freq_daily(self):
        assert RecurrenceFrequency.DAILY == "daily"

    def test_freq_weekly(self):
        assert RecurrenceFrequency.WEEKLY == "weekly"

    def test_freq_monthly(self):
        assert RecurrenceFrequency.MONTHLY == "monthly"

    def test_freq_irregular(self):
        assert RecurrenceFrequency.IRREGULAR == "irregular"

    # PatternStrength (5)
    def test_strength_strong(self):
        assert PatternStrength.STRONG == "strong"

    def test_strength_moderate(self):
        assert PatternStrength.MODERATE == "moderate"

    def test_strength_weak(self):
        assert PatternStrength.WEAK == "weak"

    def test_strength_emerging(self):
        assert PatternStrength.EMERGING == "emerging"

    def test_strength_inconclusive(self):
        assert PatternStrength.INCONCLUSIVE == "inconclusive"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_recurrence_record_defaults(self):
        r = RecurrenceRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.service_name == ""
        assert r.recurrence_type == RecurrenceType.TIME_BASED
        assert r.frequency == RecurrenceFrequency.IRREGULAR
        assert r.occurrence_count == 0
        assert r.pattern_strength == PatternStrength.INCONCLUSIVE
        assert r.details == ""
        assert r.created_at > 0

    def test_recurrence_cluster_defaults(self):
        r = RecurrenceCluster()
        assert r.id
        assert r.cluster_name == ""
        assert r.service_name == ""
        assert r.incident_count == 0
        assert r.recurrence_type == RecurrenceType.TIME_BASED
        assert r.pattern_strength == PatternStrength.INCONCLUSIVE
        assert r.created_at > 0

    def test_recurrence_pattern_report_defaults(self):
        r = RecurrencePatternReport()
        assert r.total_recurrences == 0
        assert r.total_clusters == 0
        assert r.avg_occurrence_count == 0.0
        assert r.by_type == {}
        assert r.by_frequency == {}
        assert r.strong_pattern_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_recurrence
# -------------------------------------------------------------------


class TestRecordRecurrence:
    def test_basic(self):
        eng = _engine()
        r = eng.record_recurrence("inc-1", "svc-a", occurrence_count=10)
        assert r.incident_id == "inc-1"
        assert r.pattern_strength == PatternStrength.STRONG

    def test_auto_strength_moderate(self):
        eng = _engine()
        r = eng.record_recurrence("inc-2", "svc-b", occurrence_count=5)
        assert r.pattern_strength == PatternStrength.MODERATE

    def test_auto_strength_weak(self):
        eng = _engine()
        r = eng.record_recurrence("inc-3", "svc-c", occurrence_count=3)
        assert r.pattern_strength == PatternStrength.WEAK

    def test_auto_strength_inconclusive(self):
        eng = _engine()
        r = eng.record_recurrence("inc-4", "svc-d", occurrence_count=1)
        assert r.pattern_strength == PatternStrength.INCONCLUSIVE

    def test_explicit_strength(self):
        eng = _engine()
        r = eng.record_recurrence("inc-5", "svc-e", pattern_strength=PatternStrength.EMERGING)
        assert r.pattern_strength == PatternStrength.EMERGING

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_recurrence(f"inc-{i}", f"svc-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_recurrence
# -------------------------------------------------------------------


class TestGetRecurrence:
    def test_found(self):
        eng = _engine()
        r = eng.record_recurrence("inc-1", "svc-a")
        assert eng.get_recurrence(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_recurrence("nonexistent") is None


# -------------------------------------------------------------------
# list_recurrences
# -------------------------------------------------------------------


class TestListRecurrences:
    def test_list_all(self):
        eng = _engine()
        eng.record_recurrence("inc-1", "svc-a")
        eng.record_recurrence("inc-2", "svc-b")
        assert len(eng.list_recurrences()) == 2

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_recurrence("inc-1", "svc-a")
        eng.record_recurrence("inc-2", "svc-b")
        results = eng.list_recurrences(service_name="svc-a")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_recurrence("inc-1", "svc-a", recurrence_type=RecurrenceType.SEASONAL)
        eng.record_recurrence("inc-2", "svc-b", recurrence_type=RecurrenceType.TIME_BASED)
        results = eng.list_recurrences(recurrence_type=RecurrenceType.SEASONAL)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_cluster
# -------------------------------------------------------------------


class TestAddCluster:
    def test_basic(self):
        eng = _engine()
        c = eng.add_cluster(
            "cpu-cluster",
            "svc-a",
            incident_count=15,
            recurrence_type=RecurrenceType.TIME_BASED,
            pattern_strength=PatternStrength.STRONG,
        )
        assert c.cluster_name == "cpu-cluster"
        assert c.incident_count == 15

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_cluster(f"cluster-{i}", f"svc-{i}")
        assert len(eng._clusters) == 2


# -------------------------------------------------------------------
# analyze_incident_recurrence
# -------------------------------------------------------------------


class TestAnalyzeIncidentRecurrence:
    def test_with_data(self):
        eng = _engine()
        eng.record_recurrence(
            "inc-1",
            "svc-a",
            recurrence_type=RecurrenceType.SEASONAL,
            frequency=RecurrenceFrequency.WEEKLY,
        )
        result = eng.analyze_incident_recurrence("svc-a")
        assert result["service_name"] == "svc-a"
        assert result["total_records"] == 1
        assert result["type_distribution"]["seasonal"] == 1

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_incident_recurrence("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_strong_patterns
# -------------------------------------------------------------------


class TestIdentifyStrongPatterns:
    def test_with_strong(self):
        eng = _engine()
        eng.record_recurrence("inc-1", "svc-a", occurrence_count=10)
        eng.record_recurrence("inc-2", "svc-b", occurrence_count=1)
        results = eng.identify_strong_patterns()
        assert len(results) == 1
        assert results[0]["pattern_strength"] == "strong"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_strong_patterns() == []


# -------------------------------------------------------------------
# rank_by_incident_count
# -------------------------------------------------------------------


class TestRankByIncidentCount:
    def test_with_data(self):
        eng = _engine()
        eng.record_recurrence("inc-1", "svc-a", occurrence_count=5)
        eng.record_recurrence("inc-2", "svc-b", occurrence_count=20)
        results = eng.rank_by_incident_count()
        assert results[0]["occurrence_count"] == 20

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_incident_count() == []


# -------------------------------------------------------------------
# detect_emerging_patterns
# -------------------------------------------------------------------


class TestDetectEmergingPatterns:
    def test_with_emerging(self):
        eng = _engine()
        eng.record_recurrence(
            "inc-1",
            "svc-a",
            pattern_strength=PatternStrength.EMERGING,
        )
        eng.record_recurrence(
            "inc-2",
            "svc-b",
            pattern_strength=PatternStrength.STRONG,
        )
        results = eng.detect_emerging_patterns()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.detect_emerging_patterns() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_recurrence("inc-1", "svc-a", occurrence_count=10)
        eng.record_recurrence(
            "inc-2",
            "svc-b",
            pattern_strength=PatternStrength.EMERGING,
        )
        eng.add_cluster("c1", "svc-a")
        report = eng.generate_report()
        assert report.total_recurrences == 2
        assert report.total_clusters == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_recurrences == 0
        assert "No significant" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_recurrence("inc-1", "svc-a")
        eng.add_cluster("c1", "svc-a")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._clusters) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_recurrences"] == 0
        assert stats["total_clusters"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_recurrence(
            "inc-1",
            "svc-a",
            recurrence_type=RecurrenceType.SEASONAL,
        )
        eng.record_recurrence(
            "inc-2",
            "svc-b",
            recurrence_type=RecurrenceType.TIME_BASED,
        )
        eng.add_cluster("c1", "svc-a")
        stats = eng.get_stats()
        assert stats["total_recurrences"] == 2
        assert stats["total_clusters"] == 1
        assert stats["unique_services"] == 2
