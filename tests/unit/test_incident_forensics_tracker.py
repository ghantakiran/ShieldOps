"""Tests for shieldops.incidents.incident_forensics_tracker — IncidentForensicsTracker."""

from __future__ import annotations

from shieldops.incidents.incident_forensics_tracker import (
    CustodyStatus,
    EvidenceCategory,
    ForensicAnalysis,
    ForensicRecord,
    ForensicsReport,
    IncidentForensicsTracker,
    IntegrityLevel,
)


def _engine(**kw) -> IncidentForensicsTracker:
    return IncidentForensicsTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_category_memory_dump(self):
        assert EvidenceCategory.MEMORY_DUMP == "memory_dump"

    def test_category_disk_image(self):
        assert EvidenceCategory.DISK_IMAGE == "disk_image"

    def test_category_network_capture(self):
        assert EvidenceCategory.NETWORK_CAPTURE == "network_capture"

    def test_category_log_artifact(self):
        assert EvidenceCategory.LOG_ARTIFACT == "log_artifact"

    def test_category_registry_snapshot(self):
        assert EvidenceCategory.REGISTRY_SNAPSHOT == "registry_snapshot"

    def test_custody_preserved(self):
        assert CustodyStatus.PRESERVED == "preserved"

    def test_custody_in_analysis(self):
        assert CustodyStatus.IN_ANALYSIS == "in_analysis"

    def test_custody_transferred(self):
        assert CustodyStatus.TRANSFERRED == "transferred"

    def test_custody_archived(self):
        assert CustodyStatus.ARCHIVED == "archived"

    def test_custody_compromised(self):
        assert CustodyStatus.COMPROMISED == "compromised"

    def test_integrity_verified(self):
        assert IntegrityLevel.VERIFIED == "verified"

    def test_integrity_pending_verification(self):
        assert IntegrityLevel.PENDING_VERIFICATION == "pending_verification"

    def test_integrity_tamper_detected(self):
        assert IntegrityLevel.TAMPER_DETECTED == "tamper_detected"

    def test_integrity_hash_mismatch(self):
        assert IntegrityLevel.HASH_MISMATCH == "hash_mismatch"

    def test_integrity_unknown(self):
        assert IntegrityLevel.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_forensic_record_defaults(self):
        r = ForensicRecord()
        assert r.id
        assert r.artifact_name == ""
        assert r.evidence_category == EvidenceCategory.MEMORY_DUMP
        assert r.custody_status == CustodyStatus.PRESERVED
        assert r.integrity_level == IntegrityLevel.VERIFIED
        assert r.integrity_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_forensic_analysis_defaults(self):
        c = ForensicAnalysis()
        assert c.id
        assert c.artifact_name == ""
        assert c.evidence_category == EvidenceCategory.MEMORY_DUMP
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_forensics_report_defaults(self):
        r = ForensicsReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_integrity_count == 0
        assert r.avg_integrity_score == 0.0
        assert r.by_category == {}
        assert r.by_custody == {}
        assert r.by_integrity == {}
        assert r.top_low_integrity == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_artifact
# ---------------------------------------------------------------------------


class TestRecordArtifact:
    def test_basic(self):
        eng = _engine()
        r = eng.record_artifact(
            artifact_name="host-memory-dump-001",
            evidence_category=EvidenceCategory.DISK_IMAGE,
            custody_status=CustodyStatus.IN_ANALYSIS,
            integrity_level=IntegrityLevel.PENDING_VERIFICATION,
            integrity_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.artifact_name == "host-memory-dump-001"
        assert r.evidence_category == EvidenceCategory.DISK_IMAGE
        assert r.custody_status == CustodyStatus.IN_ANALYSIS
        assert r.integrity_level == IntegrityLevel.PENDING_VERIFICATION
        assert r.integrity_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_artifact(artifact_name=f"ART-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_artifact
# ---------------------------------------------------------------------------


class TestGetArtifact:
    def test_found(self):
        eng = _engine()
        r = eng.record_artifact(
            artifact_name="host-memory-dump-001",
            integrity_level=IntegrityLevel.VERIFIED,
        )
        result = eng.get_artifact(r.id)
        assert result is not None
        assert result.integrity_level == IntegrityLevel.VERIFIED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_artifact("nonexistent") is None


# ---------------------------------------------------------------------------
# list_artifacts
# ---------------------------------------------------------------------------


class TestListArtifacts:
    def test_list_all(self):
        eng = _engine()
        eng.record_artifact(artifact_name="ART-001")
        eng.record_artifact(artifact_name="ART-002")
        assert len(eng.list_artifacts()) == 2

    def test_filter_by_evidence_category(self):
        eng = _engine()
        eng.record_artifact(
            artifact_name="ART-001",
            evidence_category=EvidenceCategory.MEMORY_DUMP,
        )
        eng.record_artifact(
            artifact_name="ART-002",
            evidence_category=EvidenceCategory.NETWORK_CAPTURE,
        )
        results = eng.list_artifacts(
            evidence_category=EvidenceCategory.MEMORY_DUMP,
        )
        assert len(results) == 1

    def test_filter_by_custody_status(self):
        eng = _engine()
        eng.record_artifact(
            artifact_name="ART-001",
            custody_status=CustodyStatus.PRESERVED,
        )
        eng.record_artifact(
            artifact_name="ART-002",
            custody_status=CustodyStatus.ARCHIVED,
        )
        results = eng.list_artifacts(
            custody_status=CustodyStatus.PRESERVED,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_artifact(artifact_name="ART-001", team="security")
        eng.record_artifact(artifact_name="ART-002", team="platform")
        results = eng.list_artifacts(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_artifact(artifact_name=f"ART-{i}")
        assert len(eng.list_artifacts(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            artifact_name="host-memory-dump-001",
            evidence_category=EvidenceCategory.DISK_IMAGE,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="low integrity detected",
        )
        assert a.artifact_name == "host-memory-dump-001"
        assert a.evidence_category == EvidenceCategory.DISK_IMAGE
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(artifact_name=f"ART-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_category_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeCategoryDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_artifact(
            artifact_name="ART-001",
            evidence_category=EvidenceCategory.MEMORY_DUMP,
            integrity_score=90.0,
        )
        eng.record_artifact(
            artifact_name="ART-002",
            evidence_category=EvidenceCategory.MEMORY_DUMP,
            integrity_score=70.0,
        )
        result = eng.analyze_category_distribution()
        assert "memory_dump" in result
        assert result["memory_dump"]["count"] == 2
        assert result["memory_dump"]["avg_integrity_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_category_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_integrity_artifacts
# ---------------------------------------------------------------------------


class TestIdentifyLowIntegrityArtifacts:
    def test_detects_below_threshold(self):
        eng = _engine(integrity_threshold=90.0)
        eng.record_artifact(artifact_name="ART-001", integrity_score=60.0)
        eng.record_artifact(artifact_name="ART-002", integrity_score=95.0)
        results = eng.identify_low_integrity_artifacts()
        assert len(results) == 1
        assert results[0]["artifact_name"] == "ART-001"

    def test_sorted_ascending(self):
        eng = _engine(integrity_threshold=90.0)
        eng.record_artifact(artifact_name="ART-001", integrity_score=50.0)
        eng.record_artifact(artifact_name="ART-002", integrity_score=30.0)
        results = eng.identify_low_integrity_artifacts()
        assert len(results) == 2
        assert results[0]["integrity_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_integrity_artifacts() == []


# ---------------------------------------------------------------------------
# rank_by_integrity
# ---------------------------------------------------------------------------


class TestRankByIntegrity:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_artifact(artifact_name="ART-001", service="auth-svc", integrity_score=90.0)
        eng.record_artifact(artifact_name="ART-002", service="api-gw", integrity_score=50.0)
        results = eng.rank_by_integrity()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_integrity_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_integrity() == []


# ---------------------------------------------------------------------------
# detect_integrity_trends
# ---------------------------------------------------------------------------


class TestDetectIntegrityTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(artifact_name="ART-001", analysis_score=50.0)
        result = eng.detect_integrity_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(artifact_name="ART-001", analysis_score=20.0)
        eng.add_analysis(artifact_name="ART-002", analysis_score=20.0)
        eng.add_analysis(artifact_name="ART-003", analysis_score=80.0)
        eng.add_analysis(artifact_name="ART-004", analysis_score=80.0)
        result = eng.detect_integrity_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_integrity_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(integrity_threshold=90.0)
        eng.record_artifact(
            artifact_name="host-memory-dump-001",
            evidence_category=EvidenceCategory.DISK_IMAGE,
            custody_status=CustodyStatus.IN_ANALYSIS,
            integrity_level=IntegrityLevel.PENDING_VERIFICATION,
            integrity_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ForensicsReport)
        assert report.total_records == 1
        assert report.low_integrity_count == 1
        assert len(report.top_low_integrity) == 1
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
        eng.record_artifact(artifact_name="ART-001")
        eng.add_analysis(artifact_name="ART-001")
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
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_artifact(
            artifact_name="ART-001",
            evidence_category=EvidenceCategory.MEMORY_DUMP,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "memory_dump" in stats["category_distribution"]
