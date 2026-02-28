"""Tests for shieldops.security.threat_hunt — ThreatHuntOrchestrator."""

from __future__ import annotations

from shieldops.security.threat_hunt import (
    HuntFinding,
    HuntRecord,
    HuntStatus,
    HuntType,
    ThreatHuntOrchestrator,
    ThreatHuntReport,
    ThreatSeverity,
)


def _engine(**kw) -> ThreatHuntOrchestrator:
    return ThreatHuntOrchestrator(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # HuntType (5)
    def test_type_hypothesis_driven(self):
        assert HuntType.HYPOTHESIS_DRIVEN == "hypothesis_driven"

    def test_type_ioc_sweep(self):
        assert HuntType.IOC_SWEEP == "ioc_sweep"

    def test_type_anomaly_based(self):
        assert HuntType.ANOMALY_BASED == "anomaly_based"

    def test_type_behavioral(self):
        assert HuntType.BEHAVIORAL == "behavioral"

    def test_type_intel_led(self):
        assert HuntType.INTEL_LED == "intel_led"

    # HuntStatus (5)
    def test_status_planning(self):
        assert HuntStatus.PLANNING == "planning"

    def test_status_active(self):
        assert HuntStatus.ACTIVE == "active"

    def test_status_analyzing(self):
        assert HuntStatus.ANALYZING == "analyzing"

    def test_status_completed(self):
        assert HuntStatus.COMPLETED == "completed"

    def test_status_archived(self):
        assert HuntStatus.ARCHIVED == "archived"

    # ThreatSeverity (5)
    def test_severity_critical(self):
        assert ThreatSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert ThreatSeverity.HIGH == "high"

    def test_severity_medium(self):
        assert ThreatSeverity.MEDIUM == "medium"

    def test_severity_low(self):
        assert ThreatSeverity.LOW == "low"

    def test_severity_informational(self):
        assert ThreatSeverity.INFORMATIONAL == "informational"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_hunt_record_defaults(self):
        r = HuntRecord()
        assert r.id
        assert r.campaign_name == ""
        assert r.hunt_type == HuntType.HYPOTHESIS_DRIVEN
        assert r.hunt_status == HuntStatus.PLANNING
        assert r.threat_severity == ThreatSeverity.MEDIUM
        assert r.findings_count == 0
        assert r.details == ""
        assert r.created_at > 0

    def test_hunt_finding_defaults(self):
        r = HuntFinding()
        assert r.id
        assert r.finding_label == ""
        assert r.hunt_type == HuntType.IOC_SWEEP
        assert r.threat_severity == ThreatSeverity.HIGH
        assert r.confidence_score == 0.0
        assert r.created_at > 0

    def test_threat_hunt_report_defaults(self):
        r = ThreatHuntReport()
        assert r.total_hunts == 0
        assert r.total_findings == 0
        assert r.detection_rate_pct == 0.0
        assert r.by_type == {}
        assert r.by_severity == {}
        assert r.critical_finding_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_hunt
# -------------------------------------------------------------------


class TestRecordHunt:
    def test_basic(self):
        eng = _engine()
        r = eng.record_hunt(
            "campaign-a",
            hunt_type=HuntType.HYPOTHESIS_DRIVEN,
            hunt_status=HuntStatus.ACTIVE,
        )
        assert r.campaign_name == "campaign-a"
        assert r.hunt_type == HuntType.HYPOTHESIS_DRIVEN

    def test_with_severity(self):
        eng = _engine()
        r = eng.record_hunt("campaign-b", threat_severity=ThreatSeverity.CRITICAL)
        assert r.threat_severity == ThreatSeverity.CRITICAL

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_hunt(f"campaign-{i}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_hunt
# -------------------------------------------------------------------


class TestGetHunt:
    def test_found(self):
        eng = _engine()
        r = eng.record_hunt("campaign-a")
        assert eng.get_hunt(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_hunt("nonexistent") is None


# -------------------------------------------------------------------
# list_hunts
# -------------------------------------------------------------------


class TestListHunts:
    def test_list_all(self):
        eng = _engine()
        eng.record_hunt("campaign-a")
        eng.record_hunt("campaign-b")
        assert len(eng.list_hunts()) == 2

    def test_filter_by_campaign(self):
        eng = _engine()
        eng.record_hunt("campaign-a")
        eng.record_hunt("campaign-b")
        results = eng.list_hunts(campaign_name="campaign-a")
        assert len(results) == 1

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_hunt("campaign-a", hunt_type=HuntType.IOC_SWEEP)
        eng.record_hunt("campaign-b", hunt_type=HuntType.BEHAVIORAL)
        results = eng.list_hunts(hunt_type=HuntType.IOC_SWEEP)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_finding
# -------------------------------------------------------------------


class TestAddFinding:
    def test_basic(self):
        eng = _engine()
        f = eng.add_finding(
            "suspicious-login",
            hunt_type=HuntType.IOC_SWEEP,
            threat_severity=ThreatSeverity.CRITICAL,
            confidence_score=0.95,
        )
        assert f.finding_label == "suspicious-login"
        assert f.confidence_score == 0.95

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_finding(f"finding-{i}")
        assert len(eng._findings) == 2


# -------------------------------------------------------------------
# analyze_hunt_effectiveness
# -------------------------------------------------------------------


class TestAnalyzeHuntEffectiveness:
    def test_with_data(self):
        eng = _engine()
        eng.record_hunt("campaign-a", threat_severity=ThreatSeverity.CRITICAL)
        eng.record_hunt("campaign-a", threat_severity=ThreatSeverity.LOW)
        result = eng.analyze_hunt_effectiveness("campaign-a")
        assert result["campaign_name"] == "campaign-a"
        assert result["total_hunts"] == 2
        assert result["detection_rate_pct"] == 50.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_hunt_effectiveness("ghost")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_low_yield_hunts
# -------------------------------------------------------------------


class TestIdentifyLowYieldHunts:
    def test_with_low_yield(self):
        eng = _engine()
        eng.record_hunt("campaign-a", findings_count=0)
        eng.record_hunt("campaign-a", findings_count=0)
        eng.record_hunt("campaign-b", findings_count=5)
        results = eng.identify_low_yield_hunts()
        assert len(results) == 1
        assert results[0]["campaign_name"] == "campaign-a"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_yield_hunts() == []


# -------------------------------------------------------------------
# rank_by_findings_count
# -------------------------------------------------------------------


class TestRankByFindingsCount:
    def test_with_data(self):
        eng = _engine()
        eng.record_hunt("campaign-a", findings_count=10)
        eng.record_hunt("campaign-a", findings_count=5)
        eng.record_hunt("campaign-b", findings_count=3)
        results = eng.rank_by_findings_count()
        assert results[0]["campaign_name"] == "campaign-a"
        assert results[0]["findings_count"] == 15

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_findings_count() == []


# -------------------------------------------------------------------
# detect_hunt_stagnation
# -------------------------------------------------------------------


class TestDetectHuntStagnation:
    def test_with_stagnation(self):
        eng = _engine()
        for _ in range(5):
            eng.record_hunt("campaign-a", hunt_status=HuntStatus.PLANNING)
        eng.record_hunt("campaign-b", hunt_status=HuntStatus.ACTIVE)
        results = eng.detect_hunt_stagnation()
        assert len(results) == 1
        assert results[0]["campaign_name"] == "campaign-a"
        assert results[0]["stagnation_detected"] is True

    def test_no_stagnation(self):
        eng = _engine()
        eng.record_hunt("campaign-a", hunt_status=HuntStatus.PLANNING)
        assert eng.detect_hunt_stagnation() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine()
        eng.record_hunt("campaign-a", threat_severity=ThreatSeverity.CRITICAL)
        eng.record_hunt("campaign-b", threat_severity=ThreatSeverity.LOW)
        eng.record_hunt("campaign-b", threat_severity=ThreatSeverity.LOW)
        eng.add_finding("finding-1")
        report = eng.generate_report()
        assert report.total_hunts == 3
        assert report.total_findings == 1
        assert report.by_type != {}
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_hunts == 0
        assert "below" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_hunt("campaign-a")
        eng.add_finding("finding-1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._findings) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_hunts"] == 0
        assert stats["total_findings"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_hunt("campaign-a", hunt_type=HuntType.HYPOTHESIS_DRIVEN)
        eng.record_hunt("campaign-b", hunt_type=HuntType.IOC_SWEEP)
        eng.add_finding("f1")
        stats = eng.get_stats()
        assert stats["total_hunts"] == 2
        assert stats["total_findings"] == 1
        assert stats["unique_campaigns"] == 2
