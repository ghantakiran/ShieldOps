"""Tests for shieldops.security.intel_sharing_orchestrator — IntelSharingOrchestrator."""

from __future__ import annotations

from shieldops.security.intel_sharing_orchestrator import (
    IntelSharingOrchestrator,
    SharingAnalysis,
    SharingLevel,
    SharingOrchestrationReport,
    SharingProtocol,
    SharingRecord,
    SharingStatus,
)


def _engine(**kw) -> IntelSharingOrchestrator:
    return IntelSharingOrchestrator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_sharingprotocol_val1(self):
        assert SharingProtocol.STIX_TAXII == "stix_taxii"

    def test_sharingprotocol_val2(self):
        assert SharingProtocol.MISP == "misp"

    def test_sharingprotocol_val3(self):
        assert SharingProtocol.OPENCTF == "openctf"

    def test_sharingprotocol_val4(self):
        assert SharingProtocol.EMAIL == "email"

    def test_sharingprotocol_val5(self):
        assert SharingProtocol.API == "api"

    def test_sharinglevel_val1(self):
        assert SharingLevel.TLP_RED == "tlp_red"

    def test_sharinglevel_val2(self):
        assert SharingLevel.TLP_AMBER == "tlp_amber"

    def test_sharinglevel_val3(self):
        assert SharingLevel.TLP_GREEN == "tlp_green"

    def test_sharinglevel_val4(self):
        assert SharingLevel.TLP_WHITE == "tlp_white"

    def test_sharinglevel_val5(self):
        assert SharingLevel.TLP_CLEAR == "tlp_clear"

    def test_sharingstatus_val1(self):
        assert SharingStatus.SHARED == "shared"

    def test_sharingstatus_val2(self):
        assert SharingStatus.PENDING == "pending"

    def test_sharingstatus_val3(self):
        assert SharingStatus.RESTRICTED == "restricted"

    def test_sharingstatus_val4(self):
        assert SharingStatus.REVOKED == "revoked"

    def test_sharingstatus_val5(self):
        assert SharingStatus.QUEUED == "queued"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = SharingRecord()
        assert r.id
        assert r.intel_name == ""
        assert r.sharing_protocol == SharingProtocol.STIX_TAXII
        assert r.share_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = SharingAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = SharingOrchestrationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_share_score == 0.0
        assert r.by_protocol == {}
        assert r.by_level == {}
        assert r.by_status == {}
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
        r = eng.record_sharing(
            intel_name="test",
            sharing_protocol=SharingProtocol.MISP,
            share_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.intel_name == "test"
        assert r.sharing_protocol == SharingProtocol.MISP
        assert r.share_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_sharing(intel_name=f"test-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_sharing(intel_name="test")
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
        eng.record_sharing(intel_name="a")
        eng.record_sharing(intel_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_sharing(intel_name="a", sharing_protocol=SharingProtocol.STIX_TAXII)
        eng.record_sharing(intel_name="b", sharing_protocol=SharingProtocol.MISP)
        results = eng.list_records(sharing_protocol=SharingProtocol.STIX_TAXII)
        assert len(results) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_sharing(intel_name="a", sharing_level=SharingLevel.TLP_RED)
        eng.record_sharing(intel_name="b", sharing_level=SharingLevel.TLP_AMBER)
        results = eng.list_records(sharing_level=SharingLevel.TLP_RED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_sharing(intel_name="a", team="sec")
        eng.record_sharing(intel_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_sharing(intel_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            intel_name="test",
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(intel_name=f"test-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_sharing(
            intel_name="a",
            sharing_protocol=SharingProtocol.STIX_TAXII,
            share_score=90.0,
        )
        eng.record_sharing(
            intel_name="b",
            sharing_protocol=SharingProtocol.STIX_TAXII,
            share_score=70.0,
        )
        result = eng.analyze_protocol_distribution()
        assert "stix_taxii" in result
        assert result["stix_taxii"]["count"] == 2
        assert result["stix_taxii"]["avg_share_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_protocol_distribution() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_sharing(intel_name="a", share_score=60.0)
        eng.record_sharing(intel_name="b", share_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["intel_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_sharing(intel_name="a", share_score=50.0)
        eng.record_sharing(intel_name="b", share_score=30.0)
        results = eng.identify_gaps()
        assert len(results) == 2
        assert results[0]["share_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_sharing(intel_name="a", service="auth-svc", share_score=90.0)
        eng.record_sharing(intel_name="b", service="api-gw", share_score=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_share_score"] == 50.0

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
            eng.add_analysis(intel_name="t", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(intel_name="t1", analysis_score=20.0)
        eng.add_analysis(intel_name="t2", analysis_score=20.0)
        eng.add_analysis(intel_name="t3", analysis_score=80.0)
        eng.add_analysis(intel_name="t4", analysis_score=80.0)
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
        eng.record_sharing(
            intel_name="test",
            sharing_protocol=SharingProtocol.MISP,
            share_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, SharingOrchestrationReport)
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
        eng.record_sharing(intel_name="test")
        eng.add_analysis(intel_name="test")
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
        assert stats["protocol_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_sharing(
            intel_name="test",
            sharing_protocol=SharingProtocol.STIX_TAXII,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "stix_taxii" in stats["protocol_distribution"]
