"""Tests for shieldops.security.phishing_campaign_detector — PhishingCampaignDetector."""

from __future__ import annotations

from shieldops.security.phishing_campaign_detector import (
    CampaignIndicator,
    CampaignStatus,
    PhishingAnalysis,
    PhishingCampaignDetector,
    PhishingCampaignReport,
    PhishingRecord,
    PhishingType,
)


def _engine(**kw) -> PhishingCampaignDetector:
    return PhishingCampaignDetector(**kw)


class TestEnums:
    def test_e1_v1(self):
        assert PhishingType.SPEAR_PHISHING == "spear_phishing"

    def test_e1_v2(self):
        assert PhishingType.WHALING == "whaling"

    def test_e1_v3(self):
        assert PhishingType.SMISHING == "smishing"

    def test_e1_v4(self):
        assert PhishingType.VISHING == "vishing"

    def test_e1_v5(self):
        assert PhishingType.BEC == "bec"

    def test_e2_v1(self):
        assert CampaignIndicator.DOMAIN_SIMILARITY == "domain_similarity"

    def test_e2_v2(self):
        assert CampaignIndicator.HEADER_ANOMALY == "header_anomaly"

    def test_e2_v3(self):
        assert CampaignIndicator.CONTENT_PATTERN == "content_pattern"

    def test_e2_v4(self):
        assert CampaignIndicator.SENDER_REPUTATION == "sender_reputation"

    def test_e2_v5(self):
        assert CampaignIndicator.LINK_ANALYSIS == "link_analysis"

    def test_e3_v1(self):
        assert CampaignStatus.ACTIVE == "active"

    def test_e3_v2(self):
        assert CampaignStatus.CONTAINED == "contained"

    def test_e3_v3(self):
        assert CampaignStatus.MITIGATED == "mitigated"

    def test_e3_v4(self):
        assert CampaignStatus.MONITORING == "monitoring"

    def test_e3_v5(self):
        assert CampaignStatus.CLOSED == "closed"


class TestModels:
    def test_rec(self):
        r = PhishingRecord()
        assert r.id and r.detection_score == 0.0 and r.service == ""

    def test_analysis(self):
        a = PhishingAnalysis()
        assert a.id and a.analysis_score == 0.0 and a.breached is False

    def test_report(self):
        r = PhishingCampaignReport()
        assert r.id and r.total_records == 0


class TestRecord:
    def test_basic(self):
        r = _engine().record_phishing(
            phishing_id="t",
            phishing_type=PhishingType.WHALING,
            campaign_indicator=CampaignIndicator.HEADER_ANOMALY,
            campaign_status=CampaignStatus.CONTAINED,
            detection_score=92.0,
            service="s",
            team="t",
        )
        assert r.phishing_id == "t" and r.detection_score == 92.0

    def test_eviction(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_phishing(phishing_id=f"t-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_phishing(phishing_id="t")
        assert eng.get_phishing(r.id) is not None

    def test_not_found(self):
        assert _engine().get_phishing("x") is None


class TestList:
    def test_all(self):
        eng = _engine()
        eng.record_phishing(phishing_id="a")
        eng.record_phishing(phishing_id="b")
        assert len(eng.list_phishings()) == 2

    def test_e1(self):
        eng = _engine()
        eng.record_phishing(phishing_id="a", phishing_type=PhishingType.SPEAR_PHISHING)
        eng.record_phishing(phishing_id="b", phishing_type=PhishingType.WHALING)
        assert len(eng.list_phishings(phishing_type=PhishingType.SPEAR_PHISHING)) == 1

    def test_e2(self):
        eng = _engine()
        eng.record_phishing(phishing_id="a", campaign_indicator=CampaignIndicator.DOMAIN_SIMILARITY)
        eng.record_phishing(phishing_id="b", campaign_indicator=CampaignIndicator.HEADER_ANOMALY)
        assert len(eng.list_phishings(campaign_indicator=CampaignIndicator.DOMAIN_SIMILARITY)) == 1

    def test_team(self):
        eng = _engine()
        eng.record_phishing(phishing_id="a", team="x")
        eng.record_phishing(phishing_id="b", team="y")
        assert len(eng.list_phishings(team="x")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_phishing(phishing_id=f"t-{i}")
        assert len(eng.list_phishings(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        a = _engine().add_analysis(
            phishing_id="t", phishing_type=PhishingType.WHALING, analysis_score=88.5, breached=True
        )
        assert a.analysis_score == 88.5 and a.breached is True

    def test_eviction(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(phishing_id=f"t-{i}")
        assert len(eng._analyses) == 2


class TestDistribution:
    def test_data(self):
        eng = _engine()
        eng.record_phishing(
            phishing_id="a", phishing_type=PhishingType.SPEAR_PHISHING, detection_score=90.0
        )
        eng.record_phishing(
            phishing_id="b", phishing_type=PhishingType.SPEAR_PHISHING, detection_score=70.0
        )
        assert "spear_phishing" in eng.analyze_type_distribution()

    def test_empty(self):
        assert _engine().analyze_type_distribution() == {}


class TestGaps:
    def test_below(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_phishing(phishing_id="a", detection_score=60.0)
        eng.record_phishing(phishing_id="b", detection_score=90.0)
        assert len(eng.identify_detection_gaps()) == 1

    def test_sorted(self):
        eng = _engine(detection_threshold=80.0)
        eng.record_phishing(phishing_id="a", detection_score=50.0)
        eng.record_phishing(phishing_id="b", detection_score=30.0)
        assert len(eng.identify_detection_gaps()) == 2


class TestRank:
    def test_data(self):
        eng = _engine()
        eng.record_phishing(phishing_id="a", service="s1", detection_score=80.0)
        eng.record_phishing(phishing_id="b", service="s2", detection_score=60.0)
        assert eng.rank_by_detection()[0]["service"] == "s2"

    def test_empty(self):
        assert _engine().rank_by_detection() == []


class TestTrends:
    def test_improving(self):
        eng = _engine()
        for v in [10, 20, 30, 40, 50, 60, 70, 80]:
            eng.add_analysis(phishing_id="t", analysis_score=float(v))
        assert eng.detect_detection_trends()["trend"] == "improving"

    def test_stable(self):
        eng = _engine()
        for v in [50, 51, 49, 50]:
            eng.add_analysis(phishing_id="t", analysis_score=float(v))
        assert eng.detect_detection_trends()["trend"] == "stable"

    def test_insufficient(self):
        assert _engine().detect_detection_trends()["trend"] == "insufficient_data"


class TestReport:
    def test_data(self):
        eng = _engine()
        eng.record_phishing(phishing_id="t", detection_score=90.0)
        assert eng.generate_report().total_records == 1

    def test_empty(self):
        assert _engine().generate_report().total_records == 0


class TestClear:
    def test_clears(self):
        eng = _engine()
        eng.record_phishing(phishing_id="t")
        eng.add_analysis(phishing_id="t")
        eng.clear_data()
        assert len(eng._records) == 0 and len(eng._analyses) == 0


class TestStats:
    def test_data(self):
        eng = _engine()
        eng.record_phishing(phishing_id="t", team="s", service="v")
        assert eng.get_stats()["total_records"] == 1

    def test_empty(self):
        assert _engine().get_stats()["total_records"] == 0

    def test_counts(self):
        eng = _engine()
        eng.record_phishing(phishing_id="a")
        eng.record_phishing(phishing_id="b")
        eng.add_analysis(phishing_id="t")
        assert eng.get_stats()["total_records"] == 2 and eng.get_stats()["total_analyses"] == 1
