"""Tests for shieldops.incidents.stakeholder_impact_tracker — StakeholderImpactTracker."""

from __future__ import annotations

from shieldops.incidents.stakeholder_impact_tracker import (
    CommunicationChannel,
    ImpactLevel,
    StakeholderAssessment,
    StakeholderGroup,
    StakeholderImpactReport,
    StakeholderImpactTracker,
    StakeholderRecord,
)


def _engine(**kw) -> StakeholderImpactTracker:
    return StakeholderImpactTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_group_executive(self):
        assert StakeholderGroup.EXECUTIVE == "executive"

    def test_group_engineering(self):
        assert StakeholderGroup.ENGINEERING == "engineering"

    def test_group_product(self):
        assert StakeholderGroup.PRODUCT == "product"

    def test_group_customer_success(self):
        assert StakeholderGroup.CUSTOMER_SUCCESS == "customer_success"

    def test_group_operations(self):
        assert StakeholderGroup.OPERATIONS == "operations"

    def test_level_critical(self):
        assert ImpactLevel.CRITICAL == "critical"

    def test_level_high(self):
        assert ImpactLevel.HIGH == "high"

    def test_level_moderate(self):
        assert ImpactLevel.MODERATE == "moderate"

    def test_level_low(self):
        assert ImpactLevel.LOW == "low"

    def test_level_informational(self):
        assert ImpactLevel.INFORMATIONAL == "informational"

    def test_channel_email(self):
        assert CommunicationChannel.EMAIL == "email"

    def test_channel_slack(self):
        assert CommunicationChannel.SLACK == "slack"

    def test_channel_pagerduty(self):
        assert CommunicationChannel.PAGERDUTY == "pagerduty"

    def test_channel_status_page(self):
        assert CommunicationChannel.STATUS_PAGE == "status_page"

    def test_channel_phone(self):
        assert CommunicationChannel.PHONE == "phone"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_stakeholder_record_defaults(self):
        r = StakeholderRecord()
        assert r.id
        assert r.incident_id == ""
        assert r.stakeholder_group == StakeholderGroup.EXECUTIVE
        assert r.impact_level == ImpactLevel.CRITICAL
        assert r.communication_channel == CommunicationChannel.EMAIL
        assert r.impact_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_stakeholder_assessment_defaults(self):
        a = StakeholderAssessment()
        assert a.id
        assert a.incident_id == ""
        assert a.stakeholder_group == StakeholderGroup.EXECUTIVE
        assert a.assessment_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_stakeholder_impact_report_defaults(self):
        r = StakeholderImpactReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_assessments == 0
        assert r.high_impact_count == 0
        assert r.avg_impact_score == 0.0
        assert r.by_group == {}
        assert r.by_level == {}
        assert r.by_channel == {}
        assert r.top_high_impact == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_impact
# ---------------------------------------------------------------------------


class TestRecordImpact:
    def test_basic(self):
        eng = _engine()
        r = eng.record_impact(
            incident_id="INC-001",
            stakeholder_group=StakeholderGroup.ENGINEERING,
            impact_level=ImpactLevel.HIGH,
            communication_channel=CommunicationChannel.SLACK,
            impact_score=85.0,
            service="api-gateway",
            team="sre",
        )
        assert r.incident_id == "INC-001"
        assert r.stakeholder_group == StakeholderGroup.ENGINEERING
        assert r.impact_level == ImpactLevel.HIGH
        assert r.communication_channel == CommunicationChannel.SLACK
        assert r.impact_score == 85.0
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_impact(incident_id=f"INC-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_impact
# ---------------------------------------------------------------------------


class TestGetImpact:
    def test_found(self):
        eng = _engine()
        r = eng.record_impact(
            incident_id="INC-001",
            stakeholder_group=StakeholderGroup.PRODUCT,
        )
        result = eng.get_impact(r.id)
        assert result is not None
        assert result.stakeholder_group == StakeholderGroup.PRODUCT

    def test_not_found(self):
        eng = _engine()
        assert eng.get_impact("nonexistent") is None


# ---------------------------------------------------------------------------
# list_impacts
# ---------------------------------------------------------------------------


class TestListImpacts:
    def test_list_all(self):
        eng = _engine()
        eng.record_impact(incident_id="INC-001")
        eng.record_impact(incident_id="INC-002")
        assert len(eng.list_impacts()) == 2

    def test_filter_by_group(self):
        eng = _engine()
        eng.record_impact(
            incident_id="INC-001",
            stakeholder_group=StakeholderGroup.ENGINEERING,
        )
        eng.record_impact(
            incident_id="INC-002",
            stakeholder_group=StakeholderGroup.EXECUTIVE,
        )
        results = eng.list_impacts(
            stakeholder_group=StakeholderGroup.ENGINEERING,
        )
        assert len(results) == 1

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_impact(
            incident_id="INC-001",
            impact_level=ImpactLevel.HIGH,
        )
        eng.record_impact(
            incident_id="INC-002",
            impact_level=ImpactLevel.LOW,
        )
        results = eng.list_impacts(
            impact_level=ImpactLevel.HIGH,
        )
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_impact(incident_id="INC-001", team="sre")
        eng.record_impact(incident_id="INC-002", team="platform")
        results = eng.list_impacts(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_impact(incident_id=f"INC-{i}")
        assert len(eng.list_impacts(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_assessment
# ---------------------------------------------------------------------------


class TestAddAssessment:
    def test_basic(self):
        eng = _engine()
        a = eng.add_assessment(
            incident_id="INC-001",
            stakeholder_group=StakeholderGroup.CUSTOMER_SUCCESS,
            assessment_score=35.0,
            threshold=70.0,
            breached=True,
            description="High stakeholder impact detected",
        )
        assert a.incident_id == "INC-001"
        assert a.stakeholder_group == StakeholderGroup.CUSTOMER_SUCCESS
        assert a.assessment_score == 35.0
        assert a.threshold == 70.0
        assert a.breached is True
        assert a.description == "High stakeholder impact detected"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_assessment(incident_id=f"INC-{i}")
        assert len(eng._assessments) == 2


# ---------------------------------------------------------------------------
# analyze_impact_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeImpactDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_impact(
            incident_id="INC-001",
            stakeholder_group=StakeholderGroup.ENGINEERING,
            impact_score=40.0,
        )
        eng.record_impact(
            incident_id="INC-002",
            stakeholder_group=StakeholderGroup.ENGINEERING,
            impact_score=50.0,
        )
        result = eng.analyze_impact_distribution()
        assert "engineering" in result
        assert result["engineering"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_impact_distribution() == {}


# ---------------------------------------------------------------------------
# identify_high_impact_stakeholders
# ---------------------------------------------------------------------------


class TestIdentifyHighImpactStakeholders:
    def test_detects_high_impact(self):
        eng = _engine(impact_score_threshold=70.0)
        eng.record_impact(
            incident_id="INC-001",
            impact_score=85.0,
        )
        eng.record_impact(
            incident_id="INC-002",
            impact_score=50.0,
        )
        results = eng.identify_high_impact_stakeholders()
        assert len(results) == 1
        assert results[0]["incident_id"] == "INC-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_impact_stakeholders() == []


# ---------------------------------------------------------------------------
# rank_by_impact
# ---------------------------------------------------------------------------


class TestRankByImpact:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_impact(
            incident_id="INC-001",
            service="api-gateway",
            impact_score=30.0,
        )
        eng.record_impact(
            incident_id="INC-002",
            service="payments",
            impact_score=90.0,
        )
        results = eng.rank_by_impact()
        assert len(results) == 2
        assert results[0]["service"] == "payments"
        assert results[0]["avg_impact_score"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_impact() == []


# ---------------------------------------------------------------------------
# detect_impact_trends
# ---------------------------------------------------------------------------


class TestDetectImpactTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_assessment(
                incident_id="INC-001",
                assessment_score=50.0,
            )
        result = eng.detect_impact_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_assessment(incident_id="INC-001", assessment_score=30.0)
        eng.add_assessment(incident_id="INC-002", assessment_score=30.0)
        eng.add_assessment(incident_id="INC-003", assessment_score=80.0)
        eng.add_assessment(incident_id="INC-004", assessment_score=80.0)
        result = eng.detect_impact_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_impact_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(impact_score_threshold=70.0)
        eng.record_impact(
            incident_id="INC-001",
            stakeholder_group=StakeholderGroup.ENGINEERING,
            impact_level=ImpactLevel.HIGH,
            communication_channel=CommunicationChannel.SLACK,
            impact_score=85.0,
        )
        report = eng.generate_report()
        assert isinstance(report, StakeholderImpactReport)
        assert report.total_records == 1
        assert report.high_impact_count == 1
        assert len(report.top_high_impact) == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "acceptable" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_impact(incident_id="INC-001")
        eng.add_assessment(incident_id="INC-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._assessments) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_assessments"] == 0
        assert stats["group_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_impact(
            incident_id="INC-001",
            stakeholder_group=StakeholderGroup.ENGINEERING,
            team="sre",
            service="api-gateway",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "engineering" in stats["group_distribution"]
