"""Tests for shieldops.security.security_maturity_model — SecurityMaturityModel."""

from __future__ import annotations

from shieldops.security.security_maturity_model import (
    AssessmentMethod,
    MaturityAnalysis,
    MaturityDomain,
    MaturityRecord,
    MaturityReport,
    MaturityTier,
    SecurityMaturityModel,
)


def _engine(**kw) -> SecurityMaturityModel:
    return SecurityMaturityModel(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_maturitydomain_identify(self):
        assert MaturityDomain.IDENTIFY == "identify"

    def test_maturitydomain_protect(self):
        assert MaturityDomain.PROTECT == "protect"

    def test_maturitydomain_detect(self):
        assert MaturityDomain.DETECT == "detect"

    def test_maturitydomain_respond(self):
        assert MaturityDomain.RESPOND == "respond"

    def test_maturitydomain_recover(self):
        assert MaturityDomain.RECOVER == "recover"

    def test_maturitytier_adaptive(self):
        assert MaturityTier.ADAPTIVE == "adaptive"

    def test_maturitytier_repeatable(self):
        assert MaturityTier.REPEATABLE == "repeatable"

    def test_maturitytier_risk_informed(self):
        assert MaturityTier.RISK_INFORMED == "risk_informed"

    def test_maturitytier_partial(self):
        assert MaturityTier.PARTIAL == "partial"

    def test_maturitytier_initial(self):
        assert MaturityTier.INITIAL == "initial"

    def test_assessmentmethod_self_assessment(self):
        assert AssessmentMethod.SELF_ASSESSMENT == "self_assessment"

    def test_assessmentmethod_external_audit(self):
        assert AssessmentMethod.EXTERNAL_AUDIT == "external_audit"

    def test_assessmentmethod_peer_review(self):
        assert AssessmentMethod.PEER_REVIEW == "peer_review"

    def test_assessmentmethod_automated(self):
        assert AssessmentMethod.AUTOMATED == "automated"

    def test_assessmentmethod_hybrid(self):
        assert AssessmentMethod.HYBRID == "hybrid"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_maturityrecord_defaults(self):
        r = MaturityRecord()
        assert r.id
        assert r.domain_name == ""
        assert r.maturity_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_maturityanalysis_defaults(self):
        c = MaturityAnalysis()
        assert c.id
        assert c.domain_name == ""
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached == 0.0
        assert c.description == ""
        assert c.created_at > 0

    def test_maturityreport_defaults(self):
        r = MaturityReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_maturity_count == 0
        assert r.avg_maturity_score == 0
        assert r.by_domain == {}
        assert r.by_tier == {}
        assert r.by_method == {}
        assert r.top_low_maturity == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_assessment
# ---------------------------------------------------------------------------


class TestRecordAssessment:
    def test_basic(self):
        eng = _engine()
        r = eng.record_assessment(
            domain_name="test-item",
            maturity_domain=MaturityDomain.PROTECT,
            maturity_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.domain_name == "test-item"
        assert r.maturity_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_assessment(domain_name=f"ITEM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_assessment
# ---------------------------------------------------------------------------


class TestGetAssessment:
    def test_found(self):
        eng = _engine()
        r = eng.record_assessment(domain_name="test-item")
        result = eng.get_assessment(r.id)
        assert result is not None
        assert result.domain_name == "test-item"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_assessment("nonexistent") is None


# ---------------------------------------------------------------------------
# list_assessments
# ---------------------------------------------------------------------------


class TestListAssessments:
    def test_list_all(self):
        eng = _engine()
        eng.record_assessment(domain_name="ITEM-001")
        eng.record_assessment(domain_name="ITEM-002")
        assert len(eng.list_assessments()) == 2

    def test_filter_by_maturity_domain(self):
        eng = _engine()
        eng.record_assessment(domain_name="ITEM-001", maturity_domain=MaturityDomain.IDENTIFY)
        eng.record_assessment(domain_name="ITEM-002", maturity_domain=MaturityDomain.PROTECT)
        results = eng.list_assessments(maturity_domain=MaturityDomain.IDENTIFY)
        assert len(results) == 1

    def test_filter_by_maturity_tier(self):
        eng = _engine()
        eng.record_assessment(domain_name="ITEM-001", maturity_tier=MaturityTier.ADAPTIVE)
        eng.record_assessment(domain_name="ITEM-002", maturity_tier=MaturityTier.REPEATABLE)
        results = eng.list_assessments(maturity_tier=MaturityTier.ADAPTIVE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_assessment(domain_name="ITEM-001", team="security")
        eng.record_assessment(domain_name="ITEM-002", team="platform")
        results = eng.list_assessments(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_assessment(domain_name=f"ITEM-{i}")
        assert len(eng.list_assessments(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            domain_name="test-item",
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="test description",
        )
        assert a.domain_name == "test-item"
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(domain_name=f"ITEM-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_maturity_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_assessment(
            domain_name="ITEM-001", maturity_domain=MaturityDomain.IDENTIFY, maturity_score=90.0
        )
        eng.record_assessment(
            domain_name="ITEM-002", maturity_domain=MaturityDomain.IDENTIFY, maturity_score=70.0
        )
        result = eng.analyze_maturity_distribution()
        assert "identify" in result
        assert result["identify"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_maturity_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_maturity_assessments
# ---------------------------------------------------------------------------


class TestIdentifyProblems:
    def test_detects_threshold(self):
        eng = _engine(maturity_threshold=70.0)
        eng.record_assessment(domain_name="ITEM-001", maturity_score=30.0)
        eng.record_assessment(domain_name="ITEM-002", maturity_score=90.0)
        results = eng.identify_low_maturity_assessments()
        assert len(results) == 1
        assert results[0]["domain_name"] == "ITEM-001"

    def test_sorted_ascending(self):
        eng = _engine(maturity_threshold=70.0)
        eng.record_assessment(domain_name="ITEM-001", maturity_score=50.0)
        eng.record_assessment(domain_name="ITEM-002", maturity_score=30.0)
        results = eng.identify_low_maturity_assessments()
        assert len(results) == 2
        assert results[0]["maturity_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_maturity_assessments() == []


# ---------------------------------------------------------------------------
# rank_by_maturity
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted(self):
        eng = _engine()
        eng.record_assessment(domain_name="ITEM-001", service="auth-svc", maturity_score=90.0)
        eng.record_assessment(domain_name="ITEM-002", service="api-gw", maturity_score=50.0)
        results = eng.rank_by_maturity()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_maturity() == []


# ---------------------------------------------------------------------------
# detect_maturity_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(domain_name="ITEM-001", analysis_score=50.0)
        result = eng.detect_maturity_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(domain_name="ITEM-001", analysis_score=20.0)
        eng.add_analysis(domain_name="ITEM-002", analysis_score=20.0)
        eng.add_analysis(domain_name="ITEM-003", analysis_score=80.0)
        eng.add_analysis(domain_name="ITEM-004", analysis_score=80.0)
        result = eng.detect_maturity_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_maturity_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(maturity_threshold=70.0)
        eng.record_assessment(domain_name="test-item", maturity_score=30.0)
        report = eng.generate_report()
        assert isinstance(report, MaturityReport)
        assert report.total_records == 1
        assert report.low_maturity_count == 1
        assert len(report.top_low_maturity) == 1
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
        eng.record_assessment(domain_name="ITEM-001")
        eng.add_analysis(domain_name="ITEM-001")
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
        eng.record_assessment(
            domain_name="ITEM-001",
            maturity_domain=MaturityDomain.IDENTIFY,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
