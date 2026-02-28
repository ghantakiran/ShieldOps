"""Tests for shieldops.changes.approval_analyzer — ChangeApprovalAnalyzer."""

from __future__ import annotations

from shieldops.changes.approval_analyzer import (
    ApprovalAnalyzerReport,
    ApprovalBottleneck,
    ApprovalBottleneckDetail,
    ApprovalOutcome,
    ApprovalRecord,
    ApprovalSpeed,
    ChangeApprovalAnalyzer,
)


def _engine(**kw) -> ChangeApprovalAnalyzer:
    return ChangeApprovalAnalyzer(**kw)


# -------------------------------------------------------------------
# Enum tests
# -------------------------------------------------------------------


class TestEnums:
    # ApprovalOutcome (5)
    def test_outcome_approved(self):
        assert ApprovalOutcome.APPROVED == "approved"

    def test_outcome_rejected(self):
        assert ApprovalOutcome.REJECTED == "rejected"

    def test_outcome_deferred(self):
        assert ApprovalOutcome.DEFERRED == "deferred"

    def test_outcome_auto_approved(self):
        assert ApprovalOutcome.AUTO_APPROVED == "auto_approved"

    def test_outcome_escalated(self):
        assert ApprovalOutcome.ESCALATED == "escalated"

    # ApprovalBottleneck (5)
    def test_bottleneck_reviewer_unavailable(self):
        assert ApprovalBottleneck.REVIEWER_UNAVAILABLE == "reviewer_unavailable"

    def test_bottleneck_insufficient_context(self):
        assert ApprovalBottleneck.INSUFFICIENT_CONTEXT == "insufficient_context"

    def test_bottleneck_risk_assessment(self):
        assert ApprovalBottleneck.RISK_ASSESSMENT == "risk_assessment"

    def test_bottleneck_compliance_check(self):
        assert ApprovalBottleneck.COMPLIANCE_CHECK == "compliance_check"

    def test_bottleneck_testing_incomplete(self):
        assert ApprovalBottleneck.TESTING_INCOMPLETE == "testing_incomplete"

    # ApprovalSpeed (5)
    def test_speed_instant(self):
        assert ApprovalSpeed.INSTANT == "instant"

    def test_speed_fast(self):
        assert ApprovalSpeed.FAST == "fast"

    def test_speed_normal(self):
        assert ApprovalSpeed.NORMAL == "normal"

    def test_speed_slow(self):
        assert ApprovalSpeed.SLOW == "slow"

    def test_speed_blocked(self):
        assert ApprovalSpeed.BLOCKED == "blocked"


# -------------------------------------------------------------------
# Model defaults
# -------------------------------------------------------------------


class TestModels:
    def test_approval_record_defaults(self):
        r = ApprovalRecord()
        assert r.id
        assert r.change_id == ""
        assert r.outcome == ApprovalOutcome.APPROVED
        assert r.speed == ApprovalSpeed.NORMAL
        assert r.wait_hours == 0.0
        assert r.reviewer_id == ""
        assert r.environment == ""
        assert r.details == ""
        assert r.created_at > 0

    def test_approval_bottleneck_detail_defaults(self):
        r = ApprovalBottleneckDetail()
        assert r.id
        assert r.change_id == ""
        assert r.bottleneck == ApprovalBottleneck.REVIEWER_UNAVAILABLE
        assert r.delay_hours == 0.0
        assert r.resolution == ""
        assert r.resolved is False
        assert r.created_at > 0

    def test_approval_analyzer_report_defaults(self):
        r = ApprovalAnalyzerReport()
        assert r.total_approvals == 0
        assert r.total_bottlenecks == 0
        assert r.avg_wait_hours == 0.0
        assert r.by_outcome == {}
        assert r.by_speed == {}
        assert r.slow_approval_count == 0
        assert r.recommendations == []
        assert r.generated_at > 0


# -------------------------------------------------------------------
# record_approval
# -------------------------------------------------------------------


class TestRecordApproval:
    def test_basic(self):
        eng = _engine()
        r = eng.record_approval(
            "CHG-001",
            outcome=ApprovalOutcome.APPROVED,
            wait_hours=2.0,
        )
        assert r.change_id == "CHG-001"
        assert r.outcome == ApprovalOutcome.APPROVED
        assert r.wait_hours == 2.0

    def test_with_reviewer(self):
        eng = _engine()
        r = eng.record_approval("CHG-002", reviewer_id="user-10", environment="prod")
        assert r.reviewer_id == "user-10"
        assert r.environment == "prod"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_approval(f"CHG-{i:03d}")
        assert len(eng._records) == 3


# -------------------------------------------------------------------
# get_approval
# -------------------------------------------------------------------


class TestGetApproval:
    def test_found(self):
        eng = _engine()
        r = eng.record_approval("CHG-001")
        assert eng.get_approval(r.id) is not None

    def test_not_found(self):
        eng = _engine()
        assert eng.get_approval("nonexistent") is None


# -------------------------------------------------------------------
# list_approvals
# -------------------------------------------------------------------


class TestListApprovals:
    def test_list_all(self):
        eng = _engine()
        eng.record_approval("CHG-001")
        eng.record_approval("CHG-002")
        assert len(eng.list_approvals()) == 2

    def test_filter_by_change(self):
        eng = _engine()
        eng.record_approval("CHG-001")
        eng.record_approval("CHG-002")
        results = eng.list_approvals(change_id="CHG-001")
        assert len(results) == 1

    def test_filter_by_outcome(self):
        eng = _engine()
        eng.record_approval("CHG-001", outcome=ApprovalOutcome.APPROVED)
        eng.record_approval("CHG-002", outcome=ApprovalOutcome.REJECTED)
        results = eng.list_approvals(outcome=ApprovalOutcome.REJECTED)
        assert len(results) == 1


# -------------------------------------------------------------------
# add_bottleneck
# -------------------------------------------------------------------


class TestAddBottleneck:
    def test_basic(self):
        eng = _engine()
        b = eng.add_bottleneck(
            "CHG-001",
            bottleneck=ApprovalBottleneck.COMPLIANCE_CHECK,
            delay_hours=8.0,
            resolution="Compliance team approved",
            resolved=True,
        )
        assert b.change_id == "CHG-001"
        assert b.bottleneck == ApprovalBottleneck.COMPLIANCE_CHECK
        assert b.delay_hours == 8.0
        assert b.resolved is True

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(4):
            eng.add_bottleneck(f"CHG-{i:03d}")
        assert len(eng._bottlenecks) == 2


# -------------------------------------------------------------------
# analyze_approval_velocity
# -------------------------------------------------------------------


class TestAnalyzeApprovalVelocity:
    def test_with_data(self):
        eng = _engine(max_approval_hours=24.0)
        eng.record_approval("CHG-001", environment="prod", wait_hours=10.0)
        eng.record_approval("CHG-002", environment="prod", wait_hours=30.0)
        result = eng.analyze_approval_velocity("prod")
        assert result["environment"] == "prod"
        assert result["total_approvals"] == 2
        assert result["avg_wait_hours"] == 20.0
        assert result["slow_approval_count"] == 1

    def test_no_data(self):
        eng = _engine()
        result = eng.analyze_approval_velocity("staging")
        assert result["status"] == "no_data"


# -------------------------------------------------------------------
# identify_slow_approvals
# -------------------------------------------------------------------


class TestIdentifySlowApprovals:
    def test_with_slow(self):
        eng = _engine(max_approval_hours=24.0)
        eng.record_approval("CHG-001", wait_hours=48.0)
        eng.record_approval("CHG-002", wait_hours=12.0)
        results = eng.identify_slow_approvals()
        assert len(results) == 1
        assert results[0]["change_id"] == "CHG-001"
        assert results[0]["exceeded_by_hours"] == 24.0

    def test_empty(self):
        eng = _engine()
        assert eng.identify_slow_approvals() == []


# -------------------------------------------------------------------
# rank_by_wait_time
# -------------------------------------------------------------------


class TestRankByWaitTime:
    def test_with_data(self):
        eng = _engine()
        eng.record_approval("CHG-001", wait_hours=5.0)
        eng.record_approval("CHG-002", wait_hours=20.0)
        results = eng.rank_by_wait_time()
        assert results[0]["change_id"] == "CHG-002"
        assert results[0]["wait_hours"] == 20.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_wait_time() == []


# -------------------------------------------------------------------
# detect_approval_bottlenecks
# -------------------------------------------------------------------


class TestDetectApprovalBottlenecks:
    def test_with_bottlenecks(self):
        eng = _engine()
        eng.add_bottleneck(
            "CHG-001", bottleneck=ApprovalBottleneck.COMPLIANCE_CHECK, delay_hours=10.0
        )
        eng.add_bottleneck(
            "CHG-002", bottleneck=ApprovalBottleneck.COMPLIANCE_CHECK, delay_hours=5.0
        )
        eng.add_bottleneck(
            "CHG-003", bottleneck=ApprovalBottleneck.RISK_ASSESSMENT, delay_hours=2.0
        )
        results = eng.detect_approval_bottlenecks()
        assert results[0]["bottleneck"] == "compliance_check"
        assert results[0]["total_delay_hours"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.detect_approval_bottlenecks() == []


# -------------------------------------------------------------------
# generate_report
# -------------------------------------------------------------------


class TestGenerateReport:
    def test_with_data(self):
        eng = _engine(max_approval_hours=24.0)
        eng.record_approval("CHG-001", wait_hours=48.0)
        eng.record_approval("CHG-002", wait_hours=6.0)
        eng.add_bottleneck("CHG-001", bottleneck=ApprovalBottleneck.REVIEWER_UNAVAILABLE)
        report = eng.generate_report()
        assert report.total_approvals == 2
        assert report.total_bottlenecks == 1
        assert report.slow_approval_count == 1
        assert report.recommendations != []

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_approvals == 0
        assert "within" in report.recommendations[0]


# -------------------------------------------------------------------
# clear_data
# -------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_approval("CHG-001")
        eng.add_bottleneck("CHG-001")
        eng.clear_data()
        assert len(eng._records) == 0
        assert len(eng._bottlenecks) == 0


# -------------------------------------------------------------------
# get_stats
# -------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_approvals"] == 0
        assert stats["total_bottlenecks"] == 0
        assert stats["outcome_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_approval("CHG-001", outcome=ApprovalOutcome.APPROVED)
        eng.record_approval("CHG-002", outcome=ApprovalOutcome.REJECTED)
        eng.add_bottleneck("CHG-001")
        stats = eng.get_stats()
        assert stats["total_approvals"] == 2
        assert stats["total_bottlenecks"] == 1
        assert stats["unique_changes"] == 2
