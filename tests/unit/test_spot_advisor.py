"""Tests for shieldops.billing.spot_advisor — SpotInstanceAdvisor."""

from __future__ import annotations

from shieldops.billing.spot_advisor import (
    InterruptionRisk,
    SavingsGrade,
    SpotAdvisorReport,
    SpotInstanceAdvisor,
    SpotMarket,
    SpotRecommendation,
    SpotUsageRecord,
)


def _engine(**kw) -> SpotInstanceAdvisor:
    return SpotInstanceAdvisor(**kw)


class TestEnums:
    def test_market_aws(self):
        assert SpotMarket.AWS_SPOT == "aws_spot"

    def test_market_gcp(self):
        assert SpotMarket.GCP_PREEMPTIBLE == "gcp_preemptible"

    def test_market_azure(self):
        assert SpotMarket.AZURE_SPOT == "azure_spot"

    def test_market_on_demand(self):
        assert SpotMarket.ON_DEMAND == "on_demand"

    def test_market_reserved(self):
        assert SpotMarket.RESERVED == "reserved"

    def test_risk_very_high(self):
        assert InterruptionRisk.VERY_HIGH == "very_high"

    def test_risk_high(self):
        assert InterruptionRisk.HIGH == "high"

    def test_risk_moderate(self):
        assert InterruptionRisk.MODERATE == "moderate"

    def test_risk_low(self):
        assert InterruptionRisk.LOW == "low"

    def test_risk_minimal(self):
        assert InterruptionRisk.MINIMAL == "minimal"

    def test_grade_excellent(self):
        assert SavingsGrade.EXCELLENT == "excellent"

    def test_grade_good(self):
        assert SavingsGrade.GOOD == "good"

    def test_grade_moderate(self):
        assert SavingsGrade.MODERATE == "moderate"

    def test_grade_marginal(self):
        assert SavingsGrade.MARGINAL == "marginal"

    def test_grade_not_recommended(self):
        assert SavingsGrade.NOT_RECOMMENDED == "not_recommended"


class TestModels:
    def test_usage_record_defaults(self):
        r = SpotUsageRecord()
        assert r.id
        assert r.instance_type == ""
        assert r.market == SpotMarket.ON_DEMAND
        assert r.interruption_risk == InterruptionRisk.MODERATE
        assert r.savings_pct == 0.0
        assert r.monthly_cost == 0.0
        assert r.on_demand_cost == 0.0
        assert r.details == ""
        assert r.created_at > 0

    def test_recommendation_defaults(self):
        r = SpotRecommendation()
        assert r.id
        assert r.instance_type == ""
        assert r.recommended_market == SpotMarket.AWS_SPOT
        assert r.savings_grade == SavingsGrade.MODERATE
        assert r.estimated_savings_pct == 0.0
        assert r.reason == ""
        assert r.created_at > 0

    def test_report_defaults(self):
        r = SpotAdvisorReport()
        assert r.total_records == 0
        assert r.total_recommendations == 0
        assert r.avg_savings_pct == 0.0
        assert r.by_market == {}
        assert r.by_risk == {}
        assert r.high_savings_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordUsage:
    def test_basic(self):
        eng = _engine()
        r = eng.record_usage(
            "m5.xlarge",
            market=SpotMarket.AWS_SPOT,
            savings_pct=60.0,
        )
        assert r.instance_type == "m5.xlarge"
        assert r.savings_pct == 60.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_usage(f"i-{i}")
        assert len(eng._records) == 3


class TestGetUsage:
    def test_found(self):
        eng = _engine()
        r = eng.record_usage("m5.xlarge")
        assert eng.get_usage(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_usage("nonexistent") is None


class TestListUsage:
    def test_list_all(self):
        eng = _engine()
        eng.record_usage("m5.xlarge")
        eng.record_usage("c5.2xlarge")
        assert len(eng.list_usage()) == 2

    def test_filter_by_instance(self):
        eng = _engine()
        eng.record_usage("m5.xlarge")
        eng.record_usage("c5.2xlarge")
        results = eng.list_usage(instance_type="m5.xlarge")
        assert len(results) == 1

    def test_filter_by_market(self):
        eng = _engine()
        eng.record_usage("i1", market=SpotMarket.AWS_SPOT)
        eng.record_usage("i2", market=SpotMarket.ON_DEMAND)
        results = eng.list_usage(market=SpotMarket.AWS_SPOT)
        assert len(results) == 1


class TestAddRecommendation:
    def test_basic(self):
        eng = _engine()
        r = eng.add_recommendation(
            "m5.xlarge",
            estimated_savings_pct=75.0,
        )
        assert r.savings_grade == SavingsGrade.EXCELLENT

    def test_explicit_grade(self):
        eng = _engine()
        r = eng.add_recommendation("i1", savings_grade=SavingsGrade.MARGINAL)
        assert r.savings_grade == SavingsGrade.MARGINAL

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_recommendation(f"i-{i}")
        assert len(eng._recommendations) == 2


class TestAnalyzeSpotSuitability:
    def test_with_data(self):
        eng = _engine()
        eng.record_usage(
            "m5.xlarge",
            market=SpotMarket.AWS_SPOT,
            savings_pct=60.0,
        )
        result = eng.analyze_spot_suitability("m5.xlarge")
        assert result["instance_type"] == "m5.xlarge"
        assert result["savings_pct"] == 60.0

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_spot_suitability("ghost")
        assert result["status"] == "no_data"


class TestIdentifyHighSavings:
    def test_with_high(self):
        eng = _engine(min_savings_pct=20.0)
        eng.record_usage("i1", savings_pct=60.0)
        eng.record_usage("i2", savings_pct=10.0)
        results = eng.identify_high_savings_opportunities()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_high_savings_opportunities() == []


class TestRankByInterruptionRisk:
    def test_with_data(self):
        eng = _engine()
        eng.record_usage("i1", interruption_risk=InterruptionRisk.LOW)
        eng.record_usage("i2", interruption_risk=InterruptionRisk.VERY_HIGH)
        results = eng.rank_by_interruption_risk()
        assert results[0]["interruption_risk"] == "very_high"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_interruption_risk() == []


class TestEstimateTotalSavings:
    def test_with_data(self):
        eng = _engine()
        eng.record_usage("i1", monthly_cost=50.0, on_demand_cost=100.0)
        eng.record_usage("i2", monthly_cost=30.0, on_demand_cost=80.0)
        result = eng.estimate_total_savings()
        assert result["total_savings"] == 100.0
        assert result["record_count"] == 2

    def test_empty(self):
        eng = _engine()
        result = eng.estimate_total_savings()
        assert result["total_savings"] == 0.0


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(min_savings_pct=20.0)
        eng.record_usage(
            "i1",
            savings_pct=60.0,
            interruption_risk=InterruptionRisk.HIGH,
        )
        eng.add_recommendation("i1")
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.total_recommendations == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "meets targets" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_usage("i1")
        eng.add_recommendation("i1")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._recommendations) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_recommendations"] == 0
        assert stats["market_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_usage("i1", market=SpotMarket.AWS_SPOT)
        eng.record_usage("i2", market=SpotMarket.GCP_PREEMPTIBLE)
        eng.add_recommendation("i1")
        stats = eng.get_stats()
        assert stats["total_records"] == 2
        assert stats["total_recommendations"] == 1
        assert stats["unique_instance_types"] == 2
