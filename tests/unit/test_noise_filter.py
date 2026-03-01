"""Tests for shieldops.incidents.noise_filter — IncidentNoiseFilter."""

from __future__ import annotations

from shieldops.incidents.noise_filter import (
    FilterAction,
    IncidentNoiseFilter,
    NoiseCategory,
    NoiseConfidence,
    NoiseFilterReport,
    NoisePattern,
    NoiseRecord,
)


def _engine(**kw) -> IncidentNoiseFilter:
    return IncidentNoiseFilter(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_category_false_alarm(self):
        assert NoiseCategory.FALSE_ALARM == "false_alarm"

    def test_category_duplicate(self):
        assert NoiseCategory.DUPLICATE == "duplicate"

    def test_category_informational(self):
        assert NoiseCategory.INFORMATIONAL == "informational"

    def test_category_transient(self):
        assert NoiseCategory.TRANSIENT == "transient"

    def test_category_legitimate(self):
        assert NoiseCategory.LEGITIMATE == "legitimate"

    def test_confidence_high(self):
        assert NoiseConfidence.HIGH == "high"

    def test_confidence_moderate(self):
        assert NoiseConfidence.MODERATE == "moderate"

    def test_confidence_low(self):
        assert NoiseConfidence.LOW == "low"

    def test_confidence_uncertain(self):
        assert NoiseConfidence.UNCERTAIN == "uncertain"

    def test_confidence_unclassified(self):
        assert NoiseConfidence.UNCLASSIFIED == "unclassified"

    def test_action_suppress(self):
        assert FilterAction.SUPPRESS == "suppress"

    def test_action_merge(self):
        assert FilterAction.MERGE == "merge"

    def test_action_downgrade(self):
        assert FilterAction.DOWNGRADE == "downgrade"

    def test_action_escalate(self):
        assert FilterAction.ESCALATE == "escalate"

    def test_action_pass_through(self):
        assert FilterAction.PASS_THROUGH == "pass_through"  # noqa: S105


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_noise_record_defaults(self):
        r = NoiseRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.noise_category == NoiseCategory.FALSE_ALARM
        assert r.confidence == NoiseConfidence.UNCLASSIFIED
        assert r.filter_action == FilterAction.PASS_THROUGH
        assert r.team == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_noise_pattern_defaults(self):
        p = NoisePattern()
        assert p.id
        assert p.pattern_name == ""
        assert p.noise_category == NoiseCategory.FALSE_ALARM
        assert p.occurrence_count == 0
        assert p.created_at > 0

    def test_noise_filter_report_defaults(self):
        r = NoiseFilterReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_patterns == 0
        assert r.false_alarm_rate_pct == 0.0
        assert r.by_category == {}
        assert r.by_confidence == {}
        assert r.by_action == {}
        assert r.top_noisy_sources == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_noise
# ---------------------------------------------------------------------------


class TestRecordNoise:
    def test_basic(self):
        eng = _engine()
        r = eng.record_noise(
            incident_id="INC-001",
            noise_category=NoiseCategory.DUPLICATE,
            confidence=NoiseConfidence.HIGH,
            filter_action=FilterAction.MERGE,
            team="sre",
        )
        assert r.incident_id == "INC-001"
        assert r.noise_category == NoiseCategory.DUPLICATE
        assert r.confidence == NoiseConfidence.HIGH
        assert r.filter_action == FilterAction.MERGE
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_noise(incident_id=f"INC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_noise
# ---------------------------------------------------------------------------


class TestGetNoise:
    def test_found(self):
        eng = _engine()
        r = eng.record_noise(
            incident_id="INC-001",
            confidence=NoiseConfidence.HIGH,
        )
        result = eng.get_noise(r.id)
        assert result is not None
        assert result.confidence == NoiseConfidence.HIGH

    def test_not_found(self):
        eng = _engine()
        assert eng.get_noise("nonexistent") is None


# ---------------------------------------------------------------------------
# list_noise
# ---------------------------------------------------------------------------


class TestListNoise:
    def test_list_all(self):
        eng = _engine()
        eng.record_noise(incident_id="INC-001")
        eng.record_noise(incident_id="INC-002")
        assert len(eng.list_noise()) == 2

    def test_filter_by_category(self):
        eng = _engine()
        eng.record_noise(
            incident_id="INC-001",
            noise_category=NoiseCategory.DUPLICATE,
        )
        eng.record_noise(
            incident_id="INC-002",
            noise_category=NoiseCategory.TRANSIENT,
        )
        results = eng.list_noise(category=NoiseCategory.DUPLICATE)
        assert len(results) == 1

    def test_filter_by_confidence(self):
        eng = _engine()
        eng.record_noise(
            incident_id="INC-001",
            confidence=NoiseConfidence.HIGH,
        )
        eng.record_noise(
            incident_id="INC-002",
            confidence=NoiseConfidence.LOW,
        )
        results = eng.list_noise(confidence=NoiseConfidence.HIGH)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_noise(incident_id="INC-001", team="sre")
        eng.record_noise(incident_id="INC-002", team="platform")
        results = eng.list_noise(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_noise(incident_id=f"INC-{i}")
        assert len(eng.list_noise(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_pattern
# ---------------------------------------------------------------------------


class TestAddPattern:
    def test_basic(self):
        eng = _engine()
        p = eng.add_pattern(
            pattern_name="flapping-cpu",
            noise_category=NoiseCategory.TRANSIENT,
            occurrence_count=15,
        )
        assert p.pattern_name == "flapping-cpu"
        assert p.noise_category == NoiseCategory.TRANSIENT
        assert p.occurrence_count == 15

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_pattern(pattern_name=f"pat-{i}")
        assert len(eng._patterns) == 2


# ---------------------------------------------------------------------------
# analyze_noise_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeNoiseDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_noise(
            incident_id="INC-001",
            noise_category=NoiseCategory.FALSE_ALARM,
            confidence=NoiseConfidence.HIGH,
        )
        eng.record_noise(
            incident_id="INC-002",
            noise_category=NoiseCategory.FALSE_ALARM,
            confidence=NoiseConfidence.LOW,
        )
        result = eng.analyze_noise_distribution()
        assert "false_alarm" in result
        assert result["false_alarm"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_noise_distribution() == {}


# ---------------------------------------------------------------------------
# identify_false_alarms
# ---------------------------------------------------------------------------


class TestIdentifyFalseAlarms:
    def test_detects_false_alarms(self):
        eng = _engine()
        eng.record_noise(
            incident_id="INC-001",
            noise_category=NoiseCategory.FALSE_ALARM,
        )
        eng.record_noise(
            incident_id="INC-002",
            noise_category=NoiseCategory.LEGITIMATE,
        )
        results = eng.identify_false_alarms()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_false_alarms() == []


# ---------------------------------------------------------------------------
# rank_by_noise_volume
# ---------------------------------------------------------------------------


class TestRankByNoiseVolume:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_noise(incident_id="INC-001", team="sre")
        eng.record_noise(incident_id="INC-002", team="sre")
        eng.record_noise(incident_id="INC-003", team="platform")
        results = eng.rank_by_noise_volume()
        assert len(results) == 2
        assert results[0]["team"] == "sre"
        assert results[0]["noise_count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_noise_volume() == []


# ---------------------------------------------------------------------------
# detect_noise_trends
# ---------------------------------------------------------------------------


class TestDetectNoiseTrends:
    def test_stable(self):
        eng = _engine()
        for count in [10, 10, 10, 10]:
            eng.add_pattern(pattern_name="p", occurrence_count=count)
        result = eng.detect_noise_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for count in [5, 5, 20, 20]:
            eng.add_pattern(pattern_name="p", occurrence_count=count)
        result = eng.detect_noise_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_noise_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_noise(
            incident_id="INC-001",
            noise_category=NoiseCategory.FALSE_ALARM,
            confidence=NoiseConfidence.HIGH,
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, NoiseFilterReport)
        assert report.total_records == 1
        assert report.false_alarm_rate_pct == 100.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_noise(incident_id="INC-001")
        eng.add_pattern(pattern_name="p1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._patterns) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_patterns"] == 0
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_noise(
            incident_id="INC-001",
            noise_category=NoiseCategory.DUPLICATE,
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_incidents"] == 1
        assert "duplicate" in stats["category_distribution"]
