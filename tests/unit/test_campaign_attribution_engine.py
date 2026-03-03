"""Tests for shieldops.security.campaign_attribution_engine — CampaignAttributionEngine."""

from __future__ import annotations

from shieldops.security.campaign_attribution_engine import (
    AttributionConfidence,
    CampaignAnalysis,
    CampaignAttributionEngine,
    CampaignAttributionReport,
    CampaignRecord,
    CampaignStatus,
    ThreatActorType,
)


def _engine(**kw) -> CampaignAttributionEngine:
    return CampaignAttributionEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_attributionconfidence_val1(self):
        assert AttributionConfidence.CONFIRMED == "confirmed"

    def test_attributionconfidence_val2(self):
        assert AttributionConfidence.HIGH == "high"

    def test_attributionconfidence_val3(self):
        assert AttributionConfidence.MEDIUM == "medium"

    def test_attributionconfidence_val4(self):
        assert AttributionConfidence.LOW == "low"

    def test_attributionconfidence_val5(self):
        assert AttributionConfidence.UNATTRIBUTED == "unattributed"

    def test_threatactortype_val1(self):
        assert ThreatActorType.APT == "apt"

    def test_threatactortype_val2(self):
        assert ThreatActorType.CYBERCRIME == "cybercrime"

    def test_threatactortype_val3(self):
        assert ThreatActorType.HACKTIVISM == "hacktivism"

    def test_threatactortype_val4(self):
        assert ThreatActorType.INSIDER == "insider"

    def test_threatactortype_val5(self):
        assert ThreatActorType.UNKNOWN == "unknown"

    def test_campaignstatus_val1(self):
        assert CampaignStatus.ACTIVE == "active"

    def test_campaignstatus_val2(self):
        assert CampaignStatus.DORMANT == "dormant"

    def test_campaignstatus_val3(self):
        assert CampaignStatus.CONCLUDED == "concluded"

    def test_campaignstatus_val4(self):
        assert CampaignStatus.EMERGING == "emerging"

    def test_campaignstatus_val5(self):
        assert CampaignStatus.HISTORICAL == "historical"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_record_defaults(self):
        r = CampaignRecord()
        assert r.id
        assert r.campaign_name == ""
        assert r.attribution_confidence == AttributionConfidence.UNATTRIBUTED
        assert r.attribution_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = CampaignAnalysis()
        assert a.id
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = CampaignAttributionReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_attribution_score == 0.0
        assert r.by_confidence == {}
        assert r.by_actor_type == {}
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
        r = eng.record_campaign(
            campaign_name="test",
            attribution_confidence=AttributionConfidence.HIGH,
            attribution_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.campaign_name == "test"
        assert r.attribution_confidence == AttributionConfidence.HIGH
        assert r.attribution_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_campaign(campaign_name=f"test-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_record
# ---------------------------------------------------------------------------


class TestGetRecord:
    def test_found(self):
        eng = _engine()
        r = eng.record_campaign(campaign_name="test")
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
        eng.record_campaign(campaign_name="a")
        eng.record_campaign(campaign_name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_enum1(self):
        eng = _engine()
        eng.record_campaign(
            campaign_name="a", attribution_confidence=AttributionConfidence.CONFIRMED
        )
        eng.record_campaign(campaign_name="b", attribution_confidence=AttributionConfidence.HIGH)
        results = eng.list_records(attribution_confidence=AttributionConfidence.CONFIRMED)
        assert len(results) == 1

    def test_filter_by_enum2(self):
        eng = _engine()
        eng.record_campaign(campaign_name="a", threat_actor_type=ThreatActorType.APT)
        eng.record_campaign(campaign_name="b", threat_actor_type=ThreatActorType.CYBERCRIME)
        results = eng.list_records(threat_actor_type=ThreatActorType.APT)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_campaign(campaign_name="a", team="sec")
        eng.record_campaign(campaign_name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_campaign(campaign_name=f"t-{i}")
        assert len(eng.list_records(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            campaign_name="test",
            analysis_score=88.5,
            breached=True,
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(campaign_name=f"test-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_campaign(
            campaign_name="a",
            attribution_confidence=AttributionConfidence.CONFIRMED,
            attribution_score=90.0,
        )
        eng.record_campaign(
            campaign_name="b",
            attribution_confidence=AttributionConfidence.CONFIRMED,
            attribution_score=70.0,
        )
        result = eng.analyze_confidence_distribution()
        assert "confirmed" in result
        assert result["confirmed"]["count"] == 2
        assert result["confirmed"]["avg_attribution_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_confidence_distribution() == {}


# ---------------------------------------------------------------------------
# identify_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_campaign(campaign_name="a", attribution_score=60.0)
        eng.record_campaign(campaign_name="b", attribution_score=90.0)
        results = eng.identify_gaps()
        assert len(results) == 1
        assert results[0]["campaign_name"] == "a"

    def test_sorted_ascending(self):
        eng = _engine(quality_threshold=80.0)
        eng.record_campaign(campaign_name="a", attribution_score=50.0)
        eng.record_campaign(campaign_name="b", attribution_score=30.0)
        results = eng.identify_gaps()
        assert len(results) == 2
        assert results[0]["attribution_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


# ---------------------------------------------------------------------------
# rank_by_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_campaign(campaign_name="a", service="auth-svc", attribution_score=90.0)
        eng.record_campaign(campaign_name="b", service="api-gw", attribution_score=50.0)
        results = eng.rank_by_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"
        assert results[0]["avg_attribution_score"] == 50.0

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
            eng.add_analysis(campaign_name="t", analysis_score=50.0)
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(campaign_name="t1", analysis_score=20.0)
        eng.add_analysis(campaign_name="t2", analysis_score=20.0)
        eng.add_analysis(campaign_name="t3", analysis_score=80.0)
        eng.add_analysis(campaign_name="t4", analysis_score=80.0)
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
        eng.record_campaign(
            campaign_name="test",
            attribution_confidence=AttributionConfidence.HIGH,
            attribution_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, CampaignAttributionReport)
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
        eng.record_campaign(campaign_name="test")
        eng.add_analysis(campaign_name="test")
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
        assert stats["confidence_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_campaign(
            campaign_name="test",
            attribution_confidence=AttributionConfidence.CONFIRMED,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "confirmed" in stats["confidence_distribution"]
