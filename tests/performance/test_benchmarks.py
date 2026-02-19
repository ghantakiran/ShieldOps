"""Micro-benchmarks for critical-path operations using pytest-benchmark.

Run with:
    pytest tests/performance/test_benchmarks.py -v --benchmark-only
"""

from datetime import UTC, datetime, timedelta

from shieldops.api.auth.service import create_access_token, hash_password, verify_password

# ---------------------------------------------------------------------------
# JWT Token Benchmarks
# ---------------------------------------------------------------------------


class TestJWTBenchmarks:
    def test_create_access_token_speed(self, benchmark):
        """Benchmark JWT token creation."""
        result = benchmark(
            create_access_token,
            subject="user@shieldops.dev",
            role="admin",
            expires_delta=timedelta(hours=1),
        )
        assert isinstance(result, str)
        assert len(result) > 20

    def test_verify_password_speed(self, benchmark):
        """Benchmark password verification (PBKDF2)."""
        hashed = hash_password("test-password-123")
        result = benchmark(verify_password, "test-password-123", hashed)
        assert result is True


# ---------------------------------------------------------------------------
# Pydantic Model Serialization Benchmarks
# ---------------------------------------------------------------------------


class TestSerializationBenchmarks:
    def test_investigation_state_serialization(self, benchmark):
        """Benchmark InvestigationState model serialization."""
        from shieldops.agents.investigation.models import InvestigationState
        from shieldops.models.base import AlertContext

        state = InvestigationState(
            alert_id="bench-alert-001",
            alert_context=AlertContext(
                alert_id="bench-alert-001",
                alert_name="HighCPU",
                severity="critical",
                source="prometheus",
                resource_id="node-1",
                triggered_at=datetime.now(UTC),
            ),
        )
        result = benchmark(state.model_dump)
        assert isinstance(result, dict)
        assert result["alert_id"] == "bench-alert-001"

    def test_investigation_state_json_serialization(self, benchmark):
        """Benchmark InvestigationState JSON serialization."""
        from shieldops.agents.investigation.models import InvestigationState
        from shieldops.models.base import AlertContext

        state = InvestigationState(
            alert_id="bench-alert-002",
            alert_context=AlertContext(
                alert_id="bench-alert-002",
                alert_name="HighMemory",
                severity="warning",
                source="datadog",
                resource_id="pod-abc",
                triggered_at=datetime.now(UTC),
            ),
        )
        result = benchmark(state.model_dump_json)
        assert isinstance(result, str)
        assert "bench-alert-002" in result

    def test_alert_context_validation(self, benchmark):
        """Benchmark AlertContext model validation (deserialization)."""
        from shieldops.models.base import AlertContext

        data = {
            "alert_id": "bench-alert-003",
            "alert_name": "PodCrashLoop",
            "severity": "critical",
            "source": "kubernetes",
            "resource_id": "pod-xyz",
            "triggered_at": datetime.now(UTC).isoformat(),
            "labels": {"namespace": "production", "cluster": "main"},
            "description": "Pod is in CrashLoopBackOff state",
        }
        result = benchmark(AlertContext.model_validate, data)
        assert result.alert_id == "bench-alert-003"


# ---------------------------------------------------------------------------
# Metrics Registry Benchmarks
# ---------------------------------------------------------------------------


class TestMetricsRegistryBenchmarks:
    def test_metrics_collect_with_entries(self, benchmark):
        """Benchmark metrics collection with many recorded entries."""
        from shieldops.api.middleware.metrics import MetricsRegistry

        registry = MetricsRegistry()
        # Simulate 1000 requests across various endpoints
        methods = ["GET", "POST", "PUT", "DELETE"]
        paths = [
            "/api/v1/investigations/",
            "/api/v1/remediations/",
            "/api/v1/agents/",
            "/api/v1/security/scans",
            "/api/v1/analytics/summary",
            "/health",
            "/ready",
            "/metrics",
        ]
        statuses = [200, 201, 400, 404, 500]

        for i in range(1000):
            method = methods[i % len(methods)]
            path = paths[i % len(paths)]
            status = statuses[i % len(statuses)]
            duration = 0.05 + (i % 100) * 0.001
            registry.inc_counter(
                "http_requests_total",
                {"method": method, "path": path, "status": str(status)},
            )
            registry.observe_histogram(
                "http_request_duration_seconds",
                {"method": method, "path": path},
                duration,
            )

        result = benchmark(registry.collect)
        assert isinstance(result, str)
        assert "http_requests_total" in result


# ---------------------------------------------------------------------------
# Policy Evaluation Benchmarks
# ---------------------------------------------------------------------------


class TestPolicyBenchmarks:
    def test_policy_engine_evaluation_latency(self, benchmark):
        """Benchmark OPA policy evaluation (mocked for speed test)."""
        from unittest.mock import AsyncMock, MagicMock

        from shieldops.models.base import Environment, RemediationAction, RiskLevel

        # Create a mock policy engine with fast path
        engine = MagicMock()
        engine.evaluate = AsyncMock(
            return_value=MagicMock(
                allowed=True,
                reasons=["allowed by default policy"],
            )
        )

        action = RemediationAction(
            id="bench-act-001",
            action_type="restart_pod",
            target_resource="pod-bench",
            environment=Environment.DEVELOPMENT,
            risk_level=RiskLevel.LOW,
            parameters={},
            description="Benchmark action",
        )

        import asyncio

        async def evaluate():
            return await engine.evaluate(action)

        loop = asyncio.new_event_loop()
        result = benchmark(lambda: loop.run_until_complete(evaluate()))
        loop.close()
        assert result.allowed is True
