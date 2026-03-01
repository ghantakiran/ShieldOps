"""Tests for shieldops.topology.api_contract_drift — APIContractDriftDetector."""

from __future__ import annotations

from shieldops.topology.api_contract_drift import (
    APIContractDriftDetector,
    APIContractDriftReport,
    ContractDriftRecord,
    DriftDetail,
    DriftSeverity,
    DriftSource,
    DriftType,
)


def _engine(**kw) -> APIContractDriftDetector:
    return APIContractDriftDetector(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_field_removed(self):
        assert DriftType.FIELD_REMOVED == "field_removed"

    def test_type_type_changed(self):
        assert DriftType.TYPE_CHANGED == "type_changed"

    def test_type_endpoint_removed(self):
        assert DriftType.ENDPOINT_REMOVED == "endpoint_removed"

    def test_type_schema_mismatch(self):
        assert DriftType.SCHEMA_MISMATCH == "schema_mismatch"

    def test_type_version_conflict(self):
        assert DriftType.VERSION_CONFLICT == "version_conflict"

    def test_severity_breaking(self):
        assert DriftSeverity.BREAKING == "breaking"

    def test_severity_major(self):
        assert DriftSeverity.MAJOR == "major"

    def test_severity_minor(self):
        assert DriftSeverity.MINOR == "minor"

    def test_severity_cosmetic(self):
        assert DriftSeverity.COSMETIC == "cosmetic"

    def test_severity_none(self):
        assert DriftSeverity.NONE == "none"

    def test_source_producer_change(self):
        assert DriftSource.PRODUCER_CHANGE == "producer_change"

    def test_source_consumer_change(self):
        assert DriftSource.CONSUMER_CHANGE == "consumer_change"

    def test_source_schema_evolution(self):
        assert DriftSource.SCHEMA_EVOLUTION == "schema_evolution"

    def test_source_documentation_gap(self):
        assert DriftSource.DOCUMENTATION_GAP == "documentation_gap"

    def test_source_deployment_mismatch(self):
        assert DriftSource.DEPLOYMENT_MISMATCH == "deployment_mismatch"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_contract_drift_record_defaults(self):
        r = ContractDriftRecord()
        assert r.id
        assert r.contract_id == ""
        assert r.drift_type == DriftType.FIELD_REMOVED
        assert r.drift_severity == DriftSeverity.NONE
        assert r.drift_source == DriftSource.PRODUCER_CHANGE
        assert r.drift_score == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_drift_detail_defaults(self):
        d = DriftDetail()
        assert d.id
        assert d.contract_id == ""
        assert d.drift_type == DriftType.FIELD_REMOVED
        assert d.detail_score == 0.0
        assert d.threshold == 0.0
        assert d.breached is False
        assert d.description == ""
        assert d.created_at > 0

    def test_api_contract_drift_report_defaults(self):
        r = APIContractDriftReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_details == 0
        assert r.breaking_drifts == 0
        assert r.avg_drift_score == 0.0
        assert r.by_drift_type == {}
        assert r.by_severity == {}
        assert r.by_source == {}
        assert r.top_drifting == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_drift
# ---------------------------------------------------------------------------


class TestRecordDrift:
    def test_basic(self):
        eng = _engine()
        r = eng.record_drift(
            contract_id="CTR-001",
            drift_type=DriftType.FIELD_REMOVED,
            drift_severity=DriftSeverity.BREAKING,
            drift_source=DriftSource.PRODUCER_CHANGE,
            drift_score=90.0,
            service="user-svc",
            team="platform",
        )
        assert r.contract_id == "CTR-001"
        assert r.drift_type == DriftType.FIELD_REMOVED
        assert r.drift_severity == DriftSeverity.BREAKING
        assert r.drift_source == DriftSource.PRODUCER_CHANGE
        assert r.drift_score == 90.0
        assert r.service == "user-svc"
        assert r.team == "platform"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_drift(contract_id=f"CTR-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_drift
# ---------------------------------------------------------------------------


class TestGetDrift:
    def test_found(self):
        eng = _engine()
        r = eng.record_drift(
            contract_id="CTR-001",
            drift_score=85.0,
        )
        result = eng.get_drift(r.id)
        assert result is not None
        assert result.drift_score == 85.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_drift("nonexistent") is None


# ---------------------------------------------------------------------------
# list_drifts
# ---------------------------------------------------------------------------


class TestListDrifts:
    def test_list_all(self):
        eng = _engine()
        eng.record_drift(contract_id="CTR-001")
        eng.record_drift(contract_id="CTR-002")
        assert len(eng.list_drifts()) == 2

    def test_filter_by_drift_type(self):
        eng = _engine()
        eng.record_drift(
            contract_id="CTR-001",
            drift_type=DriftType.FIELD_REMOVED,
        )
        eng.record_drift(
            contract_id="CTR-002",
            drift_type=DriftType.TYPE_CHANGED,
        )
        results = eng.list_drifts(drift_type=DriftType.FIELD_REMOVED)
        assert len(results) == 1

    def test_filter_by_severity(self):
        eng = _engine()
        eng.record_drift(
            contract_id="CTR-001",
            drift_severity=DriftSeverity.BREAKING,
        )
        eng.record_drift(
            contract_id="CTR-002",
            drift_severity=DriftSeverity.COSMETIC,
        )
        results = eng.list_drifts(severity=DriftSeverity.BREAKING)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_drift(contract_id="CTR-001", service="user-svc")
        eng.record_drift(contract_id="CTR-002", service="order-svc")
        results = eng.list_drifts(service="user-svc")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_drift(contract_id="CTR-001", team="sre")
        eng.record_drift(contract_id="CTR-002", team="platform")
        results = eng.list_drifts(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_drift(contract_id=f"CTR-{i}")
        assert len(eng.list_drifts(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_detail
# ---------------------------------------------------------------------------


class TestAddDetail:
    def test_basic(self):
        eng = _engine()
        d = eng.add_detail(
            contract_id="CTR-001",
            drift_type=DriftType.SCHEMA_MISMATCH,
            detail_score=0.88,
            threshold=0.7,
            breached=True,
            description="Schema field type mismatch",
        )
        assert d.contract_id == "CTR-001"
        assert d.drift_type == DriftType.SCHEMA_MISMATCH
        assert d.detail_score == 0.88
        assert d.threshold == 0.7
        assert d.breached is True
        assert d.description == "Schema field type mismatch"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_detail(contract_id=f"CTR-{i}")
        assert len(eng._details) == 2


# ---------------------------------------------------------------------------
# analyze_drift_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeDriftPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_drift(
            contract_id="CTR-001",
            drift_type=DriftType.FIELD_REMOVED,
            drift_score=80.0,
        )
        eng.record_drift(
            contract_id="CTR-002",
            drift_type=DriftType.FIELD_REMOVED,
            drift_score=60.0,
        )
        result = eng.analyze_drift_patterns()
        assert "field_removed" in result
        assert result["field_removed"]["count"] == 2

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_drift_patterns() == {}


# ---------------------------------------------------------------------------
# identify_breaking_drifts
# ---------------------------------------------------------------------------


class TestIdentifyBreakingDrifts:
    def test_detects_breaking(self):
        eng = _engine()
        eng.record_drift(
            contract_id="CTR-001",
            drift_severity=DriftSeverity.BREAKING,
        )
        eng.record_drift(
            contract_id="CTR-002",
            drift_severity=DriftSeverity.COSMETIC,
        )
        results = eng.identify_breaking_drifts()
        assert len(results) == 1
        assert results[0]["contract_id"] == "CTR-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_breaking_drifts() == []


# ---------------------------------------------------------------------------
# rank_by_drift_score
# ---------------------------------------------------------------------------


class TestRankByDriftScore:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_drift(
            contract_id="CTR-001",
            service="user-svc",
            drift_score=90.0,
        )
        eng.record_drift(
            contract_id="CTR-002",
            service="user-svc",
            drift_score=80.0,
        )
        eng.record_drift(
            contract_id="CTR-003",
            service="order-svc",
            drift_score=50.0,
        )
        results = eng.rank_by_drift_score()
        assert len(results) == 2
        assert results[0]["service"] == "user-svc"
        assert results[0]["avg_drift_score"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_drift_score() == []


# ---------------------------------------------------------------------------
# detect_drift_trends
# ---------------------------------------------------------------------------


class TestDetectDriftTrends:
    def test_stable(self):
        eng = _engine()
        for score in [50.0, 50.0, 50.0, 50.0]:
            eng.add_detail(
                contract_id="CTR-001",
                detail_score=score,
            )
        result = eng.detect_drift_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for score in [20.0, 20.0, 80.0, 80.0]:
            eng.add_detail(
                contract_id="CTR-001",
                detail_score=score,
            )
        result = eng.detect_drift_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_drift_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_drift(
            contract_id="CTR-001",
            drift_type=DriftType.FIELD_REMOVED,
            drift_severity=DriftSeverity.BREAKING,
            drift_source=DriftSource.PRODUCER_CHANGE,
            drift_score=90.0,
            service="user-svc",
            team="platform",
        )
        report = eng.generate_report()
        assert isinstance(report, APIContractDriftReport)
        assert report.total_records == 1
        assert report.breaking_drifts == 1
        assert report.avg_drift_score == 90.0
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
        eng.record_drift(contract_id="CTR-001")
        eng.add_detail(contract_id="CTR-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._details) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_details"] == 0
        assert stats["drift_type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_drift(
            contract_id="CTR-001",
            drift_type=DriftType.FIELD_REMOVED,
            service="user-svc",
            team="platform",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "field_removed" in stats["drift_type_distribution"]
