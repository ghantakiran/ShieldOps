"""Tests for shieldops.analytics.workload_fingerprint — WorkloadFingerprintEngine."""

from __future__ import annotations

from shieldops.analytics.workload_fingerprint import (
    DriftAlert,
    FingerprintStatus,
    WorkloadFingerprint,
    WorkloadFingerprintEngine,
    WorkloadSample,
    WorkloadType,
)


def _engine(**kw) -> WorkloadFingerprintEngine:
    return WorkloadFingerprintEngine(**kw)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestEnums:
    # WorkloadType (6 values)

    def test_workload_type_web_server(self):
        assert WorkloadType.WEB_SERVER == "web_server"

    def test_workload_type_batch_job(self):
        assert WorkloadType.BATCH_JOB == "batch_job"

    def test_workload_type_stream_processor(self):
        assert WorkloadType.STREAM_PROCESSOR == "stream_processor"

    def test_workload_type_database(self):
        assert WorkloadType.DATABASE == "database"

    def test_workload_type_cache(self):
        assert WorkloadType.CACHE == "cache"

    def test_workload_type_queue_worker(self):
        assert WorkloadType.QUEUE_WORKER == "queue_worker"

    # FingerprintStatus (4 values)

    def test_status_learning(self):
        assert FingerprintStatus.LEARNING == "learning"

    def test_status_stable(self):
        assert FingerprintStatus.STABLE == "stable"

    def test_status_drifted(self):
        assert FingerprintStatus.DRIFTED == "drifted"

    def test_status_unknown(self):
        assert FingerprintStatus.UNKNOWN == "unknown"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_workload_fingerprint_defaults(self):
        fp = WorkloadFingerprint(service="api")
        assert fp.id
        assert fp.workload_type == WorkloadType.WEB_SERVER
        assert fp.status == FingerprintStatus.LEARNING
        assert fp.sample_count == 0
        assert fp.cpu_mean == 0.0
        assert fp.cpu_stddev == 0.0
        assert fp.memory_mean == 0.0
        assert fp.memory_stddev == 0.0
        assert fp.request_rate_mean == 0.0
        assert fp.created_at > 0

    def test_workload_sample_defaults(self):
        sample = WorkloadSample(service="api")
        assert sample.id
        assert sample.cpu_pct == 0.0
        assert sample.memory_pct == 0.0
        assert sample.request_rate == 0.0
        assert sample.error_rate == 0.0
        assert sample.latency_p99_ms == 0.0
        assert sample.metadata == {}
        assert sample.timestamp > 0

    def test_drift_alert_defaults(self):
        alert = DriftAlert(
            service="api",
            metric="cpu_pct",
            expected_value=50.0,
            observed_value=90.0,
            deviation_pct=80.0,
        )
        assert alert.id
        assert alert.message == ""
        assert alert.detected_at > 0


# ---------------------------------------------------------------------------
# record_sample
# ---------------------------------------------------------------------------


class TestRecordSample:
    def test_basic_record(self):
        e = _engine()
        sample = e.record_sample(service="api", cpu_pct=25.0, memory_pct=50.0)
        assert sample.service == "api"
        assert sample.cpu_pct == 25.0
        assert sample.memory_pct == 50.0

    def test_creates_fingerprint(self):
        e = _engine()
        e.record_sample(service="api", cpu_pct=10.0)
        fp = e.get_fingerprint("api")
        assert fp is not None
        assert fp.service == "api"
        assert fp.sample_count == 1

    def test_updates_metrics(self):
        e = _engine()
        e.record_sample(service="api", cpu_pct=10.0)
        e.record_sample(service="api", cpu_pct=30.0)
        fp = e.get_fingerprint("api")
        assert fp is not None
        assert fp.sample_count == 2
        assert fp.cpu_mean == 20.0  # (10+30)/2

    def test_trims_to_max(self):
        e = _engine(max_samples=3)
        for _i in range(5):
            e.record_sample(service="api", cpu_pct=float(_i))
        assert len(e._samples) == 3

    def test_becomes_stable_after_min_samples(self):
        e = _engine(min_samples_for_stable=5)
        for _i in range(4):
            e.record_sample(service="api", cpu_pct=10.0)
        fp = e.get_fingerprint("api")
        assert fp.status == FingerprintStatus.LEARNING
        e.record_sample(service="api", cpu_pct=10.0)
        fp = e.get_fingerprint("api")
        assert fp.status == FingerprintStatus.STABLE


# ---------------------------------------------------------------------------
# get_fingerprint
# ---------------------------------------------------------------------------


class TestGetFingerprint:
    def test_found(self):
        e = _engine()
        e.record_sample(service="api", cpu_pct=10.0)
        assert e.get_fingerprint("api") is not None

    def test_not_found(self):
        e = _engine()
        assert e.get_fingerprint("nonexistent") is None


# ---------------------------------------------------------------------------
# list_fingerprints
# ---------------------------------------------------------------------------


class TestListFingerprints:
    def test_all(self):
        e = _engine()
        e.record_sample(service="api", cpu_pct=10.0)
        e.record_sample(service="db", cpu_pct=20.0)
        assert len(e.list_fingerprints()) == 2

    def test_by_status(self):
        e = _engine(min_samples_for_stable=2)
        e.record_sample(service="api", cpu_pct=10.0)
        e.record_sample(service="db", cpu_pct=20.0)
        e.record_sample(service="db", cpu_pct=30.0)
        learning = e.list_fingerprints(status=FingerprintStatus.LEARNING)
        stable = e.list_fingerprints(status=FingerprintStatus.STABLE)
        assert len(learning) == 1
        assert len(stable) == 1

    def test_by_workload_type(self):
        e = _engine()
        e.record_sample(service="api", cpu_pct=10.0)
        e.record_sample(service="db", cpu_pct=20.0)
        e.set_workload_type("db", WorkloadType.DATABASE)
        web = e.list_fingerprints(workload_type=WorkloadType.WEB_SERVER)
        db = e.list_fingerprints(workload_type=WorkloadType.DATABASE)
        assert len(web) == 1
        assert len(db) == 1


# ---------------------------------------------------------------------------
# check_drift
# ---------------------------------------------------------------------------


class TestCheckDrift:
    def test_no_drift_with_normal_values(self):
        e = _engine(min_samples_for_stable=2, drift_threshold_pct=50.0)
        e.record_sample(service="api", cpu_pct=50.0)
        e.record_sample(service="api", cpu_pct=50.0)
        alerts = e.check_drift("api")
        assert alerts == []

    def test_drift_detected_with_deviation(self):
        e = _engine(min_samples_for_stable=2, drift_threshold_pct=50.0)
        # Build a baseline around cpu=10
        e.record_sample(service="api", cpu_pct=10.0, memory_pct=10.0)
        e.record_sample(service="api", cpu_pct=10.0, memory_pct=10.0)
        # Now record an extreme sample
        e.record_sample(service="api", cpu_pct=100.0, memory_pct=10.0)
        alerts = e.check_drift("api")
        assert len(alerts) > 0
        metric_names = [a.metric for a in alerts]
        assert "cpu_pct" in metric_names

    def test_returns_drift_alerts_with_details(self):
        e = _engine(min_samples_for_stable=2, drift_threshold_pct=50.0)
        e.record_sample(service="api", cpu_pct=10.0)
        e.record_sample(service="api", cpu_pct=10.0)
        e.record_sample(service="api", cpu_pct=100.0)
        alerts = e.check_drift("api")
        for alert in alerts:
            assert alert.service == "api"
            assert alert.deviation_pct > 0
            assert alert.expected_value >= 0
            assert alert.observed_value >= 0


# ---------------------------------------------------------------------------
# set_workload_type
# ---------------------------------------------------------------------------


class TestSetWorkloadType:
    def test_basic(self):
        e = _engine()
        e.record_sample(service="db", cpu_pct=10.0)
        result = e.set_workload_type("db", WorkloadType.DATABASE)
        assert result is not None
        assert result.workload_type == WorkloadType.DATABASE

    def test_not_found(self):
        e = _engine()
        result = e.set_workload_type("unknown", WorkloadType.DATABASE)
        assert result is None


# ---------------------------------------------------------------------------
# get_samples
# ---------------------------------------------------------------------------


class TestGetSamples:
    def test_all_for_service(self):
        e = _engine()
        e.record_sample(service="api", cpu_pct=10.0)
        e.record_sample(service="api", cpu_pct=20.0)
        e.record_sample(service="db", cpu_pct=30.0)
        result = e.get_samples("api")
        assert len(result) == 2

    def test_newest_first(self):
        e = _engine()
        e.record_sample(service="api", cpu_pct=10.0)
        e.record_sample(service="api", cpu_pct=20.0)
        result = e.get_samples("api")
        assert result[0].cpu_pct == 20.0
        assert result[1].cpu_pct == 10.0

    def test_respects_limit(self):
        e = _engine()
        for _i in range(10):
            e.record_sample(service="api", cpu_pct=float(_i))
        result = e.get_samples("api", limit=3)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# clear_samples
# ---------------------------------------------------------------------------


class TestClearSamples:
    def test_clears_for_service(self):
        e = _engine()
        e.record_sample(service="api", cpu_pct=10.0)
        e.record_sample(service="db", cpu_pct=20.0)
        cleared = e.clear_samples("api")
        assert cleared == 1
        assert len(e._samples) == 1
        assert e.get_fingerprint("api") is None

    def test_resets_fingerprint_status(self):
        e = _engine(min_samples_for_stable=2)
        e.record_sample(service="api", cpu_pct=10.0)
        e.record_sample(service="api", cpu_pct=20.0)
        fp = e.get_fingerprint("api")
        assert fp.status == FingerprintStatus.STABLE
        e.clear_samples("api")
        assert e.get_fingerprint("api") is None


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        e = _engine()
        stats = e.get_stats()
        assert stats["total_samples"] == 0
        assert stats["total_fingerprints"] == 0
        assert stats["stable_count"] == 0
        assert stats["drifted_count"] == 0
        assert stats["learning_count"] == 0
        assert stats["avg_cpu"] == 0.0
        assert stats["avg_memory"] == 0.0

    def test_populated(self):
        e = _engine(min_samples_for_stable=2)
        e.record_sample(service="api", cpu_pct=10.0, memory_pct=20.0)
        e.record_sample(service="api", cpu_pct=30.0, memory_pct=40.0)
        stats = e.get_stats()
        assert stats["total_samples"] == 2
        assert stats["total_fingerprints"] == 1
        assert stats["stable_count"] == 1
        assert stats["learning_count"] == 0
        assert stats["avg_cpu"] == 20.0
        assert stats["avg_memory"] == 30.0
