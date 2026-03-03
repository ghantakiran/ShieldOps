"""Tests for shieldops.billing.finops_maturity_scorer."""

from __future__ import annotations

from shieldops.billing.finops_maturity_scorer import (
    AssessmentArea,
    FinOpsMaturityReport,
    FinOpsMaturityScorer,
    MaturityAnalysis,
    MaturityDomain,
    MaturityLevel,
    MaturityRecord,
)


def _engine(**kw) -> FinOpsMaturityScorer:
    return FinOpsMaturityScorer(**kw)


class TestEnums:
    def test_maturitydomain_visibility(self):
        assert MaturityDomain.VISIBILITY == "visibility"

    def test_maturitydomain_optimization(self):
        assert MaturityDomain.OPTIMIZATION == "optimization"

    def test_maturitydomain_operations(self):
        assert MaturityDomain.OPERATIONS == "operations"

    def test_maturitydomain_governance(self):
        assert MaturityDomain.GOVERNANCE == "governance"

    def test_maturitydomain_culture(self):
        assert MaturityDomain.CULTURE == "culture"

    def test_maturitylevel_crawl(self):
        assert MaturityLevel.CRAWL == "crawl"

    def test_maturitylevel_walk(self):
        assert MaturityLevel.WALK == "walk"

    def test_maturitylevel_run(self):
        assert MaturityLevel.RUN == "run"

    def test_maturitylevel_fly(self):
        assert MaturityLevel.FLY == "fly"

    def test_maturitylevel_optimized(self):
        assert MaturityLevel.OPTIMIZED == "optimized"

    def test_assessmentarea_cost_allocation(self):
        assert AssessmentArea.COST_ALLOCATION == "cost_allocation"

    def test_assessmentarea_forecasting(self):
        assert AssessmentArea.FORECASTING == "forecasting"

    def test_assessmentarea_anomaly_detection(self):
        assert AssessmentArea.ANOMALY_DETECTION == "anomaly_detection"

    def test_assessmentarea_rightsizing(self):
        assert AssessmentArea.RIGHTSIZING == "rightsizing"

    def test_assessmentarea_commitment(self):
        assert AssessmentArea.COMMITMENT == "commitment"


class TestModels:
    def test_maturity_record_defaults(self):
        r = MaturityRecord()
        assert r.id
        assert r.maturity_domain == MaturityDomain.VISIBILITY
        assert r.maturity_level == MaturityLevel.CRAWL
        assert r.assessment_area == AssessmentArea.COST_ALLOCATION
        assert r.maturity_score == 0.0
        assert r.target_score == 100.0
        assert r.gap == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_maturity_analysis_defaults(self):
        a = MaturityAnalysis()
        assert a.id
        assert a.maturity_domain == MaturityDomain.VISIBILITY
        assert a.analysis_score == 0.0
        assert a.breached is False
        assert a.created_at > 0

    def test_finops_maturity_report_defaults(self):
        r = FinOpsMaturityReport()
        assert r.id
        assert r.total_records == 0
        assert r.mature_count == 0
        assert r.avg_maturity_score == 0.0
        assert r.by_maturity_domain == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0


class TestRecordMaturity:
    def test_basic(self):
        eng = _engine()
        r = eng.record_maturity(
            maturity_domain=MaturityDomain.OPTIMIZATION,
            maturity_level=MaturityLevel.RUN,
            assessment_area=AssessmentArea.RIGHTSIZING,
            maturity_score=75.0,
            target_score=100.0,
            gap=25.0,
            service="cloud-platform",
            team="finops",
        )
        assert r.maturity_domain == MaturityDomain.OPTIMIZATION
        assert r.maturity_score == 75.0
        assert r.team == "finops"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for _i in range(5):
            eng.record_maturity(maturity_domain=MaturityDomain.VISIBILITY)
        assert len(eng._records) == 3


class TestGetMaturity:
    def test_found(self):
        eng = _engine()
        r = eng.record_maturity(maturity_score=60.0)
        result = eng.get_maturity(r.id)
        assert result is not None
        assert result.maturity_score == 60.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_maturity("nonexistent") is None


class TestListMaturities:
    def test_list_all(self):
        eng = _engine()
        eng.record_maturity(maturity_domain=MaturityDomain.VISIBILITY)
        eng.record_maturity(maturity_domain=MaturityDomain.GOVERNANCE)
        assert len(eng.list_maturities()) == 2

    def test_filter_by_domain(self):
        eng = _engine()
        eng.record_maturity(maturity_domain=MaturityDomain.VISIBILITY)
        eng.record_maturity(maturity_domain=MaturityDomain.CULTURE)
        results = eng.list_maturities(maturity_domain=MaturityDomain.VISIBILITY)
        assert len(results) == 1

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_maturity(maturity_level=MaturityLevel.CRAWL)
        eng.record_maturity(maturity_level=MaturityLevel.RUN)
        results = eng.list_maturities(maturity_level=MaturityLevel.CRAWL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_maturity(team="finops")
        eng.record_maturity(team="platform")
        results = eng.list_maturities(team="finops")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for _i in range(10):
            eng.record_maturity(maturity_domain=MaturityDomain.VISIBILITY)
        assert len(eng.list_maturities(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            maturity_domain=MaturityDomain.GOVERNANCE,
            analysis_score=78.0,
            threshold=70.0,
            breached=True,
            description="governance maturity gap detected",
        )
        assert a.maturity_domain == MaturityDomain.GOVERNANCE
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for _i in range(5):
            eng.add_analysis(maturity_domain=MaturityDomain.VISIBILITY)
        assert len(eng._analyses) == 2


class TestAnalyzeDomainDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_maturity(maturity_domain=MaturityDomain.OPTIMIZATION, maturity_score=60.0)
        eng.record_maturity(maturity_domain=MaturityDomain.OPTIMIZATION, maturity_score=80.0)
        result = eng.analyze_domain_distribution()
        assert "optimization" in result
        assert result["optimization"]["count"] == 2
        assert result["optimization"]["avg_maturity_score"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_domain_distribution() == {}


class TestIdentifyMaturityGaps:
    def test_detects_below_threshold(self):
        eng = _engine(maturity_threshold=70.0)
        eng.record_maturity(maturity_score=50.0)
        eng.record_maturity(maturity_score=90.0)
        results = eng.identify_maturity_gaps()
        assert len(results) == 1

    def test_sorted_ascending(self):
        eng = _engine(maturity_threshold=80.0)
        eng.record_maturity(maturity_score=30.0)
        eng.record_maturity(maturity_score=60.0)
        results = eng.identify_maturity_gaps()
        assert results[0]["maturity_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_maturity_gaps() == []


class TestRankByMaturityScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_maturity(team="finops", maturity_score=80.0)
        eng.record_maturity(team="ops", maturity_score=40.0)
        results = eng.rank_by_maturity_score()
        assert results[0]["team"] == "ops"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_maturity_score() == []


class TestDetectMaturityTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(analysis_score=50.0)
        result = eng.detect_maturity_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(analysis_score=10.0)
        eng.add_analysis(analysis_score=10.0)
        eng.add_analysis(analysis_score=80.0)
        eng.add_analysis(analysis_score=80.0)
        result = eng.detect_maturity_trends()
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_maturity_trends()
        assert result["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(maturity_threshold=70.0)
        eng.record_maturity(
            maturity_domain=MaturityDomain.OPTIMIZATION,
            maturity_level=MaturityLevel.WALK,
            assessment_area=AssessmentArea.RIGHTSIZING,
            maturity_score=80.0,
        )
        report = eng.generate_report()
        assert isinstance(report, FinOpsMaturityReport)
        assert report.total_records == 1
        assert report.mature_count == 1

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "target" in report.recommendations[0]


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_maturity(maturity_domain=MaturityDomain.VISIBILITY)
        eng.add_analysis(maturity_domain=MaturityDomain.VISIBILITY)
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["maturity_domain_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_maturity(
            maturity_domain=MaturityDomain.OPTIMIZATION,
            service="cloud-platform",
            team="finops",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert "optimization" in stats["maturity_domain_distribution"]
