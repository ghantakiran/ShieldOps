"""Tests for shieldops.security.response_coordination_engine — ResponseCoordinationEngine."""

from __future__ import annotations

from shieldops.security.response_coordination_engine import (
    CoordinationAnalysis,
    CoordinationRecord,
    CoordinationStatus,
    CoordinationTarget,
    ResponseAction,
    ResponseCoordinationEngine,
    ResponseCoordinationReport,
)


def _engine(**kw) -> ResponseCoordinationEngine:
    return ResponseCoordinationEngine(**kw)


class TestEnums:
    def test_response_action_isolate(self):
        assert ResponseAction.ISOLATE == "isolate"

    def test_response_action_block(self):
        assert ResponseAction.BLOCK == "block"

    def test_response_action_contain(self):
        assert ResponseAction.CONTAIN == "contain"

    def test_response_action_remediate(self):
        assert ResponseAction.REMEDIATE == "remediate"

    def test_response_action_restore(self):
        assert ResponseAction.RESTORE == "restore"

    def test_coordination_target_endpoint(self):
        assert CoordinationTarget.ENDPOINT == "endpoint"

    def test_coordination_target_network(self):
        assert CoordinationTarget.NETWORK == "network"

    def test_coordination_target_identity(self):
        assert CoordinationTarget.IDENTITY == "identity"

    def test_coordination_target_cloud(self):
        assert CoordinationTarget.CLOUD == "cloud"

    def test_coordination_target_application(self):
        assert CoordinationTarget.APPLICATION == "application"

    def test_coordination_status_executed(self):
        assert CoordinationStatus.EXECUTED == "executed"

    def test_coordination_status_pending(self):
        assert CoordinationStatus.PENDING == "pending"

    def test_coordination_status_failed(self):
        assert CoordinationStatus.FAILED == "failed"

    def test_coordination_status_rolled_back(self):
        assert CoordinationStatus.ROLLED_BACK == "rolled_back"

    def test_coordination_status_skipped(self):
        assert CoordinationStatus.SKIPPED == "skipped"


class TestModels:
    def test_record_defaults(self):
        r = CoordinationRecord()
        assert r.id
        assert r.name == ""
        assert r.response_action == ResponseAction.ISOLATE
        assert r.coordination_target == CoordinationTarget.ENDPOINT
        assert r.coordination_status == CoordinationStatus.SKIPPED
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = CoordinationAnalysis()
        assert a.id
        assert a.name == ""
        assert a.response_action == ResponseAction.ISOLATE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ResponseCoordinationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_response_action == {}
        assert r.by_coordination_target == {}
        assert r.by_coordination_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_entry(
            name="test-001",
            response_action=ResponseAction.ISOLATE,
            coordination_target=CoordinationTarget.NETWORK,
            coordination_status=CoordinationStatus.EXECUTED,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.response_action == ResponseAction.ISOLATE
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

    def test_filter_by_response_action(self):
        eng = _engine()
        eng.record_entry(name="a", response_action=ResponseAction.ISOLATE)
        eng.record_entry(name="b", response_action=ResponseAction.BLOCK)
        assert len(eng.list_records(response_action=ResponseAction.ISOLATE)) == 1

    def test_filter_by_coordination_target(self):
        eng = _engine()
        eng.record_entry(name="a", coordination_target=CoordinationTarget.ENDPOINT)
        eng.record_entry(name="b", coordination_target=CoordinationTarget.NETWORK)
        assert len(eng.list_records(coordination_target=CoordinationTarget.ENDPOINT)) == 1

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
        eng.record_entry(name="a", response_action=ResponseAction.BLOCK, score=90.0)
        eng.record_entry(name="b", response_action=ResponseAction.BLOCK, score=70.0)
        result = eng.analyze_distribution()
        assert "block" in result
        assert result["block"]["count"] == 2

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
