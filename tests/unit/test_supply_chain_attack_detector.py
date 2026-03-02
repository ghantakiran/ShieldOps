"""Tests for shieldops.security.supply_chain_attack_detector — SupplyChainAttackDetector."""

from __future__ import annotations

from shieldops.security.supply_chain_attack_detector import (
    AttackType,
    ComponentType,
    DetectionConfidence,
    SupplyChainAnalysis,
    SupplyChainAttackDetector,
    SupplyChainRecord,
    SupplyChainReport,
)


def _engine(**kw) -> SupplyChainAttackDetector:
    return SupplyChainAttackDetector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_attacktype_dependency_confusion(self):
        assert AttackType.DEPENDENCY_CONFUSION == "dependency_confusion"

    def test_attacktype_typosquatting(self):
        assert AttackType.TYPOSQUATTING == "typosquatting"

    def test_attacktype_build_compromise(self):
        assert AttackType.BUILD_COMPROMISE == "build_compromise"

    def test_attacktype_malicious_update(self):
        assert AttackType.MALICIOUS_UPDATE == "malicious_update"

    def test_attacktype_compromised_registry(self):
        assert AttackType.COMPROMISED_REGISTRY == "compromised_registry"

    def test_componenttype_npm_package(self):
        assert ComponentType.NPM_PACKAGE == "npm_package"

    def test_componenttype_pypi_package(self):
        assert ComponentType.PYPI_PACKAGE == "pypi_package"

    def test_componenttype_docker_image(self):
        assert ComponentType.DOCKER_IMAGE == "docker_image"

    def test_componenttype_git_repo(self):
        assert ComponentType.GIT_REPO == "git_repo"

    def test_componenttype_binary_artifact(self):
        assert ComponentType.BINARY_ARTIFACT == "binary_artifact"

    def test_detectionconfidence_confirmed(self):
        assert DetectionConfidence.CONFIRMED == "confirmed"

    def test_detectionconfidence_high(self):
        assert DetectionConfidence.HIGH == "high"

    def test_detectionconfidence_medium(self):
        assert DetectionConfidence.MEDIUM == "medium"

    def test_detectionconfidence_low(self):
        assert DetectionConfidence.LOW == "low"

    def test_detectionconfidence_suspected(self):
        assert DetectionConfidence.SUSPECTED == "suspected"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_supplychainrecord_defaults(self):
        r = SupplyChainRecord()
        assert r.id
        assert r.component_name == ""
        assert r.risk_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_supplychainanalysis_defaults(self):
        c = SupplyChainAnalysis()
        assert c.id
        assert c.component_name == ""
        assert c.analysis_score == 0.0
        assert c.threshold == 0.0
        assert c.breached == 0.0
        assert c.description == ""
        assert c.created_at > 0

    def test_supplychainreport_defaults(self):
        r = SupplyChainReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.low_confidence_count == 0
        assert r.avg_risk_score == 0
        assert r.by_attack_type == {}
        assert r.by_component_type == {}
        assert r.by_confidence == {}
        assert r.top_low_confidence == []
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
            component_name="test-item",
            attack_type=AttackType.TYPOSQUATTING,
            risk_score=92.0,
            service="auth-svc",
            team="security",
        )
        assert r.component_name == "test-item"
        assert r.risk_score == 92.0
        assert r.service == "auth-svc"
        assert r.team == "security"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_detection(component_name=f"ITEM-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_detection
# ---------------------------------------------------------------------------


class TestGetDetection:
    def test_found(self):
        eng = _engine()
        r = eng.record_detection(component_name="test-item")
        result = eng.get_detection(r.id)
        assert result is not None
        assert result.component_name == "test-item"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_detection("nonexistent") is None


# ---------------------------------------------------------------------------
# list_detections
# ---------------------------------------------------------------------------


class TestListDetections:
    def test_list_all(self):
        eng = _engine()
        eng.record_detection(component_name="ITEM-001")
        eng.record_detection(component_name="ITEM-002")
        assert len(eng.list_detections()) == 2

    def test_filter_by_attack_type(self):
        eng = _engine()
        eng.record_detection(component_name="ITEM-001", attack_type=AttackType.DEPENDENCY_CONFUSION)
        eng.record_detection(component_name="ITEM-002", attack_type=AttackType.TYPOSQUATTING)
        results = eng.list_detections(attack_type=AttackType.DEPENDENCY_CONFUSION)
        assert len(results) == 1

    def test_filter_by_component_type(self):
        eng = _engine()
        eng.record_detection(component_name="ITEM-001", component_type=ComponentType.NPM_PACKAGE)
        eng.record_detection(component_name="ITEM-002", component_type=ComponentType.PYPI_PACKAGE)
        results = eng.list_detections(component_type=ComponentType.NPM_PACKAGE)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_detection(component_name="ITEM-001", team="security")
        eng.record_detection(component_name="ITEM-002", team="platform")
        results = eng.list_detections(team="security")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_detection(component_name=f"ITEM-{i}")
        assert len(eng.list_detections(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            component_name="test-item",
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="test description",
        )
        assert a.component_name == "test-item"
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(component_name=f"ITEM-{i}")
        assert len(eng._analyses) == 2


# ---------------------------------------------------------------------------
# analyze_attack_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_detection(
            component_name="ITEM-001", attack_type=AttackType.DEPENDENCY_CONFUSION, risk_score=90.0
        )
        eng.record_detection(
            component_name="ITEM-002", attack_type=AttackType.DEPENDENCY_CONFUSION, risk_score=70.0
        )
        result = eng.analyze_attack_distribution()
        assert "dependency_confusion" in result
        assert result["dependency_confusion"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_attack_distribution() == {}


# ---------------------------------------------------------------------------
# identify_low_confidence_detections
# ---------------------------------------------------------------------------


class TestIdentifyProblems:
    def test_detects_threshold(self):
        eng = _engine(supply_chain_risk_threshold=55.0)
        eng.record_detection(component_name="ITEM-001", risk_score=30.0)
        eng.record_detection(component_name="ITEM-002", risk_score=90.0)
        results = eng.identify_low_confidence_detections()
        assert len(results) == 1
        assert results[0]["component_name"] == "ITEM-001"

    def test_sorted_ascending(self):
        eng = _engine(supply_chain_risk_threshold=55.0)
        eng.record_detection(component_name="ITEM-001", risk_score=50.0)
        eng.record_detection(component_name="ITEM-002", risk_score=30.0)
        results = eng.identify_low_confidence_detections()
        assert len(results) == 2
        assert results[0]["risk_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_low_confidence_detections() == []


# ---------------------------------------------------------------------------
# rank_by_risk_score
# ---------------------------------------------------------------------------


class TestRankByScore:
    def test_sorted(self):
        eng = _engine()
        eng.record_detection(component_name="ITEM-001", service="auth-svc", risk_score=90.0)
        eng.record_detection(component_name="ITEM-002", service="api-gw", risk_score=50.0)
        results = eng.rank_by_risk_score()
        assert len(results) == 2
        assert results[0]["service"] == "api-gw"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_risk_score() == []


# ---------------------------------------------------------------------------
# detect_risk_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(component_name="ITEM-001", analysis_score=50.0)
        result = eng.detect_risk_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(component_name="ITEM-001", analysis_score=20.0)
        eng.add_analysis(component_name="ITEM-002", analysis_score=20.0)
        eng.add_analysis(component_name="ITEM-003", analysis_score=80.0)
        eng.add_analysis(component_name="ITEM-004", analysis_score=80.0)
        result = eng.detect_risk_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_risk_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(supply_chain_risk_threshold=55.0)
        eng.record_detection(component_name="test-item", risk_score=30.0)
        report = eng.generate_report()
        assert isinstance(report, SupplyChainReport)
        assert report.total_records == 1
        assert report.low_confidence_count == 1
        assert len(report.top_low_confidence) == 1
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
        eng.record_detection(component_name="ITEM-001")
        eng.add_analysis(component_name="ITEM-001")
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
            component_name="ITEM-001",
            attack_type=AttackType.DEPENDENCY_CONFUSION,
            service="auth-svc",
            team="security",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
