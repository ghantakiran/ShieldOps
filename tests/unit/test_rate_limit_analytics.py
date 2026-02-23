"""Tests for shieldops.analytics.rate_limit_analytics – RateLimitAnalyticsEngine."""

from __future__ import annotations

import time

from shieldops.analytics.rate_limit_analytics import (
    AnalyticsPeriod,
    LimitAction,
    OffenderProfile,
    QuotaUtilization,
    RateLimitAnalyticsEngine,
    RateLimitEvent,
    TrendBucket,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engine(**kwargs) -> RateLimitAnalyticsEngine:
    return RateLimitAnalyticsEngine(**kwargs)


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestEnums:
    def test_limit_action_values(self):
        assert LimitAction.ALLOWED == "allowed"
        assert LimitAction.THROTTLED == "throttled"
        assert LimitAction.BLOCKED == "blocked"
        assert LimitAction.WARNED == "warned"

    def test_analytics_period_values(self):
        assert AnalyticsPeriod.MINUTE == "minute"
        assert AnalyticsPeriod.HOUR == "hour"
        assert AnalyticsPeriod.DAY == "day"
        assert AnalyticsPeriod.WEEK == "week"


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


class TestModels:
    def test_rate_limit_event_defaults(self):
        ev = RateLimitEvent(
            client_id="client-1", endpoint="/api/v1/data", action=LimitAction.ALLOWED
        )
        assert ev.id
        assert ev.client_id == "client-1"
        assert ev.endpoint == "/api/v1/data"
        assert ev.action == LimitAction.ALLOWED
        assert ev.request_count == 1
        assert ev.metadata == {}
        assert ev.recorded_at > 0

    def test_offender_profile_fields(self):
        op = OffenderProfile(
            client_id="bad-actor",
            total_violations=50,
            blocked_count=30,
            throttled_count=20,
            first_seen=1000.0,
            last_seen=2000.0,
        )
        assert op.client_id == "bad-actor"
        assert op.total_violations == 50
        assert op.blocked_count == 30
        assert op.throttled_count == 20
        assert op.top_endpoints == []
        assert op.first_seen == 1000.0
        assert op.last_seen == 2000.0

    def test_quota_utilization_fields(self):
        qu = QuotaUtilization(
            endpoint="/api/users",
            total_requests=1000,
            allowed=900,
            throttled=80,
            blocked=20,
        )
        assert qu.endpoint == "/api/users"
        assert qu.total_requests == 1000
        assert qu.utilization_pct == 0.0

    def test_trend_bucket_fields(self):
        tb = TrendBucket(period="hour", timestamp=1000.0, total_events=50, blocked_events=5)
        assert tb.period == "hour"
        assert tb.timestamp == 1000.0
        assert tb.total_events == 50
        assert tb.blocked_events == 5


# ---------------------------------------------------------------------------
# Record event
# ---------------------------------------------------------------------------


class TestRecordEvent:
    def test_basic(self):
        e = _engine()
        ev = e.record_event(client_id="c1", endpoint="/api/v1/users", action=LimitAction.ALLOWED)
        assert ev.client_id == "c1"
        assert ev.endpoint == "/api/v1/users"
        assert ev.action == LimitAction.ALLOWED
        assert ev.id

    def test_with_metadata(self):
        e = _engine()
        ev = e.record_event(
            client_id="c1",
            endpoint="/api/v1/data",
            action=LimitAction.BLOCKED,
            request_count=10,
            metadata={"reason": "rate exceeded"},
        )
        assert ev.request_count == 10
        assert ev.metadata["reason"] == "rate exceeded"

    def test_max_events_trimming(self):
        e = _engine(max_events=5)
        for i in range(10):
            e.record_event(client_id=f"c{i}", endpoint="/api", action=LimitAction.ALLOWED)
        events = e.list_events(limit=100)
        assert len(events) == 5


# ---------------------------------------------------------------------------
# Top offenders
# ---------------------------------------------------------------------------


class TestGetTopOffenders:
    def test_empty(self):
        e = _engine()
        assert e.get_top_offenders() == []

    def test_with_violations(self):
        e = _engine()
        for _ in range(5):
            e.record_event("bad-client", "/api/v1/data", LimitAction.BLOCKED)
        for _ in range(3):
            e.record_event("bad-client", "/api/v1/users", LimitAction.THROTTLED)
        offenders = e.get_top_offenders()
        assert len(offenders) == 1
        assert offenders[0].client_id == "bad-client"
        assert offenders[0].total_violations == 8
        assert offenders[0].blocked_count == 5
        assert offenders[0].throttled_count == 3

    def test_respects_limit(self):
        e = _engine()
        for i in range(5):
            e.record_event(f"client-{i}", "/api", LimitAction.BLOCKED)
        offenders = e.get_top_offenders(limit=2)
        assert len(offenders) == 2

    def test_ignores_allowed_events(self):
        e = _engine()
        e.record_event("good-client", "/api", LimitAction.ALLOWED)
        e.record_event("good-client", "/api", LimitAction.WARNED)
        offenders = e.get_top_offenders()
        assert len(offenders) == 0

    def test_sorted_by_violations(self):
        e = _engine()
        for _ in range(3):
            e.record_event("client-a", "/api", LimitAction.BLOCKED)
        for _ in range(7):
            e.record_event("client-b", "/api", LimitAction.BLOCKED)
        offenders = e.get_top_offenders()
        assert offenders[0].client_id == "client-b"
        assert offenders[1].client_id == "client-a"


# ---------------------------------------------------------------------------
# Utilization
# ---------------------------------------------------------------------------


class TestGetUtilization:
    def test_all_endpoints(self):
        e = _engine()
        e.record_event("c1", "/api/users", LimitAction.ALLOWED, request_count=100)
        e.record_event("c2", "/api/data", LimitAction.BLOCKED, request_count=10)
        utils = e.get_utilization()
        assert len(utils) == 2

    def test_specific_endpoint(self):
        e = _engine()
        e.record_event("c1", "/api/users", LimitAction.ALLOWED, request_count=90)
        e.record_event("c1", "/api/users", LimitAction.THROTTLED, request_count=10)
        e.record_event("c2", "/api/data", LimitAction.ALLOWED, request_count=100)
        utils = e.get_utilization(endpoint="/api/users")
        assert len(utils) == 1
        assert utils[0].endpoint == "/api/users"
        assert utils[0].total_requests == 100
        assert utils[0].allowed == 90
        assert utils[0].throttled == 10
        assert utils[0].utilization_pct == 10.0

    def test_empty(self):
        e = _engine()
        assert e.get_utilization() == []


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------


class TestGetTrends:
    def test_basic_hourly_trends(self):
        e = _engine()
        now = time.time()
        # Record events within the last hour
        for _ in range(5):
            ev = e.record_event("c1", "/api", LimitAction.ALLOWED)
            ev.recorded_at = now - 60  # 1 minute ago
        for _ in range(3):
            ev = e.record_event("c1", "/api", LimitAction.BLOCKED)
            ev.recorded_at = now - 60
        trends = e.get_trends(period=AnalyticsPeriod.HOUR, hours=1)
        assert len(trends) >= 1
        total_events = sum(t.total_events for t in trends)
        assert total_events == 8

    def test_empty(self):
        e = _engine()
        trends = e.get_trends(hours=1)
        assert trends == []

    def test_excludes_old_events(self):
        e = _engine()
        now = time.time()
        ev = e.record_event("c1", "/api", LimitAction.ALLOWED)
        ev.recorded_at = now - 7200  # 2 hours ago
        trends = e.get_trends(period=AnalyticsPeriod.HOUR, hours=1)
        assert trends == []


# ---------------------------------------------------------------------------
# Burst detection
# ---------------------------------------------------------------------------


class TestGetBurstDetection:
    def test_no_bursts(self):
        e = _engine()
        e.record_event("c1", "/api", LimitAction.ALLOWED)
        bursts = e.get_burst_detection(window_seconds=60, threshold=100)
        assert bursts == []

    def test_burst_detected(self):
        e = _engine()
        now = time.time()
        for _ in range(150):
            ev = e.record_event("burst-client", "/api", LimitAction.ALLOWED)
            ev.recorded_at = now - 10  # within 60s window
        bursts = e.get_burst_detection(window_seconds=60, threshold=100)
        assert len(bursts) == 1
        assert bursts[0]["client_id"] == "burst-client"
        assert bursts[0]["event_count"] == 150

    def test_multiple_bursting_clients(self):
        e = _engine()
        now = time.time()
        for _ in range(120):
            ev = e.record_event("client-a", "/api", LimitAction.ALLOWED)
            ev.recorded_at = now - 5
        for _ in range(200):
            ev = e.record_event("client-b", "/api", LimitAction.ALLOWED)
            ev.recorded_at = now - 5
        bursts = e.get_burst_detection(window_seconds=60, threshold=100)
        assert len(bursts) == 2
        # sorted by event_count descending
        assert bursts[0]["client_id"] == "client-b"
        assert bursts[1]["client_id"] == "client-a"

    def test_burst_outside_window(self):
        e = _engine()
        now = time.time()
        for _ in range(150):
            ev = e.record_event("old-client", "/api", LimitAction.ALLOWED)
            ev.recorded_at = now - 120  # outside 60s window
        bursts = e.get_burst_detection(window_seconds=60, threshold=100)
        assert bursts == []


# ---------------------------------------------------------------------------
# List events
# ---------------------------------------------------------------------------


class TestListEvents:
    def test_all(self):
        e = _engine()
        e.record_event("c1", "/api/users", LimitAction.ALLOWED)
        e.record_event("c2", "/api/data", LimitAction.BLOCKED)
        events = e.list_events()
        assert len(events) == 2

    def test_filter_by_client(self):
        e = _engine()
        e.record_event("c1", "/api/users", LimitAction.ALLOWED)
        e.record_event("c2", "/api/data", LimitAction.BLOCKED)
        events = e.list_events(client_id="c1")
        assert len(events) == 1
        assert events[0].client_id == "c1"

    def test_filter_by_endpoint(self):
        e = _engine()
        e.record_event("c1", "/api/users", LimitAction.ALLOWED)
        e.record_event("c1", "/api/data", LimitAction.BLOCKED)
        events = e.list_events(endpoint="/api/data")
        assert len(events) == 1
        assert events[0].endpoint == "/api/data"

    def test_limit(self):
        e = _engine()
        for i in range(10):
            e.record_event(f"c{i}", "/api", LimitAction.ALLOWED)
        events = e.list_events(limit=3)
        assert len(events) == 3

    def test_empty(self):
        e = _engine()
        events = e.list_events()
        assert events == []


# ---------------------------------------------------------------------------
# Endpoint analytics
# ---------------------------------------------------------------------------


class TestGetEndpointAnalytics:
    def test_with_data(self):
        e = _engine()
        e.record_event("c1", "/api/users", LimitAction.ALLOWED, request_count=5)
        e.record_event("c2", "/api/users", LimitAction.BLOCKED, request_count=2)
        e.record_event("c3", "/api/users", LimitAction.THROTTLED, request_count=3)
        analytics = e.get_endpoint_analytics("/api/users")
        assert analytics["endpoint"] == "/api/users"
        assert analytics["total_events"] == 3
        assert analytics["unique_clients"] == 3
        assert analytics["requests_total"] == 10
        assert analytics["action_breakdown"]["allowed"] == 1
        assert analytics["action_breakdown"]["blocked"] == 1
        assert analytics["action_breakdown"]["throttled"] == 1

    def test_no_data(self):
        e = _engine()
        analytics = e.get_endpoint_analytics("/api/missing")
        assert analytics["endpoint"] == "/api/missing"
        assert analytics["total_events"] == 0
        assert analytics["unique_clients"] == 0
        assert analytics["action_breakdown"] == {}
        assert analytics["requests_total"] == 0


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_empty(self):
        e = _engine()
        s = e.get_stats()
        assert s["total_events"] == 0
        assert s["blocked_events"] == 0
        assert s["throttled_events"] == 0
        assert s["unique_clients"] == 0
        assert s["unique_endpoints"] == 0

    def test_with_data(self):
        e = _engine()
        e.record_event("c1", "/api/users", LimitAction.ALLOWED)
        e.record_event("c2", "/api/users", LimitAction.BLOCKED)
        e.record_event("c1", "/api/data", LimitAction.THROTTLED)
        s = e.get_stats()
        assert s["total_events"] == 3
        assert s["blocked_events"] == 1
        assert s["throttled_events"] == 1
        assert s["unique_clients"] == 2
        assert s["unique_endpoints"] == 2
        assert s["max_events"] == 100000
        assert s["retention_hours"] == 168


# ---------------------------------------------------------------------------
# Additional coverage: edge cases and combined filters
# ---------------------------------------------------------------------------


class TestRecordEventEdgeCases:
    def test_event_ids_are_unique(self):
        e = _engine()
        ev1 = e.record_event("c1", "/api", LimitAction.ALLOWED)
        ev2 = e.record_event("c1", "/api", LimitAction.ALLOWED)
        assert ev1.id != ev2.id

    def test_default_request_count_is_one(self):
        e = _engine()
        ev = e.record_event("c1", "/api", LimitAction.ALLOWED)
        assert ev.request_count == 1

    def test_recorded_at_is_set(self):
        before = time.time()
        e = _engine()
        ev = e.record_event("c1", "/api", LimitAction.ALLOWED)
        after = time.time()
        assert before <= ev.recorded_at <= after

    def test_metadata_defaults_to_empty(self):
        e = _engine()
        ev = e.record_event("c1", "/api", LimitAction.ALLOWED)
        assert ev.metadata == {}


class TestOffenderTopEndpoints:
    def test_top_endpoints_populated(self):
        e = _engine()
        for _ in range(5):
            e.record_event("c1", "/api/users", LimitAction.BLOCKED)
        for _ in range(3):
            e.record_event("c1", "/api/data", LimitAction.BLOCKED)
        offenders = e.get_top_offenders()
        assert len(offenders) == 1
        assert "/api/users" in offenders[0].top_endpoints
        assert "/api/data" in offenders[0].top_endpoints

    def test_offender_first_and_last_seen(self):
        e = _engine()
        now = time.time()
        ev1 = e.record_event("c1", "/api", LimitAction.BLOCKED)
        ev1.recorded_at = now - 100
        ev2 = e.record_event("c1", "/api", LimitAction.BLOCKED)
        ev2.recorded_at = now
        offenders = e.get_top_offenders()
        assert offenders[0].first_seen == now - 100
        assert offenders[0].last_seen == now


class TestUtilizationCalculation:
    def test_utilization_pct_all_blocked(self):
        e = _engine()
        e.record_event("c1", "/api", LimitAction.BLOCKED, request_count=100)
        utils = e.get_utilization()
        assert utils[0].utilization_pct == 100.0

    def test_utilization_pct_all_allowed(self):
        e = _engine()
        e.record_event("c1", "/api", LimitAction.ALLOWED, request_count=100)
        utils = e.get_utilization()
        assert utils[0].utilization_pct == 0.0

    def test_utilization_mixed(self):
        e = _engine()
        e.record_event("c1", "/api", LimitAction.ALLOWED, request_count=80)
        e.record_event("c2", "/api", LimitAction.THROTTLED, request_count=15)
        e.record_event("c3", "/api", LimitAction.BLOCKED, request_count=5)
        utils = e.get_utilization()
        # (15 + 5) / 100 * 100 = 20.0
        assert utils[0].utilization_pct == 20.0
        assert utils[0].total_requests == 100
        assert utils[0].allowed == 80


class TestListEventsCombined:
    def test_filter_by_client_and_endpoint(self):
        e = _engine()
        e.record_event("c1", "/api/users", LimitAction.ALLOWED)
        e.record_event("c1", "/api/data", LimitAction.BLOCKED)
        e.record_event("c2", "/api/users", LimitAction.THROTTLED)
        events = e.list_events(client_id="c1", endpoint="/api/data")
        assert len(events) == 1
        assert events[0].client_id == "c1"
        assert events[0].endpoint == "/api/data"

    def test_limit_returns_most_recent(self):
        e = _engine()
        for i in range(5):
            e.record_event(f"c{i}", "/api", LimitAction.ALLOWED)
        events = e.list_events(limit=2)
        assert len(events) == 2
        # last two should be returned (indices 3 and 4)
        assert events[0].client_id == "c3"
        assert events[1].client_id == "c4"


class TestEndpointAnalyticsEdgeCases:
    def test_single_client_multiple_actions(self):
        e = _engine()
        e.record_event("c1", "/api/v1", LimitAction.ALLOWED, request_count=10)
        e.record_event("c1", "/api/v1", LimitAction.BLOCKED, request_count=2)
        analytics = e.get_endpoint_analytics("/api/v1")
        assert analytics["unique_clients"] == 1
        assert analytics["total_events"] == 2
        assert analytics["requests_total"] == 12

    def test_multiple_clients_same_endpoint(self):
        e = _engine()
        e.record_event("c1", "/api/v1", LimitAction.ALLOWED)
        e.record_event("c2", "/api/v1", LimitAction.ALLOWED)
        e.record_event("c3", "/api/v1", LimitAction.WARNED)
        analytics = e.get_endpoint_analytics("/api/v1")
        assert analytics["unique_clients"] == 3


class TestCustomEngineConfig:
    def test_custom_max_events(self):
        e = _engine(max_events=10)
        s = e.get_stats()
        assert s["max_events"] == 10

    def test_custom_retention_hours(self):
        e = _engine(retention_hours=24)
        s = e.get_stats()
        assert s["retention_hours"] == 24
