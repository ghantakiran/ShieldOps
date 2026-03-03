"""Tests for shieldops.compliance.cross_border_transfer_validator — CrossBorderTransferValidator."""

from __future__ import annotations

from shieldops.compliance.cross_border_transfer_validator import (
    CrossBorderTransferValidator,
    JurisdictionRisk,
    TransferAnalysis,
    TransferMechanism,
    TransferRecord,
    TransferValidationReport,
    ValidationResult,
)


def _engine(**kw) -> CrossBorderTransferValidator:
    return CrossBorderTransferValidator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_mechanism_adequacy(self):
        assert TransferMechanism.ADEQUACY == "adequacy"

    def test_mechanism_scc(self):
        assert TransferMechanism.SCC == "scc"

    def test_mechanism_bcr(self):
        assert TransferMechanism.BCR == "bcr"

    def test_mechanism_consent(self):
        assert TransferMechanism.CONSENT == "consent"

    def test_mechanism_derogation(self):
        assert TransferMechanism.DEROGATION == "derogation"

    def test_risk_low(self):
        assert JurisdictionRisk.LOW == "low"

    def test_risk_medium(self):
        assert JurisdictionRisk.MEDIUM == "medium"

    def test_risk_high(self):
        assert JurisdictionRisk.HIGH == "high"

    def test_risk_critical(self):
        assert JurisdictionRisk.CRITICAL == "critical"

    def test_risk_prohibited(self):
        assert JurisdictionRisk.PROHIBITED == "prohibited"

    def test_result_approved(self):
        assert ValidationResult.APPROVED == "approved"

    def test_result_conditional(self):
        assert ValidationResult.CONDITIONAL == "conditional"

    def test_result_denied(self):
        assert ValidationResult.DENIED == "denied"

    def test_result_pending(self):
        assert ValidationResult.PENDING == "pending"

    def test_result_requires_review(self):
        assert ValidationResult.REQUIRES_REVIEW == "requires_review"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_transfer_record_defaults(self):
        r = TransferRecord()
        assert r.id
        assert r.transfer_id == ""
        assert r.transfer_mechanism == TransferMechanism.ADEQUACY
        assert r.jurisdiction_risk == JurisdictionRisk.LOW
        assert r.validation_result == ValidationResult.APPROVED
        assert r.compliance_score == 0.0
        assert r.destination_country == ""
        assert r.data_owner == ""
        assert r.created_at > 0

    def test_transfer_analysis_defaults(self):
        a = TransferAnalysis()
        assert a.id
        assert a.transfer_id == ""
        assert a.transfer_mechanism == TransferMechanism.ADEQUACY
        assert a.analysis_score == 0.0
        assert a.threshold == 0.0
        assert a.breached is False
        assert a.description == ""
        assert a.created_at > 0

    def test_report_defaults(self):
        r = TransferValidationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_analyses == 0
        assert r.gap_count == 0
        assert r.avg_compliance_score == 0.0
        assert r.by_mechanism == {}
        assert r.by_risk == {}
        assert r.by_result == {}
        assert r.top_gaps == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_transfer / get_transfer
# ---------------------------------------------------------------------------


class TestRecordAndGet:
    def test_basic(self):
        eng = _engine()
        r = eng.record_transfer(
            transfer_id="xfr-001",
            transfer_mechanism=TransferMechanism.SCC,
            jurisdiction_risk=JurisdictionRisk.HIGH,
            validation_result=ValidationResult.CONDITIONAL,
            compliance_score=75.0,
            destination_country="CN",
            data_owner="dpo-team",
        )
        assert r.transfer_id == "xfr-001"
        assert r.transfer_mechanism == TransferMechanism.SCC
        assert r.compliance_score == 75.0
        assert r.destination_country == "CN"

    def test_get_found(self):
        eng = _engine()
        r = eng.record_transfer(transfer_id="xfr-001", transfer_mechanism=TransferMechanism.BCR)
        result = eng.get_transfer(r.id)
        assert result is not None
        assert result.transfer_mechanism == TransferMechanism.BCR

    def test_get_not_found(self):
        eng = _engine()
        assert eng.get_transfer("nonexistent") is None

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_transfer(transfer_id=f"xfr-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# list_transfers
# ---------------------------------------------------------------------------


class TestListAndFilter:
    def test_list_all(self):
        eng = _engine()
        eng.record_transfer(transfer_id="x-001")
        eng.record_transfer(transfer_id="x-002")
        assert len(eng.list_transfers()) == 2

    def test_filter_by_mechanism(self):
        eng = _engine()
        eng.record_transfer(transfer_id="x-001", transfer_mechanism=TransferMechanism.ADEQUACY)
        eng.record_transfer(transfer_id="x-002", transfer_mechanism=TransferMechanism.SCC)
        results = eng.list_transfers(transfer_mechanism=TransferMechanism.ADEQUACY)
        assert len(results) == 1

    def test_filter_by_risk(self):
        eng = _engine()
        eng.record_transfer(transfer_id="x-001", jurisdiction_risk=JurisdictionRisk.LOW)
        eng.record_transfer(transfer_id="x-002", jurisdiction_risk=JurisdictionRisk.CRITICAL)
        results = eng.list_transfers(jurisdiction_risk=JurisdictionRisk.LOW)
        assert len(results) == 1

    def test_filter_by_country(self):
        eng = _engine()
        eng.record_transfer(transfer_id="x-001", destination_country="DE")
        eng.record_transfer(transfer_id="x-002", destination_country="CN")
        results = eng.list_transfers(destination_country="DE")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_transfer(transfer_id=f"x-{i}")
        assert len(eng.list_transfers(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_analysis
# ---------------------------------------------------------------------------


class TestAnalysis:
    def test_basic(self):
        eng = _engine()
        a = eng.add_analysis(
            transfer_id="xfr-001",
            transfer_mechanism=TransferMechanism.CONSENT,
            analysis_score=88.5,
            threshold=80.0,
            breached=True,
            description="prohibited jurisdiction",
        )
        assert a.transfer_id == "xfr-001"
        assert a.transfer_mechanism == TransferMechanism.CONSENT
        assert a.analysis_score == 88.5
        assert a.breached is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_analysis(transfer_id=f"x-{i}")
        assert len(eng._analyses) == 2

    def test_stored_in_analyses(self):
        eng = _engine()
        eng.add_analysis(transfer_id="xfr-999", transfer_mechanism=TransferMechanism.DEROGATION)
        assert len(eng._analyses) == 1


# ---------------------------------------------------------------------------
# analyze_mechanism_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_transfer(
            transfer_id="x-001",
            transfer_mechanism=TransferMechanism.ADEQUACY,
            compliance_score=90.0,
        )
        eng.record_transfer(
            transfer_id="x-002",
            transfer_mechanism=TransferMechanism.ADEQUACY,
            compliance_score=70.0,
        )
        result = eng.analyze_mechanism_distribution()
        assert "adequacy" in result
        assert result["adequacy"]["count"] == 2
        assert result["adequacy"]["avg_compliance_score"] == 80.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_mechanism_distribution() == {}


# ---------------------------------------------------------------------------
# identify_transfer_gaps
# ---------------------------------------------------------------------------


class TestIdentifyGaps:
    def test_detects_below_threshold(self):
        eng = _engine(threshold=80.0)
        eng.record_transfer(transfer_id="x-001", compliance_score=60.0)
        eng.record_transfer(transfer_id="x-002", compliance_score=90.0)
        results = eng.identify_transfer_gaps()
        assert len(results) == 1
        assert results[0]["transfer_id"] == "x-001"

    def test_sorted_ascending(self):
        eng = _engine(threshold=80.0)
        eng.record_transfer(transfer_id="x-001", compliance_score=50.0)
        eng.record_transfer(transfer_id="x-002", compliance_score=30.0)
        results = eng.identify_transfer_gaps()
        assert results[0]["compliance_score"] == 30.0


# ---------------------------------------------------------------------------
# rank_by_compliance
# ---------------------------------------------------------------------------


class TestRankBy:
    def test_sorted_ascending(self):
        eng = _engine()
        eng.record_transfer(transfer_id="x-001", destination_country="DE", compliance_score=90.0)
        eng.record_transfer(transfer_id="x-002", destination_country="CN", compliance_score=50.0)
        results = eng.rank_by_compliance()
        assert results[0]["destination_country"] == "CN"
        assert results[0]["avg_compliance_score"] == 50.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_compliance() == []


# ---------------------------------------------------------------------------
# detect_transfer_trends
# ---------------------------------------------------------------------------


class TestDetectTrends:
    def test_stable(self):
        eng = _engine()
        for _ in range(4):
            eng.add_analysis(transfer_id="x-001", analysis_score=50.0)
        result = eng.detect_transfer_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        eng.add_analysis(transfer_id="x-001", analysis_score=20.0)
        eng.add_analysis(transfer_id="x-002", analysis_score=20.0)
        eng.add_analysis(transfer_id="x-003", analysis_score=80.0)
        eng.add_analysis(transfer_id="x-004", analysis_score=80.0)
        result = eng.detect_transfer_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_transfer_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestReport:
    def test_populated(self):
        eng = _engine(threshold=80.0)
        eng.record_transfer(
            transfer_id="xfr-001",
            transfer_mechanism=TransferMechanism.CONSENT,
            jurisdiction_risk=JurisdictionRisk.CRITICAL,
            validation_result=ValidationResult.DENIED,
            compliance_score=50.0,
        )
        report = eng.generate_report()
        assert isinstance(report, TransferValidationReport)
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


class TestClearAndStats:
    def test_clears(self):
        eng = _engine()
        eng.record_transfer(transfer_id="x-001")
        eng.add_analysis(transfer_id="x-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._analyses) == 0

    def test_stats_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_analyses"] == 0
        assert stats["mechanism_distribution"] == {}


# ---------------------------------------------------------------------------
# Eviction
# ---------------------------------------------------------------------------


class TestEviction:
    def test_analyses_eviction(self):
        eng = _engine(max_records=3)
        for i in range(7):
            eng.add_analysis(transfer_id=f"x-{i}")
        assert len(eng._analyses) == 3
