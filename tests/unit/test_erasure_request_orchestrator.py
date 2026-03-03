"""Tests for shieldops.compliance.erasure_request_orchestrator — ErasureRequestOrchestrator."""

from __future__ import annotations

from shieldops.compliance.erasure_request_orchestrator import (
    DataSystem,
    ErasureAnalysis,
    ErasureComplianceReport,
    ErasureRecord,
    ErasureRequestOrchestrator,
    RequestStatus,
    RequestType,
)


def _engine(**kw) -> ErasureRequestOrchestrator:
    return ErasureRequestOrchestrator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_gdpr_erasure(self):
        assert RequestType.GDPR_ERASURE == "gdpr_erasure"

    def test_type_ccpa_delete(self):
        assert RequestType.CCPA_DELETE == "ccpa_delete"

    def test_type_right_to_forget(self):
        assert RequestType.RIGHT_TO_FORGET == "right_to_forget"

    def test_type_data_portability(self):
        assert RequestType.DATA_PORTABILITY == "data_portability"

    def test_type_rectification(self):
        assert RequestType.RECTIFICATION == "rectification"

    def test_status_received(self):
        assert RequestStatus.RECEIVED == "received"

    def test_status_in_progress(self):
        assert RequestStatus.IN_PROGRESS == "in_progress"

    def test_status_completed(self):
        assert RequestStatus.COMPLETED == "completed"

    def test_status_rejected(self):
        assert RequestStatus.REJECTED == "rejected"

    def test_status_expired(self):
        assert RequestStatus.EXPIRED == "expired"

    def test_system_database(self):
        assert DataSystem.DATABASE == "database"

    def test_system_cache(self):
        assert DataSystem.CACHE == "cache"

    def test_system_backup(self):
        assert DataSystem.BACKUP == "backup"

    def test_system_analytics(self):
        assert DataSystem.ANALYTICS == "analytics"

    def test_system_third_party(self):
        assert DataSystem.THIRD_PARTY == "third_party"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_erasure_record_defaults(self):
        r = ErasureRecord()
        assert r.id
        assert r.subject_id == ""
        assert r.request_type == RequestType.GDPR_ERASURE
        assert r.request_status == RequestStatus.RECEIVED
        assert r.data_system == DataSystem.DATABASE
        assert r.completion_score == 0.0
        assert r.requester == ""
        assert r.data_owner == ""
        assert r.created_at > 0

    def test_erasure_analysis_defaults(self):
        a = ErasureAnalysis()
        assert a.id
        assert a.subject_id == ""
        assert a.request_type == RequestType.GDPR_ERASURE
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = ErasureComplianceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_completion_score == 0.0
        assert r.by_request_type == {}
        assert r.by_status == {}
        assert r.by_data_system == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_erasure / get_erasure
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_erasure(
            subject_id="user-123",
            request_type=RequestType.GDPR_ERASURE,
            request_status=RequestStatus.IN_PROGRESS,
            data_system=DataSystem.DATABASE,
            completion_score=75.0,
            requester="user-123",
            data_owner="dpo-team",
        )
        assert r.subject_id == "user-123"
        assert r.request_type == RequestType.GDPR_ERASURE
        assert r.completion_score == 75.0
        assert r.requester == "user-123"

    def test_get_found(self):
        eng = _engine()
        r = eng.record_erasure(subject_id="user-456", request_type=RequestType.CCPA_DELETE)
        result = eng.get_erasure(r.id)
        assert result is not None
        assert result.request_type == RequestType.CCPA_DELETE

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_erasure("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_erasure(subject_id=f"user-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_erasures
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_erasure(subject_id="u-001")
        eng.record_erasure(subject_id="u-002")
        assert len(eng.list_erasures()) == 2

    def test_filter_by_request_type(self):
        eng = _engine()
        eng.record_erasure(subject_id="u-001", request_type=RequestType.GDPR_ERASURE)
        eng.record_erasure(subject_id="u-002", request_type=RequestType.CCPA_DELETE)
        results = eng.list_erasures(request_type=RequestType.GDPR_ERASURE)
        assert len(results) == 1

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_erasure(subject_id="u-001", request_status=RequestStatus.RECEIVED)
        eng.record_erasure(subject_id="u-002", request_status=RequestStatus.COMPLETED)
        results = eng.list_erasures(request_status=RequestStatus.RECEIVED)
        assert len(results) == 1

    def test_filter_by_requester(self):
        eng = _engine()
        eng.record_erasure(subject_id="u-001", requester="req-a")
        eng.record_erasure(subject_id="u-002", requester="req-b")
        results = eng.list_erasures(requester="req-a")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_erasure(subject_id=f"u-{i}")
        assert len(eng.list_erasures(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            subject_id="user-123",
            request_type=RequestType.GDPR_ERASURE,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="erasure incomplete",
        )
        assert a.subject_id == "user-123"
        assert a.request_type == RequestType.GDPR_ERASURE
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(subject_id=f"u-{i}")
        assert len(eng._analyses) == 2

    def test_stored_in_analyses(self):
        eng = _engine()
        eng.add_analysis(subject_id="user-999", request_type=RequestType.RECTIFICATION)
        assert len(eng._analyses) == 1


# ---------------------------------------------------------------------------
# analyze_request_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_erasure(
            subject_id="u-001", request_type=RequestType.GDPR_ERASURE, completion_score=90.0
        )
        eng.record_erasure(
            subject_id="u-002", request_type=RequestType.GDPR_ERASURE, completion_score=70.0
        )
        result = eng.analyze_request_distribution()
        assert "gdpr_erasure" in result
        assert result["gdpr_erasure"]["count"] == 2
        assert result["gdpr_erasure"]["avg_completion_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_request_distribution() == {}


# ---------------------------------------------------------------------------
# identify_erasure_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_erasure(subject_id="u-001", completion_score=60.0)
        eng.record_erasure(subject_id="u-002", completion_score=90.0)
        results = eng.identify_erasure_gaps()
        assert len(results) == 1
        assert results[0]["subject_id"] == "u-001"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_erasure(subject_id="u-001", completion_score=50.0)
        eng.record_erasure(subject_id="u-002", completion_score=30.0)
        results = eng.identify_erasure_gaps()
        assert results[0]["completion_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_completion
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_erasure(
            subject_id="u-001", data_system=DataSystem.DATABASE, completion_score=90.0
        )
        eng.record_erasure(subject_id="u-002", data_system=DataSystem.CACHE, completion_score=50.0)
        results = eng.rank_by_completion()
        assert results[0]["data_system"] == "cache"
        assert results[0]["avg_completion_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_completion() == []


# ---------------------------------------------------------------------------
# detect_erasure_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(subject_id="u-001", analysis_score=50.0)
        result = eng.detect_erasure_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(subject_id="u-001", analysis_score=20.0)
        eng.add_analysis(subject_id="u-002", analysis_score=20.0)
        eng.add_analysis(subject_id="u-003", analysis_score=80.0)
        eng.add_analysis(subject_id="u-004", analysis_score=80.0)
        result = eng.detect_erasure_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_erasure_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_erasure(
            subject_id="user-123",
            request_type=RequestType.GDPR_ERASURE,
            request_status=RequestStatus.IN_PROGRESS,
            data_system=DataSystem.BACKUP,
            completion_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ErasureComplianceReport)
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


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_erasure(subject_id="u-001")
        eng.add_analysis(subject_id="u-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["request_type_distribution"] == {}


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=3)
        for i in range(7):
            eng.add_analysis(subject_id=f"u-{i}")
        assert len(eng._analyses) == 3
