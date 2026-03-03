"""Tests for shieldops.security.autonomous_forensics_collector — AutonomousForensicsCollector."""

from __future__ import annotations

from shieldops.security.autonomous_forensics_collector import (
    AutonomousForensicsCollector,
    AutonomousForensicsCollectorAnalysis,
    AutonomousForensicsCollectorRecord,
    AutonomousForensicsCollectorReport,
    ChainOfCustody,
    CollectionMethod,
    EvidenceType,
)


def _engine(**kw) -> AutonomousForensicsCollector:
    return AutonomousForensicsCollector(**kw)


class TestEnums:
    def test_evidence_type_first(self):
        assert EvidenceType.MEMORY_DUMP == "memory_dump"

    def test_evidence_type_second(self):
        assert EvidenceType.DISK_IMAGE == "disk_image"

    def test_evidence_type_third(self):
        assert EvidenceType.NETWORK_CAPTURE == "network_capture"

    def test_evidence_type_fourth(self):
        assert EvidenceType.LOG_BUNDLE == "log_bundle"

    def test_evidence_type_fifth(self):
        assert EvidenceType.REGISTRY == "registry"

    def test_collection_method_first(self):
        assert CollectionMethod.LIVE == "live"

    def test_collection_method_second(self):
        assert CollectionMethod.OFFLINE == "offline"

    def test_collection_method_third(self):
        assert CollectionMethod.REMOTE == "remote"

    def test_collection_method_fourth(self):
        assert CollectionMethod.AGENT_BASED == "agent_based"

    def test_collection_method_fifth(self):
        assert CollectionMethod.API == "api"

    def test_chain_of_custody_first(self):
        assert ChainOfCustody.VERIFIED == "verified"

    def test_chain_of_custody_second(self):
        assert ChainOfCustody.PENDING == "pending"

    def test_chain_of_custody_third(self):
        assert ChainOfCustody.BROKEN == "broken"

    def test_chain_of_custody_fourth(self):
        assert ChainOfCustody.NOT_APPLICABLE == "not_applicable"

    def test_chain_of_custody_fifth(self):
        assert ChainOfCustody.UNKNOWN == "unknown"


class TestModels:
    def test_record_defaults(self):
        r = AutonomousForensicsCollectorRecord()
        assert r.id
        assert r.name == ""
        assert r.evidence_type == EvidenceType.MEMORY_DUMP
        assert r.collection_method == CollectionMethod.LIVE
        assert r.chain_of_custody == ChainOfCustody.VERIFIED
        assert r.score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = AutonomousForensicsCollectorAnalysis()
        assert a.id
        assert a.name == ""
        assert a.evidence_type == EvidenceType.MEMORY_DUMP
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = AutonomousForensicsCollectorReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_score == 0.0
        assert r.by_evidence_type == {}
        assert r.by_collection_method == {}
        assert r.by_chain_of_custody == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            evidence_type=EvidenceType.MEMORY_DUMP,
            collection_method=CollectionMethod.OFFLINE,
            chain_of_custody=ChainOfCustody.BROKEN,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.evidence_type == EvidenceType.MEMORY_DUMP
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_item(name="a")
        eng.record_item(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_evidence_type(self):
        eng = _engine()
        eng.record_item(name="a", evidence_type=EvidenceType.DISK_IMAGE)
        eng.record_item(name="b", evidence_type=EvidenceType.MEMORY_DUMP)
        assert len(eng.list_records(evidence_type=EvidenceType.DISK_IMAGE)) == 1

    def test_filter_by_collection_method(self):
        eng = _engine()
        eng.record_item(name="a", collection_method=CollectionMethod.LIVE)
        eng.record_item(name="b", collection_method=CollectionMethod.OFFLINE)
        assert len(eng.list_records(collection_method=CollectionMethod.LIVE)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_item(name="a", team="sec")
        eng.record_item(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_item(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="test analysis",
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
        eng.record_item(name="a", evidence_type=EvidenceType.DISK_IMAGE, score=90.0)
        eng.record_item(name="b", evidence_type=EvidenceType.DISK_IMAGE, score=70.0)
        result = eng.analyze_distribution()
        assert "disk_image" in result
        assert result["disk_image"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=60.0)
        eng.record_item(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=50.0)
        eng.record_item(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_item(name="a", service="auth", score=90.0)
        eng.record_item(name="b", service="api", score=50.0)
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
        eng.record_item(name="test", score=50.0)
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
        eng.record_item(name="test")
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
        eng.record_item(name="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
