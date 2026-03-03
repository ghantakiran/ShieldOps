"""Tests for shieldops.security.artifact_scanning_orchestrator."""

from __future__ import annotations

from shieldops.security.artifact_scanning_orchestrator import (
    ArtifactScanningOrchestrator,
    ArtifactScanningReport,
    OrchestratorAction,
    ScanAnalysis,
    ScanPriority,
    ScanRecord,
    ScanType,
)


def _engine(**kw) -> ArtifactScanningOrchestrator:
    return ArtifactScanningOrchestrator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_scan_type_vulnerability(self):
        assert ScanType.VULNERABILITY == "vulnerability"

    def test_scan_type_license(self):
        assert ScanType.LICENSE == "license"

    def test_scan_type_secret(self):
        assert ScanType.SECRET == "secret"  # noqa: S105

    def test_scan_type_malware(self):
        assert ScanType.MALWARE == "malware"

    def test_scan_type_compliance(self):
        assert ScanType.COMPLIANCE == "compliance"

    def test_priority_critical(self):
        assert ScanPriority.CRITICAL == "critical"

    def test_priority_high(self):
        assert ScanPriority.HIGH == "high"

    def test_priority_medium(self):
        assert ScanPriority.MEDIUM == "medium"

    def test_priority_low(self):
        assert ScanPriority.LOW == "low"

    def test_priority_background(self):
        assert ScanPriority.BACKGROUND == "background"

    def test_action_scan(self):
        assert OrchestratorAction.SCAN == "scan"

    def test_action_rescan(self):
        assert OrchestratorAction.RESCAN == "rescan"

    def test_action_skip(self):
        assert OrchestratorAction.SKIP == "skip"

    def test_action_quarantine(self):
        assert OrchestratorAction.QUARANTINE == "quarantine"

    def test_action_approve(self):
        assert OrchestratorAction.APPROVE == "approve"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_scan_record_defaults(self):
        r = ScanRecord()
        assert r.id
        assert r.artifact_name == ""
        assert r.scan_type == ScanType.VULNERABILITY
        assert r.scan_priority == ScanPriority.MEDIUM
        assert r.orchestrator_action == OrchestratorAction.SCAN
        assert r.scan_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_scan_analysis_defaults(self):
        c = ScanAnalysis()
        assert c.id
        assert c.artifact_name == ""
        assert c.scan_type == ScanType.VULNERABILITY
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_artifact_scanning_report_defaults(self):
        r = ArtifactScanningReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_scan_score == 0.0
        assert r.by_scan_type == {}
        assert r.by_priority == {}
        assert r.by_action == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_scan / get / list
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_scan(
            artifact_name="my-svc:v1",
            scan_type=ScanType.VULNERABILITY,
            scan_priority=ScanPriority.HIGH,
            orchestrator_action=OrchestratorAction.QUARANTINE,
            scan_score=85.0,
            service="ci-cd",
            team="security",
        )
        assert r.artifact_name == "my-svc:v1"
        assert r.scan_type == ScanType.VULNERABILITY
        assert r.scan_priority == ScanPriority.HIGH
        assert r.orchestrator_action == OrchestratorAction.QUARANTINE
        assert r.scan_score == 85.0

    def test_get_found(self):
        eng = _engine()
        r = eng.record_scan(artifact_name="lib.whl", scan_score=70.0)
        result = eng.get_scan(r.id)
        assert result is not None
        assert result.scan_score == 70.0

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_scan("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_scan(artifact_name=f"art-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_scans
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_scan(artifact_name="a")
        eng.record_scan(artifact_name="b")
        assert len(eng.list_scans()) == 2

    def test_filter_by_scan_type(self):
        eng = _engine()
        eng.record_scan(artifact_name="a", scan_type=ScanType.VULNERABILITY)
        eng.record_scan(artifact_name="b", scan_type=ScanType.LICENSE)
        results = eng.list_scans(scan_type=ScanType.VULNERABILITY)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_scan(artifact_name="a", team="security")
        eng.record_scan(artifact_name="b", team="platform")
        results = eng.list_scans(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_scan(artifact_name=f"art-{i}")
        assert len(eng.list_scans(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            artifact_name="my-svc:v1",
            scan_type=ScanType.MALWARE,
            analysis_score=90.0,
            threshold=80.0,
            breached=True,
            description="malware detected",
        )
        assert a.artifact_name == "my-svc:v1"
        assert a.scan_type == ScanType.MALWARE
        assert a.analysis_score == 90.0
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(artifact_name=f"art-{i}")
        assert len(eng._analyses) == 2

    def test_filter_by_priority(self):
        eng = _engine()
        eng.record_scan(artifact_name="a", scan_priority=ScanPriority.CRITICAL)
        eng.record_scan(artifact_name="b", scan_priority=ScanPriority.LOW)
        results = eng.list_scans(scan_priority=ScanPriority.CRITICAL)
        assert len(results) == 1


# ---------------------------------------------------------------------------
# analyze_scan_type_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_scan(artifact_name="a", scan_type=ScanType.VULNERABILITY, scan_score=90.0)
        eng.record_scan(artifact_name="b", scan_type=ScanType.VULNERABILITY, scan_score=70.0)
        result = eng.analyze_scan_type_distribution()
        assert "vulnerability" in result
        assert result["vulnerability"]["count"] == 2
        assert result["vulnerability"]["avg_scan_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_scan_type_distribution() == {}


# ---------------------------------------------------------------------------
# identify_scan_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(scan_gap_threshold=70.0)
        eng.record_scan(artifact_name="a", scan_score=50.0)
        eng.record_scan(artifact_name="b", scan_score=80.0)
        results = eng.identify_scan_gaps()
        assert len(results) == 1
        assert results[0]["artifact_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(scan_gap_threshold=80.0)
        eng.record_scan(artifact_name="a", scan_score=50.0)
        eng.record_scan(artifact_name="b", scan_score=20.0)
        results = eng.identify_scan_gaps()
        assert len(results) == 2
        assert results[0]["scan_score"] == 20.0


# ---------------------------------------------------------------------------
# rank_by_scan_score
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_scan(artifact_name="a", service="ci-cd", scan_score=90.0)
        eng.record_scan(artifact_name="b", service="deploy", scan_score=40.0)
        results = eng.rank_by_scan_score()
        assert len(results) == 2
        assert results[0]["service"] == "deploy"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_scan_score() == []


# ---------------------------------------------------------------------------
# detect_scan_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(artifact_name="art", analysis_score=50.0)
        result = eng.detect_scan_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(artifact_name="art", analysis_score=20.0)
        eng.add_analysis(artifact_name="art", analysis_score=20.0)
        eng.add_analysis(artifact_name="art", analysis_score=80.0)
        eng.add_analysis(artifact_name="art", analysis_score=80.0)
        result = eng.detect_scan_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_scan_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(scan_gap_threshold=60.0)
        eng.record_scan(
            artifact_name="svc:v1",
            scan_type=ScanType.MALWARE,
            scan_priority=ScanPriority.CRITICAL,
            scan_score=40.0,
        )
        report = eng.generate_report()
        assert isinstance(report, ArtifactScanningReport)
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
        eng.record_scan(artifact_name="art")
        eng.add_analysis(artifact_name="art")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats(self):
        eng = _engine()
        eng.record_scan(
            artifact_name="art",
            scan_type=ScanType.VULNERABILITY,
            service="ci-cd",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "vulnerability" in stats["scan_type_distribution"]


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_records_evicted_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.record_scan(artifact_name=f"art-{i}")
        assert len(eng._records) == 2
        assert eng._records[-1].artifact_name == "art-4"
