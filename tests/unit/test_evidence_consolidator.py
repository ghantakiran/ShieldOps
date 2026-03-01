"""Tests for shieldops.compliance.evidence_consolidator — ComplianceEvidenceConsolidator."""

from __future__ import annotations

from shieldops.compliance.evidence_consolidator import (
    ComplianceEvidenceConsolidator,
    ConsolidationLevel,
    ConsolidationRecord,
    ConsolidationRule,
    EvidenceConsolidationReport,
    EvidenceSource,
    EvidenceStatus,
)


def _engine(**kw) -> ComplianceEvidenceConsolidator:
    return ComplianceEvidenceConsolidator(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_status_collected(self):
        assert EvidenceStatus.COLLECTED == "collected"

    def test_status_verified(self):
        assert EvidenceStatus.VERIFIED == "verified"

    def test_status_consolidated(self):
        assert EvidenceStatus.CONSOLIDATED == "consolidated"

    def test_status_expired(self):
        assert EvidenceStatus.EXPIRED == "expired"

    def test_status_missing(self):
        assert EvidenceStatus.MISSING == "missing"

    def test_source_automated(self):
        assert EvidenceSource.AUTOMATED == "automated"

    def test_source_manual(self):
        assert EvidenceSource.MANUAL == "manual"

    def test_source_third_party(self):
        assert EvidenceSource.THIRD_PARTY == "third_party"

    def test_source_internal_audit(self):
        assert EvidenceSource.INTERNAL_AUDIT == "internal_audit"

    def test_source_continuous_monitoring(self):
        assert EvidenceSource.CONTINUOUS_MONITORING == "continuous_monitoring"

    def test_level_complete(self):
        assert ConsolidationLevel.COMPLETE == "complete"

    def test_level_partial(self):
        assert ConsolidationLevel.PARTIAL == "partial"

    def test_level_minimal(self):
        assert ConsolidationLevel.MINIMAL == "minimal"

    def test_level_insufficient(self):
        assert ConsolidationLevel.INSUFFICIENT == "insufficient"

    def test_level_none(self):
        assert ConsolidationLevel.NONE == "none"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_consolidation_record_defaults(self):
        r = ConsolidationRecord()
        assert r.id
        assert r.framework == ""
        assert r.evidence_status == EvidenceStatus.COLLECTED
        assert r.source == EvidenceSource.AUTOMATED
        assert r.consolidation_level == ConsolidationLevel.PARTIAL
        assert r.completeness_pct == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_consolidation_rule_defaults(self):
        ru = ConsolidationRule()
        assert ru.id
        assert ru.framework_pattern == ""
        assert ru.evidence_status == EvidenceStatus.COLLECTED
        assert ru.source == EvidenceSource.AUTOMATED
        assert ru.min_completeness_pct == 0.0
        assert ru.reason == ""
        assert ru.created_at > 0

    def test_consolidation_report_defaults(self):
        r = EvidenceConsolidationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_rules == 0
        assert r.missing_count == 0
        assert r.avg_completeness_pct == 0.0
        assert r.by_status == {}
        assert r.by_source == {}
        assert r.by_level == {}
        assert r.incomplete_frameworks == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_consolidation
# ---------------------------------------------------------------------------


class TestRecordConsolidation:
    def test_basic(self):
        eng = _engine()
        r = eng.record_consolidation(
            framework="SOC2",
            evidence_status=EvidenceStatus.VERIFIED,
            source=EvidenceSource.AUTOMATED,
            completeness_pct=85.0,
            team="compliance",
        )
        assert r.framework == "SOC2"
        assert r.evidence_status == EvidenceStatus.VERIFIED
        assert r.source == EvidenceSource.AUTOMATED
        assert r.completeness_pct == 85.0
        assert r.team == "compliance"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_consolidation(framework=f"FW-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_consolidation
# ---------------------------------------------------------------------------


class TestGetConsolidation:
    def test_found(self):
        eng = _engine()
        r = eng.record_consolidation(framework="SOC2", completeness_pct=90.0)
        result = eng.get_consolidation(r.id)
        assert result is not None
        assert result.completeness_pct == 90.0

    def test_not_found(self):
        eng = _engine()
        assert eng.get_consolidation("nonexistent") is None


# ---------------------------------------------------------------------------
# list_consolidations
# ---------------------------------------------------------------------------


class TestListConsolidations:
    def test_list_all(self):
        eng = _engine()
        eng.record_consolidation(framework="SOC2")
        eng.record_consolidation(framework="PCI")
        assert len(eng.list_consolidations()) == 2

    def test_filter_by_status(self):
        eng = _engine()
        eng.record_consolidation(
            framework="SOC2",
            evidence_status=EvidenceStatus.MISSING,
        )
        eng.record_consolidation(
            framework="PCI",
            evidence_status=EvidenceStatus.VERIFIED,
        )
        results = eng.list_consolidations(status=EvidenceStatus.MISSING)
        assert len(results) == 1

    def test_filter_by_source(self):
        eng = _engine()
        eng.record_consolidation(
            framework="SOC2",
            source=EvidenceSource.AUTOMATED,
        )
        eng.record_consolidation(
            framework="PCI",
            source=EvidenceSource.MANUAL,
        )
        results = eng.list_consolidations(source=EvidenceSource.AUTOMATED)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_consolidation(framework="SOC2", team="compliance")
        eng.record_consolidation(framework="PCI", team="security")
        results = eng.list_consolidations(team="compliance")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_consolidation(framework=f"FW-{i}")
        assert len(eng.list_consolidations(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_rule
# ---------------------------------------------------------------------------


class TestAddRule:
    def test_basic(self):
        eng = _engine()
        ru = eng.add_rule(
            framework_pattern="SOC*",
            evidence_status=EvidenceStatus.VERIFIED,
            min_completeness_pct=90.0,
            reason="SOC2 requires full evidence",
        )
        assert ru.framework_pattern == "SOC*"
        assert ru.evidence_status == EvidenceStatus.VERIFIED
        assert ru.min_completeness_pct == 90.0
        assert ru.reason == "SOC2 requires full evidence"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_rule(framework_pattern=f"FW-{i}")
        assert len(eng._rules) == 2


# ---------------------------------------------------------------------------
# analyze_consolidation_coverage
# ---------------------------------------------------------------------------


class TestAnalyzeConsolidationCoverage:
    def test_with_data(self):
        eng = _engine()
        eng.record_consolidation(
            framework="SOC2",
            evidence_status=EvidenceStatus.COLLECTED,
            completeness_pct=80.0,
        )
        eng.record_consolidation(
            framework="PCI",
            evidence_status=EvidenceStatus.COLLECTED,
            completeness_pct=60.0,
        )
        result = eng.analyze_consolidation_coverage()
        assert "collected" in result
        assert result["collected"]["count"] == 2
        assert result["collected"]["avg_completeness"] == 70.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_consolidation_coverage() == {}


# ---------------------------------------------------------------------------
# identify_missing_evidence
# ---------------------------------------------------------------------------


class TestIdentifyMissingEvidence:
    def test_detects_missing(self):
        eng = _engine()
        eng.record_consolidation(
            framework="SOC2",
            evidence_status=EvidenceStatus.MISSING,
        )
        eng.record_consolidation(
            framework="PCI",
            evidence_status=EvidenceStatus.VERIFIED,
        )
        results = eng.identify_missing_evidence()
        assert len(results) == 1
        assert results[0]["evidence_status"] == "missing"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_missing_evidence() == []


# ---------------------------------------------------------------------------
# rank_by_completeness
# ---------------------------------------------------------------------------


class TestRankByCompleteness:
    def test_ranked_ascending(self):
        eng = _engine()
        eng.record_consolidation(framework="SOC2", completeness_pct=90.0)
        eng.record_consolidation(framework="PCI", completeness_pct=60.0)
        results = eng.rank_by_completeness()
        assert len(results) == 2
        assert results[0]["framework"] == "PCI"
        assert results[0]["avg_completeness"] == 60.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_completeness() == []


# ---------------------------------------------------------------------------
# detect_consolidation_trends
# ---------------------------------------------------------------------------


class TestDetectConsolidationTrends:
    def test_stable(self):
        eng = _engine()
        for pct in [80.0, 80.0, 80.0, 80.0]:
            eng.record_consolidation(framework="SOC2", completeness_pct=pct)
        result = eng.detect_consolidation_trends()
        assert result["trend"] == "stable"

    def test_improving(self):
        eng = _engine()
        for pct in [50.0, 50.0, 90.0, 90.0]:
            eng.record_consolidation(framework="SOC2", completeness_pct=pct)
        result = eng.detect_consolidation_trends()
        assert result["trend"] == "improving"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_consolidation_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_consolidation(
            framework="SOC2",
            evidence_status=EvidenceStatus.MISSING,
            completeness_pct=30.0,
        )
        report = eng.generate_report()
        assert isinstance(report, EvidenceConsolidationReport)
        assert report.total_records == 1
        assert report.missing_count == 1
        assert len(report.incomplete_frameworks) == 1
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
        eng.record_consolidation(framework="SOC2")
        eng.add_rule(framework_pattern="SOC*")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._rules) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_rules"] == 0
        assert stats["status_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_consolidation(
            framework="SOC2",
            evidence_status=EvidenceStatus.COLLECTED,
            team="compliance",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_frameworks"] == 1
        assert "collected" in stats["status_distribution"]
