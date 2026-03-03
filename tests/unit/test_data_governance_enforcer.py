"""Tests for shieldops.compliance.data_governance_enforcer — DataGovernanceEnforcer."""

from __future__ import annotations

from shieldops.compliance.data_governance_enforcer import (
    DataClassification,
    DataGovernanceEnforcer,
    DataGovernanceReport,
    GovernanceAction,
    GovernanceAnalysis,
    GovernanceRecord,
    GovernanceStatus,
)


def _engine(**kw) -> DataGovernanceEnforcer:
    return DataGovernanceEnforcer(**kw)


class TestEnums:
    def test_classification_public(self):
        assert DataClassification.PUBLIC == "public"

    def test_classification_internal(self):
        assert DataClassification.INTERNAL == "internal"

    def test_classification_confidential(self):
        assert DataClassification.CONFIDENTIAL == "confidential"

    def test_classification_restricted(self):
        assert DataClassification.RESTRICTED == "restricted"

    def test_classification_top_secret(self):
        assert DataClassification.TOP_SECRET == "top_secret"  # noqa: S105

    def test_action_classify(self):
        assert GovernanceAction.CLASSIFY == "classify"

    def test_action_encrypt(self):
        assert GovernanceAction.ENCRYPT == "encrypt"

    def test_action_mask(self):
        assert GovernanceAction.MASK == "mask"

    def test_action_retain(self):
        assert GovernanceAction.RETAIN == "retain"

    def test_action_delete(self):
        assert GovernanceAction.DELETE == "delete"

    def test_status_compliant(self):
        assert GovernanceStatus.COMPLIANT == "compliant"

    def test_status_non_compliant(self):
        assert GovernanceStatus.NON_COMPLIANT == "non_compliant"

    def test_status_remediation(self):
        assert GovernanceStatus.REMEDIATION == "remediation"

    def test_status_exception(self):
        assert GovernanceStatus.EXCEPTION == "exception"

    def test_status_unknown(self):
        assert GovernanceStatus.UNKNOWN == "unknown"


class TestModels:
    def test_record_defaults(self):
        r = GovernanceRecord()
        assert r.id
        assert r.data_asset == ""
        assert r.data_classification == DataClassification.PUBLIC
        assert r.governance_action == GovernanceAction.CLASSIFY
        assert r.governance_status == GovernanceStatus.COMPLIANT
        assert r.governance_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_analysis_defaults(self):
        a = GovernanceAnalysis()
        assert a.id
        assert a.data_asset == ""
        assert a.data_classification == DataClassification.PUBLIC
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = DataGovernanceReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_governance_score == 0.0
        assert r.by_classification == {}
        assert r.by_action == {}
        assert r.by_status == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


class TestRecord:
    def test_basic(self):
        eng = _engine()
        r = eng.record_governance(
            data_asset="customer-db",
            data_classification=DataClassification.CONFIDENTIAL,
            governance_action=GovernanceAction.ENCRYPT,
            governance_status=GovernanceStatus.COMPLIANT,
            governance_score=85.0,
            service="data-platform",
            team="data-eng",
        )
        assert r.data_asset == "customer-db"
        assert r.data_classification == DataClassification.CONFIDENTIAL
        assert r.governance_score == 85.0
        assert r.service == "data-platform"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_governance(data_asset=f"asset-{i}")
        assert len(eng._records) == 3


class TestGet:
    def test_found(self):
        eng = _engine()
        r = eng.record_governance(data_asset="test")
        assert eng.get_record(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_record("nonexistent") is None


class TestList:
    def test_list_all(self):
        eng = _engine()
        eng.record_governance(data_asset="a")
        eng.record_governance(data_asset="b")
        assert len(eng.list_records()) == 2

    def test_filter_by_data_classification(self):
        eng = _engine()
        eng.record_governance(data_asset="a", data_classification=DataClassification.PUBLIC)
        eng.record_governance(data_asset="b", data_classification=DataClassification.CONFIDENTIAL)
        assert len(eng.list_records(data_classification=DataClassification.PUBLIC)) == 1

    def test_filter_by_governance_status(self):
        eng = _engine()
        eng.record_governance(data_asset="a", governance_status=GovernanceStatus.COMPLIANT)
        eng.record_governance(data_asset="b", governance_status=GovernanceStatus.NON_COMPLIANT)
        assert len(eng.list_records(governance_status=GovernanceStatus.COMPLIANT)) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_governance(data_asset="a", team="sec")
        eng.record_governance(data_asset="b", team="ops")
        assert len(eng.list_records(team="sec")) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_governance(data_asset=f"d-{i}")
        assert len(eng.list_records(limit=5)) == 5


class TestAddAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            data_asset="test",
            analysis_score=88.5,
            breached=True,
            description="governance gap",
        )
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(data_asset=f"t-{i}")
        assert len(eng._analyses) == 2


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_governance(
            data_asset="a",
            data_classification=DataClassification.PUBLIC,
            governance_score=90.0,
        )
        eng.record_governance(
            data_asset="b",
            data_classification=DataClassification.PUBLIC,
            governance_score=70.0,
        )
        result = eng.analyze_distribution()
        assert "public" in result
        assert result["public"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_distribution() == {}


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_governance(data_asset="a", governance_score=60.0)
        eng.record_governance(data_asset="b", governance_score=90.0)
        assert len(eng.identify_gaps()) == 1

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_governance(data_asset="a", governance_score=50.0)
        eng.record_governance(data_asset="b", governance_score=30.0)
        results = eng.identify_gaps()
        assert results[0]["governance_score"] == 30.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_gaps() == []


class TestRankByScore:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_governance(data_asset="a", service="auth", governance_score=90.0)
        eng.record_governance(data_asset="b", service="api", governance_score=50.0)
        results = eng.rank_by_score()
        assert results[0]["service"] == "api"

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_score() == []


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(data_asset="t", analysis_score=50.0)
        assert eng.detect_trends()["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(data_asset="a", analysis_score=20.0)
        eng.add_analysis(data_asset="b", analysis_score=20.0)
        eng.add_analysis(data_asset="c", analysis_score=80.0)
        eng.add_analysis(data_asset="d", analysis_score=80.0)
        assert eng.detect_trends()["trend"] == "improving"

    def test_insufficient_data(self):
        eng = _engine()
        assert eng.detect_trends()["trend"] == "insufficient_data"


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_governance(data_asset="test", governance_score=50.0)
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
        eng.record_governance(data_asset="test")
        eng.add_analysis(data_asset="test")
        assert eng.clear_data() == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0

    def test_populated(self):
        eng = _engine()
        eng.record_governance(data_asset="test", service="auth", team="sec")
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
