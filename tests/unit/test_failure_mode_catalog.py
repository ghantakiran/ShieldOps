"""Tests for shieldops.topology.failure_mode_catalog — FailureModeCatalog.

Covers FailureSeverity, DetectionMethod, and MitigationStrategy enums,
FailureMode / FailureOccurrence / FailureModeCatalogReport models, and all
FailureModeCatalog operations including failure mode registration, occurrence
recording, MTBF calculation, frequency ranking, unmitigated mode identification,
detection coverage analysis, and report generation.
"""

from __future__ import annotations

from shieldops.topology.failure_mode_catalog import (
    DetectionMethod,
    FailureMode,
    FailureModeCatalog,
    FailureModeCatalogReport,
    FailureOccurrence,
    FailureSeverity,
    MitigationStrategy,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine(**kw) -> FailureModeCatalog:
    return FailureModeCatalog(**kw)


# ===========================================================================
# Enum tests
# ===========================================================================


class TestEnums:
    """Validate every member of FailureSeverity, DetectionMethod, and MitigationStrategy."""

    # -- FailureSeverity (5 members) ------------------------------------------

    def test_severity_cosmetic(self):
        assert FailureSeverity.COSMETIC == "cosmetic"

    def test_severity_minor(self):
        assert FailureSeverity.MINOR == "minor"

    def test_severity_major(self):
        assert FailureSeverity.MAJOR == "major"

    def test_severity_critical(self):
        assert FailureSeverity.CRITICAL == "critical"

    def test_severity_catastrophic(self):
        assert FailureSeverity.CATASTROPHIC == "catastrophic"

    # -- DetectionMethod (5 members) ------------------------------------------

    def test_detection_automated_alert(self):
        assert DetectionMethod.AUTOMATED_ALERT == "automated_alert"

    def test_detection_manual_check(self):
        assert DetectionMethod.MANUAL_CHECK == "manual_check"

    def test_detection_synthetic_probe(self):
        assert DetectionMethod.SYNTHETIC_PROBE == "synthetic_probe"

    def test_detection_log_pattern(self):
        assert DetectionMethod.LOG_PATTERN == "log_pattern"

    def test_detection_metric_threshold(self):
        assert DetectionMethod.METRIC_THRESHOLD == "metric_threshold"

    # -- MitigationStrategy (5 members) ---------------------------------------

    def test_mitigation_retry(self):
        assert MitigationStrategy.RETRY == "retry"

    def test_mitigation_circuit_break(self):
        assert MitigationStrategy.CIRCUIT_BREAK == "circuit_break"

    def test_mitigation_failover(self):
        assert MitigationStrategy.FAILOVER == "failover"

    def test_mitigation_graceful_degrade(self):
        assert MitigationStrategy.GRACEFUL_DEGRADE == "graceful_degrade"

    def test_mitigation_manual_intervention(self):
        assert MitigationStrategy.MANUAL_INTERVENTION == "manual_intervention"


# ===========================================================================
# Model defaults
# ===========================================================================


class TestModels:
    """Verify default field values for each Pydantic model."""

    def test_failure_mode_defaults(self):
        m = FailureMode()
        assert m.id
        assert m.service_name == ""
        assert m.name == ""
        assert m.severity == FailureSeverity.MINOR
        assert m.detection_method == DetectionMethod.AUTOMATED_ALERT
        assert m.mitigation_strategy == MitigationStrategy.RETRY
        assert m.description == ""
        assert m.is_mitigated is False
        assert m.occurrences_count == 0
        assert m.last_occurrence_at == 0.0
        assert m.created_at > 0

    def test_failure_occurrence_defaults(self):
        o = FailureOccurrence()
        assert o.id
        assert o.failure_mode_id == ""
        assert o.occurred_at > 0
        assert o.detected_at == 0.0
        assert o.resolved_at == 0.0
        assert o.notes == ""

    def test_failure_mode_catalog_report_defaults(self):
        r = FailureModeCatalogReport()
        assert r.total_modes == 0
        assert r.total_occurrences == 0
        assert r.unmitigated_count == 0
        assert r.by_severity == {}
        assert r.by_detection == {}
        assert r.avg_mtbf_hours == 0.0
        assert r.recommendations == []
        assert r.generated_at > 0


# ===========================================================================
# RegisterFailureMode
# ===========================================================================


class TestRegisterFailureMode:
    """Test FailureModeCatalog.register_failure_mode."""

    def test_basic_registration(self):
        eng = _engine()
        mode = eng.register_failure_mode(
            service_name="auth-svc",
            name="Connection timeout",
            severity=FailureSeverity.MAJOR,
            detection_method=DetectionMethod.METRIC_THRESHOLD,
            mitigation_strategy=MitigationStrategy.CIRCUIT_BREAK,
            description="DB connections timing out under load",
        )
        assert mode.id
        assert mode.service_name == "auth-svc"
        assert mode.name == "Connection timeout"
        assert mode.severity == FailureSeverity.MAJOR
        assert mode.detection_method == DetectionMethod.METRIC_THRESHOLD
        assert mode.mitigation_strategy == MitigationStrategy.CIRCUIT_BREAK
        assert mode.is_mitigated is False

    def test_eviction_on_overflow(self):
        eng = _engine(max_modes=2)
        eng.register_failure_mode(service_name="svc-a", name="mode-1")
        eng.register_failure_mode(service_name="svc-b", name="mode-2")
        m3 = eng.register_failure_mode(service_name="svc-c", name="mode-3")
        modes = eng.list_failure_modes(limit=10)
        assert len(modes) == 2
        assert modes[-1].id == m3.id

    def test_mitigated_flag(self):
        eng = _engine()
        mode = eng.register_failure_mode(
            service_name="svc-a", name="mitigated-mode", is_mitigated=True
        )
        assert mode.is_mitigated is True


# ===========================================================================
# GetFailureMode
# ===========================================================================


class TestGetFailureMode:
    """Test FailureModeCatalog.get_failure_mode."""

    def test_found(self):
        eng = _engine()
        mode = eng.register_failure_mode(service_name="svc-a", name="find-me")
        assert eng.get_failure_mode(mode.id) is mode

    def test_not_found(self):
        eng = _engine()
        assert eng.get_failure_mode("nonexistent-id") is None


# ===========================================================================
# ListFailureModes
# ===========================================================================


class TestListFailureModes:
    """Test FailureModeCatalog.list_failure_modes with various filters."""

    def test_all_modes(self):
        eng = _engine()
        eng.register_failure_mode(service_name="svc-a", name="mode-1")
        eng.register_failure_mode(service_name="svc-b", name="mode-2")
        assert len(eng.list_failure_modes()) == 2

    def test_filter_by_severity(self):
        eng = _engine()
        eng.register_failure_mode(
            service_name="svc-a", name="minor", severity=FailureSeverity.MINOR
        )
        eng.register_failure_mode(
            service_name="svc-b", name="critical", severity=FailureSeverity.CRITICAL
        )
        results = eng.list_failure_modes(severity=FailureSeverity.CRITICAL)
        assert len(results) == 1
        assert results[0].severity == FailureSeverity.CRITICAL

    def test_filter_by_service(self):
        eng = _engine()
        eng.register_failure_mode(service_name="auth-svc", name="m1")
        eng.register_failure_mode(service_name="billing-svc", name="m2")
        eng.register_failure_mode(service_name="auth-svc", name="m3")
        results = eng.list_failure_modes(service_name="auth-svc")
        assert len(results) == 2
        assert all(m.service_name == "auth-svc" for m in results)

    def test_filter_by_detection_method(self):
        eng = _engine()
        eng.register_failure_mode(
            service_name="svc",
            name="auto",
            detection_method=DetectionMethod.AUTOMATED_ALERT,
        )
        eng.register_failure_mode(
            service_name="svc",
            name="manual",
            detection_method=DetectionMethod.MANUAL_CHECK,
        )
        results = eng.list_failure_modes(detection_method=DetectionMethod.MANUAL_CHECK)
        assert len(results) == 1
        assert results[0].detection_method == DetectionMethod.MANUAL_CHECK


# ===========================================================================
# RecordOccurrence
# ===========================================================================


class TestRecordOccurrence:
    """Test FailureModeCatalog.record_occurrence."""

    def test_record_for_existing_mode(self):
        eng = _engine()
        mode = eng.register_failure_mode(service_name="svc-a", name="timeout")
        occ = eng.record_occurrence(
            failure_mode_id=mode.id,
            detected_at=1000.0,
            resolved_at=1500.0,
            notes="Resolved by restart",
        )
        assert occ is not None
        assert occ.failure_mode_id == mode.id
        assert occ.detected_at == 1000.0
        assert occ.resolved_at == 1500.0
        assert occ.notes == "Resolved by restart"
        assert mode.occurrences_count == 1
        assert mode.last_occurrence_at == occ.occurred_at

    def test_record_for_nonexistent_mode(self):
        eng = _engine()
        result = eng.record_occurrence(failure_mode_id="nonexistent")
        assert result is None

    def test_multiple_occurrences_increment(self):
        eng = _engine()
        mode = eng.register_failure_mode(service_name="svc", name="flaky")
        eng.record_occurrence(failure_mode_id=mode.id)
        eng.record_occurrence(failure_mode_id=mode.id)
        eng.record_occurrence(failure_mode_id=mode.id)
        assert mode.occurrences_count == 3


# ===========================================================================
# CalculateMtbf
# ===========================================================================


class TestCalculateMtbf:
    """Test FailureModeCatalog.calculate_mtbf."""

    def test_fewer_than_two_occurrences(self):
        eng = _engine()
        mode = eng.register_failure_mode(service_name="svc", name="rare")
        eng.record_occurrence(failure_mode_id=mode.id)
        result = eng.calculate_mtbf(mode.id)
        assert result["occurrence_count"] == 1
        assert result["mtbf_hours"] == 0

    def test_two_occurrences(self):
        eng = _engine()
        mode = eng.register_failure_mode(service_name="svc", name="periodic")
        # Manually control occurred_at for deterministic MTBF
        occ1 = eng.record_occurrence(failure_mode_id=mode.id)
        occ1.occurred_at = 1000.0
        occ2 = eng.record_occurrence(failure_mode_id=mode.id)
        occ2.occurred_at = 4600.0  # 3600 seconds = 1 hour apart
        result = eng.calculate_mtbf(mode.id)
        assert result["occurrence_count"] == 2
        assert result["mtbf_hours"] == 1.0

    def test_three_occurrences(self):
        eng = _engine()
        mode = eng.register_failure_mode(service_name="svc", name="frequent")
        occ1 = eng.record_occurrence(failure_mode_id=mode.id)
        occ1.occurred_at = 0.0
        occ2 = eng.record_occurrence(failure_mode_id=mode.id)
        occ2.occurred_at = 7200.0  # 2 hours
        occ3 = eng.record_occurrence(failure_mode_id=mode.id)
        occ3.occurred_at = 14400.0  # 4 hours
        result = eng.calculate_mtbf(mode.id)
        assert result["occurrence_count"] == 3
        assert result["mtbf_hours"] == 2.0  # avg gap = 7200s = 2h


# ===========================================================================
# RankByFrequency
# ===========================================================================


class TestRankByFrequency:
    """Test FailureModeCatalog.rank_by_frequency."""

    def test_ranked_order(self):
        eng = _engine()
        m1 = eng.register_failure_mode(service_name="svc", name="rare")
        m2 = eng.register_failure_mode(service_name="svc", name="frequent")
        eng.record_occurrence(failure_mode_id=m1.id)
        eng.record_occurrence(failure_mode_id=m2.id)
        eng.record_occurrence(failure_mode_id=m2.id)
        eng.record_occurrence(failure_mode_id=m2.id)
        ranked = eng.rank_by_frequency()
        assert ranked[0].id == m2.id
        assert ranked[0].occurrences_count == 3
        assert ranked[1].id == m1.id
        assert ranked[1].occurrences_count == 1

    def test_empty_catalog(self):
        eng = _engine()
        assert eng.rank_by_frequency() == []


# ===========================================================================
# IdentifyUnmitigatedModes
# ===========================================================================


class TestIdentifyUnmitigatedModes:
    """Test FailureModeCatalog.identify_unmitigated_modes."""

    def test_with_mixed_modes(self):
        eng = _engine()
        eng.register_failure_mode(service_name="svc", name="mitigated", is_mitigated=True)
        eng.register_failure_mode(service_name="svc", name="unmitigated", is_mitigated=False)
        unmitigated = eng.identify_unmitigated_modes()
        assert len(unmitigated) == 1
        assert unmitigated[0].name == "unmitigated"

    def test_all_mitigated(self):
        eng = _engine()
        eng.register_failure_mode(service_name="svc", name="m1", is_mitigated=True)
        eng.register_failure_mode(service_name="svc", name="m2", is_mitigated=True)
        assert eng.identify_unmitigated_modes() == []


# ===========================================================================
# AnalyzeDetectionCoverage
# ===========================================================================


class TestAnalyzeDetectionCoverage:
    """Test FailureModeCatalog.analyze_detection_coverage."""

    def test_mixed_detection(self):
        eng = _engine()
        eng.register_failure_mode(
            service_name="svc",
            name="auto",
            detection_method=DetectionMethod.AUTOMATED_ALERT,
        )
        eng.register_failure_mode(
            service_name="svc",
            name="threshold",
            detection_method=DetectionMethod.METRIC_THRESHOLD,
        )
        eng.register_failure_mode(
            service_name="svc",
            name="manual",
            detection_method=DetectionMethod.MANUAL_CHECK,
        )
        coverage = eng.analyze_detection_coverage()
        assert coverage["total_modes"] == 3
        # 2 out of 3 are automated (AUTOMATED_ALERT + METRIC_THRESHOLD)
        assert coverage["automated_pct"] == round(2 / 3 * 100, 2)
        assert coverage["methods"]["automated_alert"] == 1
        assert coverage["methods"]["metric_threshold"] == 1
        assert coverage["methods"]["manual_check"] == 1

    def test_empty_catalog(self):
        eng = _engine()
        coverage = eng.analyze_detection_coverage()
        assert coverage["total_modes"] == 0
        assert coverage["automated_pct"] == 0.0
        assert coverage["methods"] == {}


# ===========================================================================
# GenerateCatalogReport
# ===========================================================================


class TestGenerateCatalogReport:
    """Test FailureModeCatalog.generate_catalog_report."""

    def test_basic_report(self):
        eng = _engine()
        m1 = eng.register_failure_mode(
            service_name="svc-a",
            name="timeout",
            severity=FailureSeverity.CRITICAL,
            detection_method=DetectionMethod.MANUAL_CHECK,
        )
        eng.register_failure_mode(
            service_name="svc-b",
            name="oom",
            severity=FailureSeverity.MAJOR,
            detection_method=DetectionMethod.AUTOMATED_ALERT,
            is_mitigated=True,
        )
        eng.record_occurrence(failure_mode_id=m1.id)
        report = eng.generate_catalog_report()
        assert isinstance(report, FailureModeCatalogReport)
        assert report.total_modes == 2
        assert report.total_occurrences == 1
        assert report.unmitigated_count == 1
        assert report.by_severity["critical"] == 1
        assert report.by_severity["major"] == 1
        assert report.generated_at > 0
        # Should have recommendations for unmitigated + low automated + critical
        assert len(report.recommendations) >= 1

    def test_empty_report(self):
        eng = _engine()
        report = eng.generate_catalog_report()
        assert report.total_modes == 0
        assert report.total_occurrences == 0
        assert report.avg_mtbf_hours == 0.0


# ===========================================================================
# ClearData
# ===========================================================================


class TestClearData:
    """Test FailureModeCatalog.clear_data."""

    def test_clears_all(self):
        eng = _engine()
        mode = eng.register_failure_mode(service_name="svc", name="temp")
        eng.record_occurrence(failure_mode_id=mode.id)
        eng.clear_data()
        assert len(eng.list_failure_modes()) == 0
        stats = eng.get_stats()
        assert stats["total_modes"] == 0
        assert stats["total_occurrences"] == 0


# ===========================================================================
# GetStats
# ===========================================================================


class TestGetStats:
    """Test FailureModeCatalog.get_stats."""

    def test_empty(self):
        eng = _engine()
        stats = eng.get_stats()
        assert stats["total_modes"] == 0
        assert stats["total_occurrences"] == 0
        assert stats["unique_services"] == 0
        assert stats["severity_distribution"] == {}
        assert stats["detection_distribution"] == {}
        assert stats["mitigation_distribution"] == {}

    def test_populated(self):
        eng = _engine()
        m = eng.register_failure_mode(
            service_name="auth-svc",
            name="timeout",
            severity=FailureSeverity.CRITICAL,
            detection_method=DetectionMethod.AUTOMATED_ALERT,
            mitigation_strategy=MitigationStrategy.CIRCUIT_BREAK,
        )
        eng.register_failure_mode(
            service_name="billing-svc",
            name="oom",
            severity=FailureSeverity.MAJOR,
            detection_method=DetectionMethod.METRIC_THRESHOLD,
            mitigation_strategy=MitigationStrategy.FAILOVER,
        )
        eng.record_occurrence(failure_mode_id=m.id)
        stats = eng.get_stats()
        assert stats["total_modes"] == 2
        assert stats["total_occurrences"] == 1
        assert stats["unique_services"] == 2
        assert stats["severity_distribution"]["critical"] == 1
        assert stats["severity_distribution"]["major"] == 1
        assert stats["detection_distribution"]["automated_alert"] == 1
        assert stats["detection_distribution"]["metric_threshold"] == 1
        assert stats["mitigation_distribution"]["circuit_break"] == 1
        assert stats["mitigation_distribution"]["failover"] == 1
