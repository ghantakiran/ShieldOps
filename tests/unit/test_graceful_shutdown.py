"""Tests for graceful shutdown middleware and request draining."""

from __future__ import annotations

import asyncio

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from shieldops.api.middleware.shutdown import (
    GracefulShutdownMiddleware,
    ShutdownState,
    get_shutdown_state,
    reset_shutdown_state,
)

# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_singleton():
    """Reset the global singleton before and after every test."""
    reset_shutdown_state()
    yield
    reset_shutdown_state()


@pytest.fixture
def state() -> ShutdownState:
    """Fresh ShutdownState for unit tests."""
    return ShutdownState()


def _make_app(
    shutdown_state: ShutdownState | None = None,
) -> Starlette:
    """Build a minimal Starlette app with the shutdown middleware."""

    async def homepage(request: Request) -> Response:
        return JSONResponse({"ok": True})

    async def health(request: Request) -> Response:
        return JSONResponse({"status": "healthy"})

    async def slow(request: Request) -> Response:
        await asyncio.sleep(0.3)
        return JSONResponse({"done": True})

    async def failing(request: Request) -> Response:
        raise RuntimeError("boom")

    app = Starlette(
        routes=[
            Route("/", homepage),
            Route("/health", health),
            Route("/slow", slow),
            Route("/fail", failing),
        ],
    )
    app.add_middleware(GracefulShutdownMiddleware)

    # If a specific state was provided, inject it as the singleton.
    if shutdown_state is not None:
        import shieldops.api.middleware.shutdown as _mod

        _mod._shutdown_state = shutdown_state

    return app


# ================================================================
# ShutdownState unit tests
# ================================================================


class TestShutdownStateInitialConditions:
    """Verify the default state of a fresh ShutdownState."""

    def test_not_shutting_down(self, state: ShutdownState) -> None:
        assert state.shutting_down is False

    def test_zero_in_flight(self, state: ShutdownState) -> None:
        assert state.in_flight == 0


class TestShutdownStateSignal:
    """Tests for signal_shutdown()."""

    def test_signal_sets_flag(self, state: ShutdownState) -> None:
        state.signal_shutdown()
        assert state.shutting_down is True

    def test_signal_is_idempotent(self, state: ShutdownState) -> None:
        state.signal_shutdown()
        state.signal_shutdown()
        assert state.shutting_down is True


class TestShutdownStateInFlight:
    """Tests for increment() / decrement()."""

    @pytest.mark.asyncio
    async def test_increment(self, state: ShutdownState) -> None:
        await state.increment()
        assert state.in_flight == 1

    @pytest.mark.asyncio
    async def test_increment_multiple(self, state: ShutdownState) -> None:
        await state.increment()
        await state.increment()
        await state.increment()
        assert state.in_flight == 3

    @pytest.mark.asyncio
    async def test_decrement(self, state: ShutdownState) -> None:
        await state.increment()
        await state.decrement()
        assert state.in_flight == 0

    @pytest.mark.asyncio
    async def test_decrement_never_negative(self, state: ShutdownState) -> None:
        await state.decrement()
        assert state.in_flight == 0

    @pytest.mark.asyncio
    async def test_increment_decrement_sequence(self, state: ShutdownState) -> None:
        await state.increment()
        await state.increment()
        await state.decrement()
        assert state.in_flight == 1
        await state.decrement()
        assert state.in_flight == 0


class TestShutdownStateDrain:
    """Tests for wait_for_drain()."""

    @pytest.mark.asyncio
    async def test_drain_immediate_when_empty(self, state: ShutdownState) -> None:
        result = await state.wait_for_drain(timeout=1.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_drain_waits_for_zero(self, state: ShutdownState) -> None:
        await state.increment()

        async def _release():
            await asyncio.sleep(0.05)
            await state.decrement()

        task = asyncio.create_task(_release())
        result = await state.wait_for_drain(timeout=2.0)
        assert result is True
        assert state.in_flight == 0
        await task

    @pytest.mark.asyncio
    async def test_drain_timeout_returns_false(self, state: ShutdownState) -> None:
        await state.increment()
        result = await state.wait_for_drain(timeout=0.05)
        assert result is False
        assert state.in_flight == 1

    @pytest.mark.asyncio
    async def test_decrement_signals_drain_event(self, state: ShutdownState) -> None:
        """Drain event should be set when count hits zero."""
        await state.increment()
        assert not state._drain_event.is_set()
        await state.decrement()
        assert state._drain_event.is_set()


class TestShutdownStateConcurrency:
    """Concurrent increment/decrement safety."""

    @pytest.mark.asyncio
    async def test_concurrent_increments(self, state: ShutdownState) -> None:
        tasks = [asyncio.create_task(state.increment()) for _ in range(100)]
        await asyncio.gather(*tasks)
        assert state.in_flight == 100

    @pytest.mark.asyncio
    async def test_concurrent_decrements(self, state: ShutdownState) -> None:
        for _ in range(50):
            await state.increment()

        tasks = [asyncio.create_task(state.decrement()) for _ in range(50)]
        await asyncio.gather(*tasks)
        assert state.in_flight == 0

    @pytest.mark.asyncio
    async def test_concurrent_mixed(self, state: ShutdownState) -> None:
        """Interleaved inc/dec should never go negative."""

        async def _worker():
            await state.increment()
            await asyncio.sleep(0)
            await state.decrement()

        tasks = [asyncio.create_task(_worker()) for _ in range(100)]
        await asyncio.gather(*tasks)
        assert state.in_flight == 0


class TestShutdownStateReset:
    """Tests for reset() helper."""

    @pytest.mark.asyncio
    async def test_reset_clears_everything(self, state: ShutdownState) -> None:
        await state.increment()
        state.signal_shutdown()
        state.reset()
        assert state.shutting_down is False
        assert state.in_flight == 0


# ================================================================
# Singleton accessor tests
# ================================================================


class TestShutdownStateSingleton:
    def test_get_returns_same_instance(self) -> None:
        a = get_shutdown_state()
        b = get_shutdown_state()
        assert a is b

    def test_reset_creates_new_instance(self) -> None:
        a = get_shutdown_state()
        reset_shutdown_state()
        b = get_shutdown_state()
        assert a is not b


# ================================================================
# Middleware tests (using Starlette TestClient)
# ================================================================


class TestGracefulShutdownMiddlewareNormal:
    """Middleware behaviour during normal (non-shutdown) operation."""

    def test_request_passes_through(self) -> None:
        app = _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_in_flight_counter_returns_to_zero(self) -> None:
        state = ShutdownState()
        app = _make_app(shutdown_state=state)
        client = TestClient(app, raise_server_exceptions=False)
        client.get("/")
        assert state.in_flight == 0

    def test_in_flight_counter_after_failure(self) -> None:
        state = ShutdownState()
        app = _make_app(shutdown_state=state)
        client = TestClient(app, raise_server_exceptions=False)
        client.get("/fail")
        # Counter must be decremented even on exception.
        assert state.in_flight == 0


class TestGracefulShutdownMiddlewareDuringShutdown:
    """Middleware behaviour after shutdown has been signaled."""

    def test_returns_503(self) -> None:
        state = ShutdownState()
        state.signal_shutdown()
        app = _make_app(shutdown_state=state)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/")
        assert response.status_code == 503

    def test_503_includes_retry_after(self) -> None:
        state = ShutdownState()
        state.signal_shutdown()
        app = _make_app(shutdown_state=state)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/")
        assert "retry-after" in response.headers
        assert response.headers["retry-after"] == "5"

    def test_503_json_body(self) -> None:
        state = ShutdownState()
        state.signal_shutdown()
        app = _make_app(shutdown_state=state)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/")
        body = response.json()
        assert body["detail"] == "Server is shutting down"

    def test_health_exempt_during_shutdown(self) -> None:
        state = ShutdownState()
        state.signal_shutdown()
        app = _make_app(shutdown_state=state)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_non_health_paths_rejected(self) -> None:
        state = ShutdownState()
        state.signal_shutdown()
        app = _make_app(shutdown_state=state)
        client = TestClient(app, raise_server_exceptions=False)
        for path in ["/", "/slow"]:
            response = client.get(path)
            assert response.status_code == 503, f"{path} should be rejected"


class TestGracefulShutdownMiddlewareMultipleRequests:
    """Verify correct tracking with multiple concurrent requests."""

    def test_multiple_sequential_requests(self) -> None:
        state = ShutdownState()
        app = _make_app(shutdown_state=state)
        client = TestClient(app, raise_server_exceptions=False)
        for _ in range(5):
            response = client.get("/")
            assert response.status_code == 200
        assert state.in_flight == 0


# ================================================================
# Integration tests (lifespan drain simulation)
# ================================================================


class TestLifespanShutdownIntegration:
    """Simulate the lifespan shutdown flow with drain."""

    @pytest.mark.asyncio
    async def test_signal_then_drain(self) -> None:
        """Drain completes immediately when no in-flight."""
        state = ShutdownState()
        state.signal_shutdown()
        assert state.shutting_down is True
        drained = await state.wait_for_drain(timeout=1.0)
        assert drained is True

    @pytest.mark.asyncio
    async def test_drain_waits_for_in_flight(self) -> None:
        """Drain blocks until in-flight hits zero."""
        state = ShutdownState()
        await state.increment()
        state.signal_shutdown()

        async def _finish_request():
            await asyncio.sleep(0.05)
            await state.decrement()

        task = asyncio.create_task(_finish_request())
        drained = await state.wait_for_drain(timeout=2.0)
        assert drained is True
        assert state.in_flight == 0
        await task

    @pytest.mark.asyncio
    async def test_drain_timeout_logs_warning(self) -> None:
        """Timeout returns False so caller can log warning."""
        state = ShutdownState()
        await state.increment()
        state.signal_shutdown()
        drained = await state.wait_for_drain(timeout=0.05)
        assert drained is False
        assert state.in_flight == 1

    @pytest.mark.asyncio
    async def test_full_shutdown_sequence(self) -> None:
        """End-to-end: signal -> drain -> cleanup callbacks."""
        state = ShutdownState()
        cleanup_called = False

        async def cleanup():
            nonlocal cleanup_called
            cleanup_called = True

        state.signal_shutdown()
        drained = await state.wait_for_drain(timeout=1.0)
        assert drained is True
        await cleanup()
        assert cleanup_called is True

    @pytest.mark.asyncio
    async def test_new_requests_rejected_after_signal(
        self,
    ) -> None:
        """After signal, the middleware should return 503."""
        state = ShutdownState()
        app = _make_app(shutdown_state=state)
        client = TestClient(app, raise_server_exceptions=False)

        # Normal request works
        response = client.get("/")
        assert response.status_code == 200

        # Signal shutdown
        state.signal_shutdown()

        # Now rejected
        response = client.get("/")
        assert response.status_code == 503

        # Health still works
        response = client.get("/health")
        assert response.status_code == 200
