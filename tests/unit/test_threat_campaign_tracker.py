"""Tests for shieldops.security.threat_campaign_tracker — ThreatCampaignTracker."""

from __future__ import annotations

from shieldops.security.threat_campaign_tracker import (
    CampaignAnalysis,
    CampaignRecord,
    CampaignReport,
    CampaignSeverity,
    CampaignStatus,
    CampaignType,
    ThreatCampaignTracker,
)


def _engine(**kw) -> ThreatCampaignTracker:
    return ThreatCampaignTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_apt(self):
        assert CampaignType.APT == "apt"

    def test_type_ransomware(self):
        assert CampaignType.RANSOMWARE == "ransomware"

    def test_type_phishing(self):
        assert CampaignType.PHISHING == "phishing"

    def test_type_supply_chain(self):
        assert CampaignType.SUPPLY_CHAIN == "supply_chain"

    def test_type_insider_threat(self):
        assert CampaignType.INSIDER_THREAT == "insider_threat"

    def test_status_active(self):
        assert CampaignStatus.ACTIVE == "active"

    def test_status_contained(self):
        assert CampaignStatus.CONTAINED == "contained"

    def test_status_eradicated(self):
        assert CampaignStatus.ERADICATED == "eradicated"

    def test_status_monitoring(self):
        assert CampaignStatus.MONITORING == "monitoring"

    def test_status_closed(self):
        assert CampaignStatus.CLOSED == "closed"

    def test_severity_critical(self):
        assert CampaignSeverity.CRITICAL == "critical"

    def test_severity_high(self):
        assert CampaignSeverity.HIGH == "high"

    def test_severity_medium(self):
        assert CampaignSeverity.MEDIUM == "medium"

    def test_severity_low(self):
        assert CampaignSeverity.LOW == "low"

    def test_severity_informational(self):
        assert CampaignSeverity.INFORMATIONAL == "informational"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_campaign_record_defaults(self):
        r = CampaignRecord()
        assert r.id
        assert r.campaign_name == ""
        assert r.campaign_type == CampaignType.APT
        assert r.campaign_status == CampaignStatus.ACTIVE
        assert r.campaign_severity == CampaignSeverity.CRITICAL
        assert r.threat_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_campaign_analysis_defaults(self):
        c = CampaignAnalysis()
        assert c.id
        assert c.campaign_name == ""
        assert c.campaign_type == CampaignType.APT
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached is False
        assert c.description == ""
        assert c.created_at > 0

    def test_campaign_report_defaults(self):
        r = CampaignReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.high_threat_count == 0
        assert r.avg_threat_score == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.by_severity == {}
        assert r.top_high_threat == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_campaign
# ---------------------------------------------------------------------------


class TestRecordCampaign:
    def test_basic(self):
        eng = _engine()
        r = eng.record_campaign(
            campaign_name="camp-001",
            campaign_type=CampaignType.RANSOMWARE,
            campaign_status=CampaignStatus.CONTAINED,
            campaign_severity=CampaignSeverity.HIGH,
            threat_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.campaign_name == "camp-001"
        assert r.campaign_type == CampaignType.RANSOMWARE
        assert r.campaign_status == CampaignStatus.CONTAINED
        assert r.campaign_severity == CampaignSeverity.HIGH
        assert r.threat_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_campaign(campaign_name=f"camp-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_campaign
# ---------------------------------------------------------------------------


class TestGetCampaign:
    def test_found(self):
        eng = _engine()
        r = eng.record_campaign(
            campaign_name="camp-001",
            campaign_severity=CampaignSeverity.CRITICAL,
        )
        result = eng.get_campaign(r.id)
        assert result is not None
        assert result.campaign_severity == CampaignSeverity.CRITICAL

    def test_not_found(self):
        eng = _engine()
        assert eng.get_campaign("nonexistent") is None


# ---------------------------------------------------------------------------
# list_campaigns
# ---------------------------------------------------------------------------


class TestListCampaigns:
    def test_list_all(self):
        eng = _engine()
        eng.record_campaign(campaign_name="camp-001")
        eng.record_campaign(campaign_name="camp-002")
        assert len(eng.list_campaigns()) == 2

    def test_filter_by_campaign_type(self):
        eng = _engine()
        eng.record_campaign(
            campaign_name="camp-001",
            campaign_type=CampaignType.APT,
        )
        eng.record_campaign(
            campaign_name="camp-002",
            campaign_type=CampaignType.RANSOMWARE,
        )
        results = eng.list_campaigns(campaign_type=CampaignType.APT)
        assert len(results) == 1

    def test_filter_by_campaign_status(self):
        eng = _engine()
        eng.record_campaign(
            campaign_name="camp-001",
            campaign_status=CampaignStatus.ACTIVE,
        )
        eng.record_campaign(
            campaign_name="camp-002",
            campaign_status=CampaignStatus.CLOSED,
        )
        results = eng.list_campaigns(campaign_status=CampaignStatus.ACTIVE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_campaign(campaign_name="camp-001", team="security")
        eng.record_campaign(campaign_name="camp-002", team="platform")
        results = eng.list_campaigns(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_campaign(campaign_name=f"camp-{i}")
        assert len(eng.list_campaigns(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            campaign_name="camp-001",
            campaign_type=CampaignType.RANSOMWARE,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="high threat detected",
        )
        assert a.campaign_name == "camp-001"
        assert a.campaign_type == CampaignType.RANSOMWARE
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(campaign_name=f"camp-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_campaign_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_campaign(
            campaign_name="camp-001",
            campaign_type=CampaignType.APT,
            threat_score=90.0,
        )
        eng.record_campaign(
            campaign_name="camp-002",
            campaign_type=CampaignType.APT,
            threat_score=70.0,
        )
        result = eng.analyze_campaign_distribution()
        assert "apt" in result
        assert result["apt"]["count"] == 2
        assert result["apt"]["avg_threat_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_campaign_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_threat_campaigns
# ---------------------------------------------------------------------------


class TestIdentifyHighThreatCampaigns:
    def test_detects_above_threshold(self):
        eng = _engine(threat_score_threshold=80.0)
        eng.record_campaign(campaign_name="camp-001", threat_score=90.0)
        eng.record_campaign(campaign_name="camp-002", threat_score=60.0)
        results = eng.identify_high_threat_campaigns()
        assert len(results) == 1
        assert results[0]["campaign_name"] == "camp-001"

    def test_sorted_descending(self):
        eng = _engine(threat_score_threshold=50.0)
        eng.record_campaign(campaign_name="camp-001", threat_score=80.0)
        eng.record_campaign(campaign_name="camp-002", threat_score=95.0)
        results = eng.identify_high_threat_campaigns()
        assert len(results) == 2
        assert results[0]["threat_score"] == 95.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_threat_campaigns() == []


# ---------------------------------------------------------------------------
# rank_by_threat
# ---------------------------------------------------------------------------


class TestRankByThreat:
    def test_sorted_descending(self):
        eng = _engine()
        eng.record_campaign(campaign_name="camp-001", service="auth-svc", threat_score=50.0)
        eng.record_campaign(campaign_name="camp-002", service="api-gw", threat_score=90.0)
        results = eng.rank_by_threat()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_threat_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_threat() == []


# ---------------------------------------------------------------------------
# detect_campaign_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(campaign_name="camp-001", analysis_score=50.0)
        result = eng.detect_campaign_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(campaign_name="camp-001", analysis_score=20.0)
        eng.add_analysis(campaign_name="camp-002", analysis_score=20.0)
        eng.add_analysis(campaign_name="camp-003", analysis_score=80.0)
        eng.add_analysis(campaign_name="camp-004", analysis_score=80.0)
        result = eng.detect_campaign_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_campaign_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threat_score_threshold=80.0)
        eng.record_campaign(
            campaign_name="camp-001",
            campaign_type=CampaignType.RANSOMWARE,
            campaign_status=CampaignStatus.CONTAINED,
            campaign_severity=CampaignSeverity.HIGH,
            threat_score=95.0,
        )
        report = eng.generate_report()
        assert isinstance(report, CampaignReport)
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
        eng.record_campaign(campaign_name="camp-001")
        eng.add_analysis(campaign_name="camp-001")
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
        eng.record_campaign(
            campaign_name="camp-001",
            campaign_type=CampaignType.APT,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "apt" in stats["type_distribution"]
