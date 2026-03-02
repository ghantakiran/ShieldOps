"""Tests for shieldops.security.ioc_lifecycle_manager — IOCLifecycleManager."""

from __future__ import annotations

from shieldops.security.ioc_lifecycle_manager import (
    IOCAnalysis,
    IOCConfidence,
    IOCLifecycleManager,
    IOCLifecycleReport,
    IOCRecord,
    IOCStatus,
    IOCType,
)


def _engine(**kw) -> IOCLifecycleManager:
    return IOCLifecycleManager(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_ioctype_val1(self):
        assert IOCType.IP_ADDRESS == "ip_address"

    def test_ioctype_val2(self):
        assert IOCType.DOMAIN == "domain"

    def test_ioctype_val3(self):
        assert IOCType.FILE_HASH == "file_hash"

    def test_ioctype_val4(self):
        assert IOCType.URL == "url"

    def test_ioctype_val5(self):
        assert IOCType.EMAIL == "email"

    def test_iocstatus_val1(self):
        assert IOCStatus.ACTIVE == "active"

    def test_iocstatus_val2(self):
        assert IOCStatus.EXPIRED == "expired"

    def test_iocstatus_val3(self):
        assert IOCStatus.REVOKED == "revoked"

    def test_iocstatus_val4(self):
        assert IOCStatus.DEPRECATED == "deprecated"

    def test_iocstatus_val5(self):
        assert IOCStatus.QUARANTINED == "quarantined"

    def test_iocconfidence_val1(self):
        assert IOCConfidence.CONFIRMED == "confirmed"

    def test_iocconfidence_val2(self):
        assert IOCConfidence.HIGH == "high"

    def test_iocconfidence_val3(self):
        assert IOCConfidence.MEDIUM == "medium"

    def test_iocconfidence_val4(self):
        assert IOCConfidence.LOW == "low"

    def test_iocconfidence_val5(self):
        assert IOCConfidence.UNVERIFIED == "unverified"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = IOCRecord()
        assert r.id
        assert r.ioc_value == ""
        assert r.ioc_type == IOCType.IP_ADDRESS
        assert r.relevance_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = IOCAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = IOCLifecycleReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_relevance_score == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.by_confidence == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_ioc(
            ioc_value="test",
            ioc_type=IOCType.DOMAIN,
            relevance_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.ioc_value == "test"
        assert r.ioc_type == IOCType.DOMAIN
        assert r.relevance_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_ioc(ioc_value=f"test-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_ioc(ioc_value="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


# ---------------------------------------------------------------------------
# list_records
# ---------------------------------------------------------------------------


class TestListRecords:
    def test_list_all(self):
        eng = _engine()
        eng.record_ioc(ioc_value="a")
        eng.record_ioc(ioc_value="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_ioc(ioc_value="a", ioc_type=IOCType.IP_ADDRESS)
        eng.record_ioc(ioc_value="b", ioc_type=IOCType.DOMAIN)
        results = eng.list_records(ioc_type=IOCType.IP_ADDRESS)
        assert len(results) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_ioc(ioc_value="a", ioc_status=IOCStatus.ACTIVE)
        eng.record_ioc(ioc_value="b", ioc_status=IOCStatus.EXPIRED)
        results = eng.list_records(ioc_status=IOCStatus.ACTIVE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_ioc(ioc_value="a", team="sec")
        eng.record_ioc(ioc_value="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_ioc(ioc_value=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            ioc_value="test",
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(ioc_value=f"test-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_ioc(
            ioc_value="a",
            ioc_type=IOCType.IP_ADDRESS,
            relevance_score=90.0,
        )
        eng.record_ioc(
            ioc_value="b",
            ioc_type=IOCType.IP_ADDRESS,
            relevance_score=70.0,
        )
        result = eng.analyze_type_distribution()
        assert "ip_address" in result
        assert result["ip_address"]["count"] == 2
        assert result["ip_address"]["avg_relevance_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_type_distribution() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_ioc(ioc_value="a", relevance_score=60.0)
        eng.record_ioc(ioc_value="b", relevance_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["ioc_value"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_ioc(ioc_value="a", relevance_score=50.0)
        eng.record_ioc(ioc_value="b", relevance_score=30.0)
        results = eng.identify_gaps()
        assert len(results) == 2
        assert results[0]["relevance_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_ioc(ioc_value="a", service="auth-svc", relevance_score=90.0)
        eng.record_ioc(ioc_value="b", service="api-gw", relevance_score=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_relevance_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


# ---------------------------------------------------------------------------
# detect_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(ioc_value="t", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(ioc_value="t1", analysis_score=20.0)
        eng.add_analysis(ioc_value="t2", analysis_score=20.0)
        eng.add_analysis(ioc_value="t3", analysis_score=80.0)
        eng.add_analysis(ioc_value="t4", analysis_score=80.0)
        result = eng.detect_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_ioc(
            ioc_value="test",
            ioc_type=IOCType.DOMAIN,
            relevance_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, IOCLifecycleReport)
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.top_gaps) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "healthy" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_ioc(ioc_value="test")
        eng.add_analysis(ioc_value="test")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_ioc(
            ioc_value="test",
            ioc_type=IOCType.IP_ADDRESS,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "ip_address" in stats["type_distribution"]
