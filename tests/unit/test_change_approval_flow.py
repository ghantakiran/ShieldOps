"""Tests for shieldops.changes.change_approval_flow — ChangeApprovalFlowTracker."""

from __future__ import annotations

from shieldops.changes.change_approval_flow import (
    ApprovalChannel,
    ApprovalMetric,
    ApprovalPriority,
    ApprovalRecord,
    ApprovalStage,
    ChangeApprovalFlowReport,
    ChangeApprovalFlowTracker,
)


def _engine(**kw) -> ChangeApprovalFlowTracker:
    return ChangeApprovalFlowTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_approval_stage_submitted(self):
        assert ApprovalStage.SUBMITTED == "submitted"

    def test_approval_stage_review(self):
        assert ApprovalStage.REVIEW == "review"

    def test_approval_stage_approved(self):
        assert ApprovalStage.APPROVED == "approved"

    def test_approval_stage_rejected(self):
        assert ApprovalStage.REJECTED == "rejected"

    def test_approval_stage_expired(self):
        assert ApprovalStage.EXPIRED == "expired"

    def test_approval_priority_emergency(self):
        assert ApprovalPriority.EMERGENCY == "emergency"

    def test_approval_priority_high(self):
        assert ApprovalPriority.HIGH == "high"

    def test_approval_priority_standard(self):
        assert ApprovalPriority.STANDARD == "standard"

    def test_approval_priority_low(self):
        assert ApprovalPriority.LOW == "low"

    def test_approval_priority_routine(self):
        assert ApprovalPriority.ROUTINE == "routine"

    def test_approval_channel_automated(self):
        assert ApprovalChannel.AUTOMATED == "automated"

    def test_approval_channel_peer_review(self):
        assert ApprovalChannel.PEER_REVIEW == "peer_review"

    def test_approval_channel_manager(self):
        assert ApprovalChannel.MANAGER == "manager"

    def test_approval_channel_cab(self):
        assert ApprovalChannel.CAB == "cab"

    def test_approval_channel_executive(self):
        assert ApprovalChannel.EXECUTIVE == "executive"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_approval_record_defaults(self):
        r = ApprovalRecord()
        assert r.id
        assert r.change_id == ""
        assert r.approval_stage == ApprovalStage.SUBMITTED
        assert r.approval_priority == ApprovalPriority.STANDARD
        assert r.approval_channel == ApprovalChannel.AUTOMATED
        assert r.approval_time_hours == 0.0
        assert r.service == ""
        assert r.team == ""
        assert r.created_at > 0

    def test_approval_metric_defaults(self):
        m = ApprovalMetric()
        assert m.id
        assert m.change_id == ""
        assert m.approval_stage == ApprovalStage.SUBMITTED
        assert m.metric_score == 0.0
        assert m.threshold == 0.0
        assert m.breached is False
        assert m.description == ""
        assert m.created_at > 0

    def test_change_approval_flow_report_defaults(self):
        r = ChangeApprovalFlowReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_metrics == 0
        assert r.slow_approvals == 0
        assert r.avg_approval_time_hours == 0.0
        assert r.by_stage == {}
        assert r.by_priority == {}
        assert r.by_channel == {}
        assert r.top_slow == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_approval
# ---------------------------------------------------------------------------


class TestRecordApproval:
    def test_basic(self):
        eng = _engine()
        r = eng.record_approval(
            change_id="CHG-001",
            approval_stage=ApprovalStage.REVIEW,
            approval_priority=ApprovalPriority.HIGH,
            approval_channel=ApprovalChannel.CAB,
            approval_time_hours=12.5,
            service="api-gateway",
            team="sre",
        )
        assert r.change_id == "CHG-001"
        assert r.approval_stage == ApprovalStage.REVIEW
        assert r.approval_priority == ApprovalPriority.HIGH
        assert r.approval_channel == ApprovalChannel.CAB
        assert r.approval_time_hours == 12.5
        assert r.service == "api-gateway"
        assert r.team == "sre"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_approval(change_id=f"CHG-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_approval
# ---------------------------------------------------------------------------


class TestGetApproval:
    def test_found(self):
        eng = _engine()
        r = eng.record_approval(
            change_id="CHG-001",
            approval_stage=ApprovalStage.APPROVED,
        )
        result = eng.get_approval(r.id)
        assert result is not None
        assert result.approval_stage == ApprovalStage.APPROVED

    def test_not_found(self):
        eng = _engine()
        assert eng.get_approval("nonexistent") is None


# ---------------------------------------------------------------------------
# list_approvals
# ---------------------------------------------------------------------------


class TestListApprovals:
    def test_list_all(self):
        eng = _engine()
        eng.record_approval(change_id="CHG-001")
        eng.record_approval(change_id="CHG-002")
        assert len(eng.list_approvals()) == 2

    def test_filter_by_stage(self):
        eng = _engine()
        eng.record_approval(change_id="CHG-001", approval_stage=ApprovalStage.SUBMITTED)
        eng.record_approval(change_id="CHG-002", approval_stage=ApprovalStage.APPROVED)
        results = eng.list_approvals(stage=ApprovalStage.SUBMITTED)
        assert len(results) == 1

    def test_filter_by_priority(self):
        eng = _engine()
        eng.record_approval(
            change_id="CHG-001",
            approval_priority=ApprovalPriority.EMERGENCY,
        )
        eng.record_approval(
            change_id="CHG-002",
            approval_priority=ApprovalPriority.ROUTINE,
        )
        results = eng.list_approvals(priority=ApprovalPriority.EMERGENCY)
        assert len(results) == 1

    def test_filter_by_service(self):
        eng = _engine()
        eng.record_approval(change_id="CHG-001", service="api-gateway")
        eng.record_approval(change_id="CHG-002", service="auth-svc")
        results = eng.list_approvals(service="api-gateway")
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_approval(change_id="CHG-001", team="sre")
        eng.record_approval(change_id="CHG-002", team="platform")
        results = eng.list_approvals(team="sre")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_approval(change_id=f"CHG-{i}")
        assert len(eng.list_approvals(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_metric
# ---------------------------------------------------------------------------


class TestAddMetric:
    def test_basic(self):
        eng = _engine()
        m = eng.add_metric(
            change_id="CHG-001",
            approval_stage=ApprovalStage.REVIEW,
            metric_score=85.0,
            threshold=90.0,
            breached=True,
            description="Approval bottleneck detected",
        )
        assert m.change_id == "CHG-001"
        assert m.approval_stage == ApprovalStage.REVIEW
        assert m.metric_score == 85.0
        assert m.threshold == 90.0
        assert m.breached is True
        assert m.description == "Approval bottleneck detected"

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_metric(change_id=f"CHG-{i}")
        assert len(eng._metrics) == 2


# ---------------------------------------------------------------------------
# analyze_approval_distribution
# ---------------------------------------------------------------------------


class TestAnalyzeApprovalDistribution:
    def test_with_data(self):
        eng = _engine()
        eng.record_approval(
            change_id="CHG-001",
            approval_stage=ApprovalStage.REVIEW,
            approval_time_hours=10.0,
        )
        eng.record_approval(
            change_id="CHG-002",
            approval_stage=ApprovalStage.REVIEW,
            approval_time_hours=20.0,
        )
        result = eng.analyze_approval_distribution()
        assert "review" in result
        assert result["review"]["count"] == 2
        assert result["review"]["avg_approval_time_hours"] == 15.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_approval_distribution() == {}


# ---------------------------------------------------------------------------
# identify_slow_approvals
# ---------------------------------------------------------------------------


class TestIdentifySlowApprovals:
    def test_detects(self):
        eng = _engine(max_approval_time_hours=24.0)
        eng.record_approval(
            change_id="CHG-001",
            approval_time_hours=48.0,
        )
        eng.record_approval(
            change_id="CHG-002",
            approval_time_hours=12.0,
        )
        results = eng.identify_slow_approvals()
        assert len(results) == 1
        assert results[0]["change_id"] == "CHG-001"

    def test_empty(self):
        eng = _engine()
        assert eng.identify_slow_approvals() == []


# ---------------------------------------------------------------------------
# rank_by_approval_time
# ---------------------------------------------------------------------------


class TestRankByApprovalTime:
    def test_ranked(self):
        eng = _engine()
        eng.record_approval(
            change_id="CHG-001",
            service="api-gateway",
            approval_time_hours=120.0,
        )
        eng.record_approval(
            change_id="CHG-002",
            service="auth-svc",
            approval_time_hours=30.0,
        )
        eng.record_approval(
            change_id="CHG-003",
            service="api-gateway",
            approval_time_hours=80.0,
        )
        results = eng.rank_by_approval_time()
        assert len(results) == 2
        # descending: api-gateway (100.0) first, auth-svc (30.0) second
        assert results[0]["service"] == "api-gateway"
        assert results[0]["avg_approval_time_hours"] == 100.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_approval_time() == []


# ---------------------------------------------------------------------------
# detect_approval_trends
# ---------------------------------------------------------------------------


class TestDetectApprovalTrends:
    def test_stable(self):
        eng = _engine()
        for val in [60.0, 60.0, 60.0, 60.0]:
            eng.add_metric(change_id="CHG-1", metric_score=val)
        result = eng.detect_approval_trends()
        assert result["trend"] == "stable"

    def test_growing(self):
        eng = _engine()
        for val in [5.0, 5.0, 20.0, 20.0]:
            eng.add_metric(change_id="CHG-1", metric_score=val)
        result = eng.detect_approval_trends()
        assert result["trend"] == "growing"
        assert result["delta"] > 0

    def test_shrinking(self):
        eng = _engine()
        for val in [20.0, 20.0, 5.0, 5.0]:
            eng.add_metric(change_id="CHG-1", metric_score=val)
        result = eng.detect_approval_trends()
        assert result["trend"] == "shrinking"
        assert result["delta"] < 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_approval_trends()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine(max_approval_time_hours=24.0)
        eng.record_approval(
            change_id="CHG-001",
            approval_stage=ApprovalStage.REVIEW,
            approval_priority=ApprovalPriority.HIGH,
            approval_channel=ApprovalChannel.CAB,
            approval_time_hours=48.0,
            service="api-gateway",
            team="sre",
        )
        report = eng.generate_report()
        assert isinstance(report, ChangeApprovalFlowReport)
        assert report.total_records == 1
        assert report.slow_approvals == 1
        assert len(report.top_slow) >= 1
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
        eng.record_approval(change_id="CHG-001")
        eng.add_metric(change_id="CHG-001")
        result = eng.clear_data()
        assert result == {"status": "cleared"}
        assert len(eng._records) == 0
        assert len(eng._metrics) == 0


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_records"] == 0
        assert stats["total_metrics"] == 0
        assert stats["approval_stage_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_approval(
            change_id="CHG-001",
            approval_stage=ApprovalStage.REVIEW,
            service="api-gateway",
            team="sre",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_services"] == 1
        assert "review" in stats["approval_stage_distribution"]
