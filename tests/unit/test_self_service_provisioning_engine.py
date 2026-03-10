"""Tests for self_service_provisioning_engine — SelfServiceProvisioningEngine."""

from __future__ import annotations

from shieldops.operations.self_service_provisioning_engine import (
    ApprovalMode,
    ProvisioningStatus,
    ProvisioningType,
    SelfServiceProvisioningEngine,
)


def _engine(**kw) -> SelfServiceProvisioningEngine:
    return SelfServiceProvisioningEngine(**kw)


class TestEnums:
    def test_provisioningtype_compute(self):
        assert ProvisioningType.COMPUTE == "compute"

    def test_provisioningtype_database(self):
        assert ProvisioningType.DATABASE == "database"

    def test_provisioningtype_storage(self):
        assert ProvisioningType.STORAGE == "storage"

    def test_provisioningtype_network(self):
        assert ProvisioningType.NETWORK == "network"

    def test_provisioningtype_kubernetes(self):
        assert ProvisioningType.KUBERNETES == "kubernetes"

    def test_provisioningstatus_pending(self):
        assert ProvisioningStatus.PENDING == "pending"

    def test_provisioningstatus_approved(self):
        assert ProvisioningStatus.APPROVED == "approved"

    def test_provisioningstatus_provisioning(self):
        assert ProvisioningStatus.PROVISIONING == "provisioning"

    def test_provisioningstatus_completed(self):
        assert ProvisioningStatus.COMPLETED == "completed"

    def test_provisioningstatus_failed(self):
        assert ProvisioningStatus.FAILED == "failed"

    def test_approvalmode_auto_approved(self):
        assert ApprovalMode.AUTO_APPROVED == "auto_approved"

    def test_approvalmode_manual_review(self):
        assert ApprovalMode.MANUAL_REVIEW == "manual_review"

    def test_approvalmode_policy_gated(self):
        assert ApprovalMode.POLICY_GATED == "policy_gated"

    def test_approvalmode_escalated(self):
        assert ApprovalMode.ESCALATED == "escalated"

    def test_approvalmode_denied(self):
        assert ApprovalMode.DENIED == "denied"


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_item(
            name="test-001",
            provisioning_type=ProvisioningType.COMPUTE,
            score=85.0,
            service="svc-a",
            team="team-a",
        )
        assert r.name == "test-001"
        assert r.provisioning_type == ProvisioningType.COMPUTE
        assert r.score == 85.0
        assert r.service == "svc-a"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_item(name=f"item-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_item(name="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_item(name="a")
        eng.record_item(name="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_provisioning_type(self):
        eng = _engine()
        eng.record_item(
            name="a",
            provisioning_type=ProvisioningType.COMPUTE,
        )
        eng.record_item(
            name="b",
            provisioning_type=ProvisioningType.DATABASE,
        )
        result = eng.list_records(
            provisioning_type=ProvisioningType.COMPUTE,
        )
        assert len(result) == 1

    def test_filter_by_provisioning_status(self):
        eng = _engine()
        eng.record_item(
            name="a",
            provisioning_status=ProvisioningStatus.PENDING,
        )
        eng.record_item(
            name="b",
            provisioning_status=ProvisioningStatus.APPROVED,
        )
        result = eng.list_records(
            provisioning_status=ProvisioningStatus.PENDING,
        )
        assert len(result) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_item(name="a", team="sec")
        eng.record_item(name="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_item(name=f"a-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            name="test",
            analysis_score=88.5,
            breached=True,
            description="test analysis",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(name=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_item(
            name="a",
            provisioning_type=ProvisioningType.COMPUTE,
            score=90.0,
        )
        eng.record_item(
            name="b",
            provisioning_type=ProvisioningType.COMPUTE,
            score=70.0,
        )
        result = eng.analyze_distribution()
        assert "compute" in result
        assert result["compute"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=60.0)
        eng.record_item(name="b", score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="a", score=50.0)
        eng.record_item(name="b", score=30.0)
        results = eng.identify_gaps()
        assert results[0]["score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_item(
            name="a",
            service="auth",
            score=90.0,
        )
        eng.record_item(
            name="b",
            service="api",
            score=50.0,
        )
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(
                name="t",
                analysis_score=50.0,
            )
        result = eng.detect_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(
            name="a",
            analysis_score=20.0,
        )
        eng.add_analysis(
            name="b",
            analysis_score=20.0,
        )
        eng.add_analysis(
            name="c",
            analysis_score=80.0,
        )
        eng.add_analysis(
            name="d",
            analysis_score=80.0,
        )
        result = eng.detect_trends()
        assert result["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_trends()
        assert result["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_item(name="test", score=50.0)
        report = eng.generate_report()
        assert report.total_records == 1
        assert report.gap_count == 1
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_item(name="test")
        eng.add_analysis(name="test")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_item(
            name="test",
            service="auth",
            team="sec",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
