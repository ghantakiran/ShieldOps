"""Tests for shieldops.security.apt_detection_engine — APTDetectionEngine."""

from __future__ import annotations

from shieldops.security.apt_detection_engine import (
    APTAnalysis,
    APTDetectionEngine,
    APTIndicator,
    APTRecord,
    APTReport,
    APTStage,
    DetectionSource,
)


def _engine(**kw) -> APTDetectionEngine:
    return APTDetectionEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_aptindicator_long_dwell(self):
        assert APTIndicator.LONG_DWELL == "long_dwell"

    def test_aptindicator_slow_exfiltration(self):
        assert APTIndicator.SLOW_EXFILTRATION == "slow_exfiltration"

    def test_aptindicator_living_off_land(self):
        assert APTIndicator.LIVING_OFF_LAND == "living_off_land"

    def test_aptindicator_credential_theft(self):
        assert APTIndicator.CREDENTIAL_THEFT == "credential_theft"

    def test_aptindicator_persistence_mechanism(self):
        assert APTIndicator.PERSISTENCE_MECHANISM == "persistence_mechanism"

    def test_aptstage_initial_compromise(self):
        assert APTStage.INITIAL_COMPROMISE == "initial_compromise"

    def test_aptstage_establish_foothold(self):
        assert APTStage.ESTABLISH_FOOTHOLD == "establish_foothold"

    def test_aptstage_escalate_privilege(self):
        assert APTStage.ESCALATE_PRIVILEGE == "escalate_privilege"

    def test_aptstage_internal_recon(self):
        assert APTStage.INTERNAL_RECON == "internal_recon"

    def test_aptstage_mission_complete(self):
        assert APTStage.MISSION_COMPLETE == "mission_complete"

    def test_detectionsource_edr(self):
        assert DetectionSource.EDR == "edr"

    def test_detectionsource_network(self):
        assert DetectionSource.NETWORK == "network"

    def test_detectionsource_siem(self):
        assert DetectionSource.SIEM == "siem"

    def test_detectionsource_threat_intel(self):
        assert DetectionSource.THREAT_INTEL == "threat_intel"

    def test_detectionsource_behavioral_analytics(self):
        assert DetectionSource.BEHAVIORAL_ANALYTICS == "behavioral_analytics"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_aptrecord_defaults(self):
        r = APTRecord()
        assert r.id
        assert r.campaign_name == ""
        assert r.threat_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_aptanalysis_defaults(self):
        c = APTAnalysis()
        assert c.id
        assert c.campaign_name == ""
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached == 0.0
        assert c.description == ""
        assert c.created_at > 0

    def test_aptreport_defaults(self):
        r = APTReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_threat_count == 0
        assert r.avg_threat_score == 0
        assert r.by_indicator == {}
        assert r.by_stage == {}
        assert r.by_source == {}
        assert r.top_high_threat == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_detection
# ---------------------------------------------------------------------------


class TestRecordDetection:
    def test_basic(self):
        eng = _engine()
        r = eng.record_detection(
            campaign_name="test-item",
            apt_indicator=APTIndicator.SLOW_EXFILTRATION,
            threat_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.campaign_name == "test-item"
        assert r.threat_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_detection(campaign_name=f"ITEM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_detection
# ---------------------------------------------------------------------------


class TestGetDetection:
    def test_found(self):
        eng = _engine()
        r = eng.record_detection(campaign_name="test-item")
        result = eng.get_detection(r.id)
        assert result is not None
        assert result.campaign_name == "test-item"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_detection("nonexistent") is None


# ---------------------------------------------------------------------------
# list_detections
# ---------------------------------------------------------------------------


class TestListDetections:
    def test_list_all(self):
        eng = _engine()
        eng.record_detection(campaign_name="ITEM-001")
        eng.record_detection(campaign_name="ITEM-002")
        assert len(eng.list_detections()) == 2

    def test_filter_by_apt_indicator(self):
        eng = _engine()
        eng.record_detection(campaign_name="ITEM-001", apt_indicator=APTIndicator.LONG_DWELL)
        eng.record_detection(campaign_name="ITEM-002", apt_indicator=APTIndicator.SLOW_EXFILTRATION)
        results = eng.list_detections(apt_indicator=APTIndicator.LONG_DWELL)
        assert len(results) == 1

    def test_filter_by_apt_stage(self):
        eng = _engine()
        eng.record_detection(campaign_name="ITEM-001", apt_stage=APTStage.INITIAL_COMPROMISE)
        eng.record_detection(campaign_name="ITEM-002", apt_stage=APTStage.ESTABLISH_FOOTHOLD)
        results = eng.list_detections(apt_stage=APTStage.INITIAL_COMPROMISE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_detection(campaign_name="ITEM-001", team="security")
        eng.record_detection(campaign_name="ITEM-002", team="platform")
        results = eng.list_detections(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_detection(campaign_name=f"ITEM-{i}")
        assert len(eng.list_detections(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            campaign_name="test-item",
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="test description",
        )
        assert a.campaign_name == "test-item"
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(campaign_name=f"ITEM-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_threat_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_detection(
            campaign_name="ITEM-001", apt_indicator=APTIndicator.LONG_DWELL, threat_score=90.0
        )
        eng.record_detection(
            campaign_name="ITEM-002", apt_indicator=APTIndicator.LONG_DWELL, threat_score=70.0
        )
        result = eng.analyze_threat_distribution()
        assert "long_dwell" in result
        assert result["long_dwell"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_threat_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_threat_detections
# ---------------------------------------------------------------------------


class TestIdentifyProblems:
    def test_detects_threshold(self):
        eng = _engine(apt_threat_threshold=65.0)
        eng.record_detection(campaign_name="ITEM-001", threat_score=90.0)
        eng.record_detection(campaign_name="ITEM-002", threat_score=40.0)
        results = eng.identify_high_threat_detections()
        assert len(results) == 1
        assert results[0]["campaign_name"] == "ITEM-001"

    def test_sorted_descending(self):
        eng = _engine(apt_threat_threshold=65.0)
        eng.record_detection(campaign_name="ITEM-001", threat_score=80.0)
        eng.record_detection(campaign_name="ITEM-002", threat_score=95.0)
        results = eng.identify_high_threat_detections()
        assert len(results) == 2
        assert results[0]["threat_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_threat_detections() == []


# ---------------------------------------------------------------------------
# rank_by_threat_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted(self):
        eng = _engine()
        eng.record_detection(campaign_name="ITEM-001", service="auth-svc", threat_score=90.0)
        eng.record_detection(campaign_name="ITEM-002", service="api-gw", threat_score=50.0)
        results = eng.rank_by_threat_score()
        assert len(results) == 2
        assert results[0]["service"] == "auth-svc"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_threat_score() == []


# ---------------------------------------------------------------------------
# detect_threat_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(campaign_name="ITEM-001", analysis_score=50.0)
        result = eng.detect_threat_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(campaign_name="ITEM-001", analysis_score=20.0)
        eng.add_analysis(campaign_name="ITEM-002", analysis_score=20.0)
        eng.add_analysis(campaign_name="ITEM-003", analysis_score=80.0)
        eng.add_analysis(campaign_name="ITEM-004", analysis_score=80.0)
        result = eng.detect_threat_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_threat_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(apt_threat_threshold=65.0)
        eng.record_detection(campaign_name="test-item", threat_score=90.0)
        report = eng.generate_report()
        assert isinstance(report, APTReport)
        assert report.total_records == 1
        assert report.high_threat_count == 1
        assert len(report.top_high_threat) == 1
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
        eng.record_detection(campaign_name="ITEM-001")
        eng.add_analysis(campaign_name="ITEM-001")
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

    def test_populated(self):
        eng = _engine()
        eng.record_detection(
            campaign_name="ITEM-001",
            apt_indicator=APTIndicator.LONG_DWELL,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
