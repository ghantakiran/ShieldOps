"""Tests for shieldops.billing.cost_anomaly_rca — CostAnomalyRootCauseAnalyzer."""

from __future__ import annotations

import time

from shieldops.billing.cost_anomaly_rca import (
    CostAnomalyRootCauseAnalyzer,
    CostRCAReport,
    CostSpike,
    ImpactSeverity,
    InvestigationStatus,
    RootCauseCategory,
    RootCauseFinding,
)


def _engine(**kw) -> CostAnomalyRootCauseAnalyzer:
    return CostAnomalyRootCauseAnalyzer(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # RootCauseCategory (6)
    def test_category_scaling_event(self):
        assert RootCauseCategory.SCALING_EVENT == "scaling_event"

    def test_category_misconfiguration(self):
        assert RootCauseCategory.MISCONFIGURATION == "misconfiguration"

    def test_category_traffic_spike(self):
        assert RootCauseCategory.TRAFFIC_SPIKE == "traffic_spike"

    def test_category_data_transfer(self):
        assert RootCauseCategory.DATA_TRANSFER == "data_transfer"

    def test_category_new_resource(self):
        assert RootCauseCategory.NEW_RESOURCE == "new_resource"

    def test_category_pricing_change(self):
        assert RootCauseCategory.PRICING_CHANGE == "pricing_change"

    # InvestigationStatus (5)
    def test_status_open(self):
        assert InvestigationStatus.OPEN == "open"

    def test_status_investigating(self):
        assert InvestigationStatus.INVESTIGATING == "investigating"

    def test_status_root_cause_found(self):
        assert InvestigationStatus.ROOT_CAUSE_FOUND == "root_cause_found"

    def test_status_remediated(self):
        assert InvestigationStatus.REMEDIATED == "remediated"

    def test_status_false_positive(self):
        assert InvestigationStatus.FALSE_POSITIVE == "false_positive"

    # ImpactSeverity (5)
    def test_severity_trivial(self):
        assert ImpactSeverity.TRIVIAL == "trivial"

    def test_severity_minor(self):
        assert ImpactSeverity.MINOR == "minor"

    def test_severity_moderate(self):
        assert ImpactSeverity.MODERATE == "moderate"

    def test_severity_major(self):
        assert ImpactSeverity.MAJOR == "major"

    def test_severity_severe(self):
        assert ImpactSeverity.SEVERE == "severe"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_cost_spike_defaults(self):
        s = CostSpike()
        assert s.id
        assert s.service_name == ""
        assert s.resource_id == ""
        assert s.spike_amount == 0.0
        assert s.baseline_amount == 0.0
        assert s.deviation_pct == 0.0
        assert s.status == InvestigationStatus.OPEN
        assert s.root_cause_category is None
        assert s.created_at > 0

    def test_root_cause_finding_defaults(self):
        f = RootCauseFinding()
        assert f.id
        assert f.spike_id == ""
        assert f.category == RootCauseCategory.SCALING_EVENT
        assert f.description == ""
        assert f.confidence_pct == 0.0
        assert f.excess_spend == 0.0
        assert f.remediation_suggestion == ""
        assert f.created_at > 0

    def test_cost_rca_report_defaults(self):
        r = CostRCAReport()
        assert r.total_spikes == 0
        assert r.open_investigations == 0
        assert r.resolved_count == 0
        assert r.total_excess_spend == 0.0
        assert r.avg_deviation_pct == 0.0
        assert r.category_distribution == {}
        assert r.severity_distribution == {}
        assert r.recommendations == []
        assert r.generated_at > 0


# ---------------------------------------------------------------------------
# record_spike
# ---------------------------------------------------------------------------


class TestRecordSpike:
    def test_basic_record_with_auto_deviation(self):
        eng = _engine()
        spike = eng.record_spike(
            service_name="ec2",
            resource_id="i-abc123",
            spike_amount=300.0,
            baseline_amount=100.0,
        )
        assert spike.service_name == "ec2"
        assert spike.resource_id == "i-abc123"
        assert spike.spike_amount == 300.0
        assert spike.baseline_amount == 100.0
        assert spike.deviation_pct == 200.0
        assert spike.status == InvestigationStatus.OPEN

    def test_eviction_at_max(self):
        eng = _engine(max_spikes=3)
        for i in range(5):
            eng.record_spike(
                service_name=f"svc-{i}",
                resource_id=f"res-{i}",
                spike_amount=float(i * 100),
                baseline_amount=50.0,
            )
        assert len(eng._spikes) == 3


# ---------------------------------------------------------------------------
# get_spike
# ---------------------------------------------------------------------------


class TestGetSpike:
    def test_found(self):
        eng = _engine()
        spike = eng.record_spike(
            service_name="rds",
            resource_id="db-1",
            spike_amount=200.0,
            baseline_amount=100.0,
        )
        assert eng.get_spike(spike.id) is not None
        assert eng.get_spike(spike.id).service_name == "rds"

    def test_not_found(self):
        eng = _engine()
        assert eng.get_spike("nonexistent") is None


# ---------------------------------------------------------------------------
# list_spikes
# ---------------------------------------------------------------------------


class TestListSpikes:
    def test_list_all(self):
        eng = _engine()
        eng.record_spike("ec2", "r1", 200.0, 100.0)
        eng.record_spike("rds", "r2", 300.0, 100.0)
        assert len(eng.list_spikes()) == 2

    def test_filter_by_status(self):
        eng = _engine()
        s1 = eng.record_spike("ec2", "r1", 200.0, 100.0)
        eng.record_spike("rds", "r2", 300.0, 100.0)
        eng.update_spike_status(s1.id, InvestigationStatus.REMEDIATED)
        results = eng.list_spikes(status=InvestigationStatus.OPEN)
        assert len(results) == 1
        assert results[0].service_name == "rds"

    def test_filter_by_service_name(self):
        eng = _engine()
        eng.record_spike("ec2", "r1", 200.0, 100.0)
        eng.record_spike("rds", "r2", 300.0, 100.0)
        eng.record_spike("ec2", "r3", 150.0, 100.0)
        results = eng.list_spikes(service_name="ec2")
        assert len(results) == 2


# ---------------------------------------------------------------------------
# analyze_root_cause
# ---------------------------------------------------------------------------


class TestAnalyzeRootCause:
    def test_high_deviation_misconfiguration(self):
        eng = _engine()
        spike = eng.record_spike("ec2", "i-001", 1000.0, 100.0)
        # deviation = 900%
        finding = eng.analyze_root_cause(spike.id)
        assert finding is not None
        assert finding.category == RootCauseCategory.MISCONFIGURATION
        assert finding.confidence_pct > 0
        assert finding.excess_spend == 900.0
        assert spike.status == InvestigationStatus.ROOT_CAUSE_FOUND
        assert spike.root_cause_category == RootCauseCategory.MISCONFIGURATION

    def test_moderate_deviation_traffic_spike(self):
        eng = _engine()
        spike = eng.record_spike("lambda", "fn-001", 160.0, 100.0)
        # deviation = 60%
        finding = eng.analyze_root_cause(spike.id)
        assert finding is not None
        assert finding.category == RootCauseCategory.TRAFFIC_SPIKE
        assert finding.excess_spend == 60.0


# ---------------------------------------------------------------------------
# correlate_with_changes
# ---------------------------------------------------------------------------


class TestCorrelateWithChanges:
    def test_with_correlated_spikes(self):
        eng = _engine()
        now = time.time()
        s1 = eng.record_spike("ec2", "r1", 200.0, 100.0, detected_at=now)
        eng.record_spike("rds", "r2", 300.0, 100.0, detected_at=now + 600)
        eng.record_spike("s3", "r3", 150.0, 100.0, detected_at=now + 7200)
        correlations = eng.correlate_with_changes(s1.id)
        # Only the rds spike is within +/- 1 hour; s3 is at +2 hours
        assert len(correlations) == 1
        assert correlations[0]["service_name"] == "rds"
        assert correlations[0]["same_service"] is False


# ---------------------------------------------------------------------------
# identify_top_offenders
# ---------------------------------------------------------------------------


class TestIdentifyTopOffenders:
    def test_multiple_services(self):
        eng = _engine()
        eng.record_spike("ec2", "r1", 500.0, 100.0)
        eng.record_spike("ec2", "r2", 300.0, 100.0)
        eng.record_spike("rds", "r3", 1000.0, 100.0)
        offenders = eng.identify_top_offenders()
        assert len(offenders) == 2
        # rds has the highest excess spend (900)
        assert offenders[0]["service_name"] == "rds"
        assert offenders[0]["total_excess_spend"] == 900.0
        # ec2 total excess = 400 + 200 = 600
        assert offenders[1]["service_name"] == "ec2"
        assert offenders[1]["spike_count"] == 2


# ---------------------------------------------------------------------------
# calculate_excess_spend
# ---------------------------------------------------------------------------


class TestCalculateExcessSpend:
    def test_total_excess(self):
        eng = _engine()
        eng.record_spike("ec2", "r1", 300.0, 100.0)
        eng.record_spike("rds", "r2", 500.0, 200.0)
        result = eng.calculate_excess_spend()
        assert result["total_excess_spend"] == 500.0
        assert result["spike_count"] == 2
        assert result["filter_service"] is None

    def test_by_service(self):
        eng = _engine()
        eng.record_spike("ec2", "r1", 300.0, 100.0)
        eng.record_spike("rds", "r2", 500.0, 200.0)
        result = eng.calculate_excess_spend(service_name="ec2")
        assert result["total_excess_spend"] == 200.0
        assert result["spike_count"] == 1
        assert result["filter_service"] == "ec2"
        assert "ec2" in result["service_breakdown"]


# ---------------------------------------------------------------------------
# update_spike_status
# ---------------------------------------------------------------------------


class TestUpdateSpikeStatus:
    def test_success(self):
        eng = _engine()
        spike = eng.record_spike("ec2", "r1", 200.0, 100.0)
        ok = eng.update_spike_status(
            spike.id,
            InvestigationStatus.REMEDIATED,
            root_cause_category=RootCauseCategory.SCALING_EVENT,
        )
        assert ok is True
        assert spike.status == InvestigationStatus.REMEDIATED
        assert spike.root_cause_category == RootCauseCategory.SCALING_EVENT

    def test_not_found(self):
        eng = _engine()
        assert eng.update_spike_status("bad-id", InvestigationStatus.OPEN) is False


# ---------------------------------------------------------------------------
# generate_rca_report
# ---------------------------------------------------------------------------


class TestGenerateRCAReport:
    def test_basic_report(self):
        eng = _engine()
        s1 = eng.record_spike("ec2", "r1", 500.0, 100.0)
        s2 = eng.record_spike("rds", "r2", 250.0, 100.0)
        eng.analyze_root_cause(s1.id)
        eng.analyze_root_cause(s2.id)
        report = eng.generate_rca_report()
        assert report.total_spikes == 2
        assert report.resolved_count == 2
        assert report.total_excess_spend > 0
        assert report.avg_deviation_pct > 0
        assert len(report.category_distribution) > 0
        assert len(report.severity_distribution) > 0
        assert len(report.recommendations) > 0
        assert report.generated_at > 0


# ---------------------------------------------------------------------------
# clear_data
# ---------------------------------------------------------------------------


class TestClearData:
    def test_clears_both_lists(self):
        eng = _engine()
        s = eng.record_spike("ec2", "r1", 300.0, 100.0)
        eng.analyze_root_cause(s.id)
        assert len(eng._spikes) == 1
        assert len(eng._findings) == 1
        eng.clear_data()
        assert len(eng._spikes) == 0
        assert len(eng._findings) == 0


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_spikes"] == 0
        assert stats["total_findings"] == 0
        assert stats["status_distribution"] == {}
        assert stats["service_distribution"] == {}
        assert stats["category_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        s = eng.record_spike("ec2", "r1", 500.0, 100.0)
        eng.analyze_root_cause(s.id)
        stats = eng.get_stats()
        assert stats["total_spikes"] == 1
        assert stats["total_findings"] == 1
        assert stats["max_spikes"] == 100000
        assert stats["deviation_threshold_pct"] == 25.0
