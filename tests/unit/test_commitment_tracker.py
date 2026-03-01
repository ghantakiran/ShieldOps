"""Tests for shieldops.billing.commitment_tracker — CommitmentUtilizationTracker."""

from __future__ import annotations

from shieldops.billing.commitment_tracker import (
    CommitmentRecord,
    CommitmentRisk,
    CommitmentType,
    CommitmentUtilizationReport,
    CommitmentUtilizationTracker,
    UtilizationDetail,
    UtilizationLevel,
)


def _engine(**kw) -> CommitmentUtilizationTracker:
    return CommitmentUtilizationTracker(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_type_reserved_instance(self):
        assert CommitmentType.RESERVED_INSTANCE == "reserved_instance"

    def test_type_savings_plan(self):
        assert CommitmentType.SAVINGS_PLAN == "savings_plan"

    def test_type_committed_use(self):
        assert CommitmentType.COMMITTED_USE == "committed_use"

    def test_type_enterprise_agreement(self):
        assert CommitmentType.ENTERPRISE_AGREEMENT == "enterprise_agreement"

    def test_type_spot_fleet(self):
        assert CommitmentType.SPOT_FLEET == "spot_fleet"

    def test_level_optimal(self):
        assert UtilizationLevel.OPTIMAL == "optimal"

    def test_level_good(self):
        assert UtilizationLevel.GOOD == "good"

    def test_level_underutilized(self):
        assert UtilizationLevel.UNDERUTILIZED == "underutilized"

    def test_level_wasted(self):
        assert UtilizationLevel.WASTED == "wasted"

    def test_level_expired(self):
        assert UtilizationLevel.EXPIRED == "expired"

    def test_risk_overcommitted(self):
        assert CommitmentRisk.OVERCOMMITTED == "overcommitted"

    def test_risk_well_balanced(self):
        assert CommitmentRisk.WELL_BALANCED == "well_balanced"

    def test_risk_undercommitted(self):
        assert CommitmentRisk.UNDERCOMMITTED == "undercommitted"

    def test_risk_expiring_soon(self):
        assert CommitmentRisk.EXPIRING_SOON == "expiring_soon"

    def test_risk_mismatched(self):
        assert CommitmentRisk.MISMATCHED == "mismatched"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_commitment_record_defaults(self):
        r = CommitmentRecord()
        assert r.id
        assert r.commitment_id == ""
        assert r.commitment_type == CommitmentType.RESERVED_INSTANCE
        assert r.utilization_level == UtilizationLevel.GOOD
        assert r.commitment_risk == CommitmentRisk.WELL_BALANCED
        assert r.utilization_pct == 0.0
        assert r.team == ""
        assert r.created_at > 0

    def test_utilization_detail_defaults(self):
        d = UtilizationDetail()
        assert d.id
        assert d.detail_name == ""
        assert d.commitment_type == CommitmentType.RESERVED_INSTANCE
        assert d.utilization_threshold == 0.0
        assert d.avg_utilization_pct == 0.0
        assert d.description == ""
        assert d.created_at > 0

    def test_commitment_utilization_report_defaults(self):
        r = CommitmentUtilizationReport()
        assert r.id
        assert r.total_records == 0
        assert r.total_details == 0
        assert r.underutilized_commitments == 0
        assert r.avg_utilization_pct == 0.0
        assert r.by_type == {}
        assert r.by_level == {}
        assert r.by_risk == {}
        assert r.top_items == []
        assert r.recommendations == []
        assert r.generated_at > 0
        assert r.created_at > 0


# ---------------------------------------------------------------------------
# record_commitment
# ---------------------------------------------------------------------------


class TestRecordCommitment:
    def test_basic(self):
        eng = _engine()
        r = eng.record_commitment(
            commitment_id="ri-001",
            commitment_type=CommitmentType.SAVINGS_PLAN,
            utilization_level=UtilizationLevel.OPTIMAL,
            commitment_risk=CommitmentRisk.WELL_BALANCED,
            utilization_pct=92.0,
            team="finops",
        )
        assert r.commitment_id == "ri-001"
        assert r.commitment_type == CommitmentType.SAVINGS_PLAN
        assert r.utilization_level == UtilizationLevel.OPTIMAL
        assert r.commitment_risk == CommitmentRisk.WELL_BALANCED
        assert r.utilization_pct == 92.0
        assert r.team == "finops"

    def test_eviction_at_max(self):
        eng = _engine(max_records=3)
        for i in range(5):
            eng.record_commitment(commitment_id=f"ri-{i}")
        assert len(eng._records) == 3


# ---------------------------------------------------------------------------
# get_commitment
# ---------------------------------------------------------------------------


class TestGetCommitment:
    def test_found(self):
        eng = _engine()
        r = eng.record_commitment(
            commitment_id="ri-001",
            commitment_type=CommitmentType.COMMITTED_USE,
        )
        result = eng.get_commitment(r.id)
        assert result is not None
        assert result.commitment_type == CommitmentType.COMMITTED_USE

    def test_not_found(self):
        eng = _engine()
        assert eng.get_commitment("nonexistent") is None


# ---------------------------------------------------------------------------
# list_commitments
# ---------------------------------------------------------------------------


class TestListCommitments:
    def test_list_all(self):
        eng = _engine()
        eng.record_commitment(commitment_id="ri-001")
        eng.record_commitment(commitment_id="ri-002")
        assert len(eng.list_commitments()) == 2

    def test_filter_by_type(self):
        eng = _engine()
        eng.record_commitment(
            commitment_id="ri-001",
            commitment_type=CommitmentType.RESERVED_INSTANCE,
        )
        eng.record_commitment(
            commitment_id="ri-002",
            commitment_type=CommitmentType.SAVINGS_PLAN,
        )
        results = eng.list_commitments(ctype=CommitmentType.RESERVED_INSTANCE)
        assert len(results) == 1

    def test_filter_by_level(self):
        eng = _engine()
        eng.record_commitment(
            commitment_id="ri-001",
            utilization_level=UtilizationLevel.OPTIMAL,
        )
        eng.record_commitment(
            commitment_id="ri-002",
            utilization_level=UtilizationLevel.WASTED,
        )
        results = eng.list_commitments(level=UtilizationLevel.OPTIMAL)
        assert len(results) == 1

    def test_filter_by_team(self):
        eng = _engine()
        eng.record_commitment(commitment_id="ri-001", team="finops")
        eng.record_commitment(commitment_id="ri-002", team="platform")
        results = eng.list_commitments(team="finops")
        assert len(results) == 1

    def test_limit(self):
        eng = _engine()
        for i in range(10):
            eng.record_commitment(commitment_id=f"ri-{i}")
        assert len(eng.list_commitments(limit=5)) == 5


# ---------------------------------------------------------------------------
# add_utilization
# ---------------------------------------------------------------------------


class TestAddUtilization:
    def test_basic(self):
        eng = _engine()
        d = eng.add_utilization(
            detail_name="ec2-ri-check",
            commitment_type=CommitmentType.RESERVED_INSTANCE,
            utilization_threshold=0.8,
            avg_utilization_pct=75.0,
            description="EC2 RI utilization check",
        )
        assert d.detail_name == "ec2-ri-check"
        assert d.commitment_type == CommitmentType.RESERVED_INSTANCE
        assert d.utilization_threshold == 0.8
        assert d.avg_utilization_pct == 75.0

    def test_eviction_at_max(self):
        eng = _engine(max_records=2)
        for i in range(5):
            eng.add_utilization(detail_name=f"detail-{i}")
        assert len(eng._details) == 2


# ---------------------------------------------------------------------------
# analyze_utilization_patterns
# ---------------------------------------------------------------------------


class TestAnalyzeUtilizationPatterns:
    def test_with_data(self):
        eng = _engine()
        eng.record_commitment(
            commitment_id="ri-001",
            commitment_type=CommitmentType.RESERVED_INSTANCE,
            utilization_pct=90.0,
        )
        eng.record_commitment(
            commitment_id="ri-002",
            commitment_type=CommitmentType.RESERVED_INSTANCE,
            utilization_pct=80.0,
        )
        result = eng.analyze_utilization_patterns()
        assert "reserved_instance" in result
        assert result["reserved_instance"]["count"] == 2
        assert result["reserved_instance"]["avg_utilization_pct"] == 85.0

    def test_empty(self):
        eng = _engine()
        assert eng.analyze_utilization_patterns() == {}


# ---------------------------------------------------------------------------
# identify_underutilized_commitments
# ---------------------------------------------------------------------------


class TestIdentifyUnderutilizedCommitments:
    def test_detects_wasted(self):
        eng = _engine()
        eng.record_commitment(
            commitment_id="ri-001",
            utilization_level=UtilizationLevel.WASTED,
            utilization_pct=15.0,
        )
        eng.record_commitment(
            commitment_id="ri-002",
            utilization_level=UtilizationLevel.OPTIMAL,
        )
        results = eng.identify_underutilized_commitments()
        assert len(results) == 1
        assert results[0]["commitment_id"] == "ri-001"

    def test_detects_underutilized(self):
        eng = _engine()
        eng.record_commitment(
            commitment_id="ri-001",
            utilization_level=UtilizationLevel.UNDERUTILIZED,
        )
        results = eng.identify_underutilized_commitments()
        assert len(results) == 1

    def test_empty(self):
        eng = _engine()
        assert eng.identify_underutilized_commitments() == []


# ---------------------------------------------------------------------------
# rank_by_utilization_pct
# ---------------------------------------------------------------------------


class TestRankByUtilizationPct:
    def test_ranked_descending(self):
        eng = _engine()
        eng.record_commitment(commitment_id="ri-001", team="finops", utilization_pct=95.0)
        eng.record_commitment(commitment_id="ri-002", team="finops", utilization_pct=85.0)
        eng.record_commitment(commitment_id="ri-003", team="platform", utilization_pct=70.0)
        results = eng.rank_by_utilization_pct()
        assert len(results) == 2
        assert results[0]["team"] == "finops"
        assert results[0]["avg_utilization_pct"] == 90.0

    def test_empty(self):
        eng = _engine()
        assert eng.rank_by_utilization_pct() == []


# ---------------------------------------------------------------------------
# detect_commitment_risks
# ---------------------------------------------------------------------------


class TestDetectCommitmentRisks:
    def test_stable(self):
        eng = _engine()
        for s in [80.0, 80.0, 80.0, 80.0]:
            eng.add_utilization(detail_name="d", avg_utilization_pct=s)
        result = eng.detect_commitment_risks()
        assert result["trend"] == "stable"

    def test_increasing(self):
        eng = _engine()
        for s in [50.0, 50.0, 90.0, 90.0]:
            eng.add_utilization(detail_name="d", avg_utilization_pct=s)
        result = eng.detect_commitment_risks()
        assert result["trend"] == "increasing"
        assert result["delta"] > 0

    def test_insufficient_data(self):
        eng = _engine()
        result = eng.detect_commitment_risks()
        assert result["trend"] == "insufficient_data"


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_populated(self):
        eng = _engine()
        eng.record_commitment(
            commitment_id="ri-001",
            utilization_level=UtilizationLevel.WASTED,
            commitment_type=CommitmentType.RESERVED_INSTANCE,
            utilization_pct=15.0,
            team="finops",
        )
        report = eng.generate_report()
        assert isinstance(report, CommitmentUtilizationReport)
        assert report.total_records == 1
        assert report.underutilized_commitments == 1
        assert report.avg_utilization_pct == 15.0
        assert len(report.recommendations) > 0

    def test_empty(self):
        eng = _engine()
        report = eng.generate_report()
        assert report.total_records == 0
        assert "below threshold" in report.recommendations[0]


# ---------------------------------------------------------------------------
# clear_data / get_stats
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears(self):
        eng = _engine()
        eng.record_commitment(commitment_id="ri-001")
        eng.add_utilization(detail_name="d1")
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
        assert stats["type_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        eng.record_commitment(
            commitment_id="ri-001",
            commitment_type=CommitmentType.RESERVED_INSTANCE,
            team="finops",
        )
        stats = eng.get_stats()
        assert stats["total_records"] == 1
        assert stats["unique_teams"] == 1
        assert stats["unique_commitments"] == 1
        assert "reserved_instance" in stats["type_distribution"]
