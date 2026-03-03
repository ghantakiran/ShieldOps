"""Tests for shieldops.security.threat_hunting_intelligence — ThreatHuntingIntelligence."""

from __future__ import annotations

from shieldops.security.threat_hunting_intelligence import (
    HuntAnalysis,
    HuntOutcome,
    HuntRecord,
    HuntSource,
    HuntType,
    ThreatHuntingIntelligence,
    ThreatHuntingReport,
)


def _engine(**kw) -> ThreatHuntingIntelligence:
    return ThreatHuntingIntelligence(**kw)


class TestEnums:
    def test_hunt_type_hypothesis_driven(self):
        assert HuntType.HYPOTHESIS_DRIVEN == "hypothesis_driven"

    def test_hunt_type_ioc_sweep(self):
        assert HuntType.IOC_SWEEP == "ioc_sweep"

    def test_hunt_type_behavioral(self):
        assert HuntType.BEHAVIORAL == "behavioral"

    def test_hunt_type_baseline(self):
        assert HuntType.BASELINE == "baseline"

    def test_hunt_type_campaign(self):
        assert HuntType.CAMPAIGN == "campaign"

    def test_hunt_source_threat_intel(self):
        assert HuntSource.THREAT_INTEL == "threat_intel"

    def test_hunt_source_incident_history(self):
        assert HuntSource.INCIDENT_HISTORY == "incident_history"

    def test_hunt_source_anomaly_detection(self):
        assert HuntSource.ANOMALY_DETECTION == "anomaly_detection"

    def test_hunt_source_analyst(self):
        assert HuntSource.ANALYST == "analyst"

    def test_hunt_source_automated(self):
        assert HuntSource.AUTOMATED == "automated"

    def test_hunt_outcome_confirmed_threat(self):
        assert HuntOutcome.CONFIRMED_THREAT == "confirmed_threat"

    def test_hunt_outcome_suspicious(self):
        assert HuntOutcome.SUSPICIOUS == "suspicious"

    def test_hunt_outcome_benign(self):
        assert HuntOutcome.BENIGN == "benign"

    def test_hunt_outcome_inconclusive(self):
        assert HuntOutcome.INCONCLUSIVE == "inconclusive"

    def test_hunt_outcome_false_positive(self):
        assert HuntOutcome.FALSE_POSITIVE == "false_positive"


class TestModels:
    def test_record_defaults(self):
        r = HuntRecord()
        assert r.id
        assert r.name == ""
        assert r.hunt_type == HuntType.HYPOTHESIS_DRIVEN
        assert r.hunt_source == HuntSource.THREAT_INTEL
        assert r.hunt_outcome == HuntOutcome.FALSE_POSITIVE
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = HuntAnalysis()
        assert a.id
        assert a.name == ""
        assert a.hunt_type == HuntType.HYPOTHESIS_DRIVEN
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ThreatHuntingReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_hunt_type == {}
        assert r.by_hunt_source == {}
        assert r.by_hunt_outcome == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            hunt_type=HuntType.HYPOTHESIS_DRIVEN,
            hunt_source=HuntSource.INCIDENT_HISTORY,
            hunt_outcome=HuntOutcome.CONFIRMED_THREAT,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.hunt_type == HuntType.HYPOTHESIS_DRIVEN
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_entry(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_entry(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_entry(name="a")
        eng.record_entry(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_hunt_type(self):
        eng = _engine()
        eng.record_entry(name="a", hunt_type=HuntType.HYPOTHESIS_DRIVEN)
        eng.record_entry(name="b", hunt_type=HuntType.IOC_SWEEP)
        assert len(eng.list_records(hunt_type=HuntType.HYPOTHESIS_DRIVEN)) == 1

    def test_filter_by_hunt_source(self):
        eng = _engine()
        eng.record_entry(name="a", hunt_source=HuntSource.THREAT_INTEL)
        eng.record_entry(name="b", hunt_source=HuntSource.INCIDENT_HISTORY)
        assert len(eng.list_records(hunt_source=HuntSource.THREAT_INTEL)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_entry(name="a", team="sec")
        eng.record_entry(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_entry(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="confirmed issue",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_entry(name="a", hunt_type=HuntType.IOC_SWEEP, score=90.0)
        eng.record_entry(name="b", hunt_type=HuntType.IOC_SWEEP, score=70.0)
        result = eng.analyze_distribution()
        assert "ioc_sweep" in result
        assert result["ioc_sweep"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=60.0)
        eng.record_entry(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="a", score=50.0)
        eng.record_entry(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_entry(name="a", service="auth", score=90.0)
        eng.record_entry(name="b", service="api", score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(name="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(name="a", analysis_score=20.0)
        eng.add_analysis(name="b", analysis_score=20.0)
        eng.add_analysis(name="c", analysis_score=80.0)
        eng.add_analysis(name="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_entry(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_entry(name="test")
        eng.add_analysis(name="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_entry(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
