"""Tests for shieldops.audit.change_audit — ChangeAuditAnalyzer."""

from __future__ import annotations

from shieldops.audit.change_audit import (
    AuditFinding,
    AuditObservation,
    AuditStatus,
    ChangeAuditAnalyzer,
    ChangeAuditRecord,
    ChangeAuditReport,
    ChangeType,
)


def _engine(**kw) -> ChangeAuditAnalyzer:
    return ChangeAuditAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_change_type_infrastructure(self):
        assert ChangeType.INFRASTRUCTURE == "infrastructure"

    def test_change_type_application(self):
        assert ChangeType.APPLICATION == "application"

    def test_change_type_configuration(self):
        assert ChangeType.CONFIGURATION == "configuration"

    def test_change_type_database(self):
        assert ChangeType.DATABASE == "database"

    def test_change_type_network(self):
        assert ChangeType.NETWORK == "network"

    def test_audit_status_compliant(self):
        assert AuditStatus.COMPLIANT == "compliant"

    def test_audit_status_non_compliant(self):
        assert AuditStatus.NON_COMPLIANT == "non_compliant"

    def test_audit_status_pending_review(self):
        assert AuditStatus.PENDING_REVIEW == "pending_review"

    def test_audit_status_exempted(self):
        assert AuditStatus.EXEMPTED == "exempted"

    def test_audit_status_remediated(self):
        assert AuditStatus.REMEDIATED == "remediated"

    def test_audit_finding_unauthorized_change(self):
        assert AuditFinding.UNAUTHORIZED_CHANGE == "unauthorized_change"

    def test_audit_finding_missing_approval(self):
        assert AuditFinding.MISSING_APPROVAL == "missing_approval"

    def test_audit_finding_incomplete_testing(self):
        assert AuditFinding.INCOMPLETE_TESTING == "incomplete_testing"

    def test_audit_finding_no_rollback_plan(self):
        assert AuditFinding.NO_ROLLBACK_PLAN == "no_rollback_plan"

    def test_audit_finding_documentation_gap(self):
        assert AuditFinding.DOCUMENTATION_GAP == "documentation_gap"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_change_audit_record_defaults(self):
        r = ChangeAuditRecord()
        assert r.id
        assert r.change_id == ""
        assert r.change_type == ChangeType.INFRASTRUCTURE
        assert r.audit_status == AuditStatus.PENDING_REVIEW
        assert r.audit_finding == AuditFinding.UNAUTHORIZED_CHANGE
        assert r.compliance_pct == 0.0
        assert r.auditor == ""
        assert r.created_at > 0

    def test_audit_observation_defaults(self):
        o = AuditObservation()
        assert o.id
        assert o.observation_name == ""
        assert o.change_type == ChangeType.INFRASTRUCTURE
        assert o.severity_score == 0.0
        assert o.changes_reviewed == 0
        assert o.description == ""
        assert o.created_at > 0

    def test_change_audit_report_defaults(self):
        r = ChangeAuditReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_observations == 0
        assert r.audited_changes == 0
        assert r.avg_compliance_pct == 0.0
        assert r.by_type == {}
        assert r.by_status == {}
        assert r.by_finding == {}
        assert r.non_compliant_changes == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_audit
# ---------------------------------------------------------------------------


class TestRecordAudit:
    def test_basic(self):
        eng = _engine()
        r = eng.record_audit(
            change_id="chg-001",
            change_type=ChangeType.APPLICATION,
            audit_status=AuditStatus.COMPLIANT,
            audit_finding=AuditFinding.MISSING_APPROVAL,
            compliance_pct=95.0,
            auditor="alice",
        )
        assert r.change_id == "chg-001"
        assert r.change_type == ChangeType.APPLICATION
        assert r.audit_status == AuditStatus.COMPLIANT
        assert r.audit_finding == AuditFinding.MISSING_APPROVAL
        assert r.compliance_pct == 95.0
        assert r.auditor == "alice"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_audit(change_id=f"chg-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_audit
# ---------------------------------------------------------------------------


class TestGetAudit:
    def test_found(self):
        eng = _engine()
        r = eng.record_audit(
            change_id="chg-001",
            change_type=ChangeType.DATABASE,
        )
        result = eng.get_audit(r.id)
        assert result is not None
        assert result.change_type == ChangeType.DATABASE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_audit("nonexistent") is None


# ---------------------------------------------------------------------------
# list_audits
# ---------------------------------------------------------------------------


class TestListAudits:
    def test_list_all(self):
        eng = _engine()
        eng.record_audit(change_id="chg-001")
        eng.record_audit(change_id="chg-002")
        assert len(eng.list_audits()) == 2

    def test_filter_by_change_type(self):
        eng = _engine()
        eng.record_audit(
            change_id="chg-001",
            change_type=ChangeType.INFRASTRUCTURE,
        )
        eng.record_audit(
            change_id="chg-002",
            change_type=ChangeType.NETWORK,
        )
        results = eng.list_audits(change_type=ChangeType.INFRASTRUCTURE)
        assert len(results) == 1

    def test_filter_by_audit_status(self):
        eng = _engine()
        eng.record_audit(
            change_id="chg-001",
            audit_status=AuditStatus.COMPLIANT,
        )
        eng.record_audit(
            change_id="chg-002",
            audit_status=AuditStatus.NON_COMPLIANT,
        )
        results = eng.list_audits(audit_status=AuditStatus.COMPLIANT)
        assert len(results) == 1

    def test_filter_by_auditor(self):
        eng = _engine()
        eng.record_audit(change_id="chg-001", auditor="alice")
        eng.record_audit(change_id="chg-002", auditor="bob")
        results = eng.list_audits(auditor="alice")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_audit(change_id=f"chg-{i}")
        assert len(eng.list_audits(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_observation
# ---------------------------------------------------------------------------


class TestAddObservation:
    def test_basic(self):
        eng = _engine()
        o = eng.add_observation(
            observation_name="q1-audit-review",
            change_type=ChangeType.CONFIGURATION,
            severity_score=7.5,
            changes_reviewed=20,
            description="Quarterly audit observation",
        )
        assert o.observation_name == "q1-audit-review"
        assert o.change_type == ChangeType.CONFIGURATION
        assert o.severity_score == 7.5
        assert o.changes_reviewed == 20

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_observation(observation_name=f"observation-{i}")
        assert len(eng._observations) == 2


# ---------------------------------------------------------------------------
# analyze_audit_compliance
# ---------------------------------------------------------------------------


class TestAnalyzeAuditCompliance:
    def test_with_data(self):
        eng = _engine()
        eng.record_audit(
            change_id="chg-001",
            change_type=ChangeType.INFRASTRUCTURE,
            compliance_pct=90.0,
        )
        eng.record_audit(
            change_id="chg-002",
            change_type=ChangeType.INFRASTRUCTURE,
            compliance_pct=80.0,
        )
        result = eng.analyze_audit_compliance()
        assert "infrastructure" in result
        assert result["infrastructure"]["count"] == 2
        assert result["infrastructure"]["avg_compliance_pct"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_audit_compliance() == {}


# ---------------------------------------------------------------------------
# identify_non_compliant_changes
# ---------------------------------------------------------------------------


class TestIdentifyNonCompliantChanges:
    def test_detects_non_compliant(self):
        eng = _engine(min_audit_compliance_pct=90.0)
        eng.record_audit(
            change_id="chg-001",
            compliance_pct=60.0,
        )
        eng.record_audit(
            change_id="chg-002",
            compliance_pct=95.0,
        )
        results = eng.identify_non_compliant_changes()
        assert len(results) == 1
        assert results[0]["change_id"] == "chg-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_non_compliant_changes() == []


# ---------------------------------------------------------------------------
# rank_by_severity
# ---------------------------------------------------------------------------


class TestRankBySeverity:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_audit(change_id="c1", auditor="alice", compliance_pct=90.0)
        eng.record_audit(change_id="c2", auditor="alice", compliance_pct=80.0)
        eng.record_audit(change_id="c3", auditor="bob", compliance_pct=50.0)
        results = eng.rank_by_severity()
        assert len(results) == 2
        assert results[0]["auditor"] == "alice"
        assert results[0]["total_compliance"] == 170.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_severity() == []


# ---------------------------------------------------------------------------
# detect_audit_trends
# ---------------------------------------------------------------------------


class TestDetectAuditTrends:
    def test_stable(self):
        eng = _engine()
        for pct in [80.0, 80.0, 80.0, 80.0]:
            eng.record_audit(change_id="chg-001", compliance_pct=pct)
        result = eng.detect_audit_trends()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for pct in [50.0, 50.0, 90.0, 90.0]:
            eng.record_audit(change_id="chg-001", compliance_pct=pct)
        result = eng.detect_audit_trends()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_audit_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(min_audit_compliance_pct=90.0)
        eng.record_audit(
            change_id="chg-001",
            change_type=ChangeType.INFRASTRUCTURE,
            audit_status=AuditStatus.NON_COMPLIANT,
            compliance_pct=60.0,
            auditor="alice",
        )
        report = eng.generate_report()
        assert isinstance(report, ChangeAuditReport)
        assert report.total_records == 1
        assert report.avg_compliance_pct == 60.0
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
        eng.record_audit(change_id="chg-001")
        eng.add_observation(observation_name="o1")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._observations) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_observations"] == 0
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_audit(
            change_id="chg-001",
            change_type=ChangeType.APPLICATION,
            auditor="alice",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_changes"] == 1
        assert stats["unique_auditors"] == 1
        assert "application" in stats["type_distribution"]
