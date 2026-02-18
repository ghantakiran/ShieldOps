"""Unit tests for the ShieldOps dashboard — API client and components."""

from unittest.mock import MagicMock, patch

import httpx

from shieldops.dashboard.api_client import ShieldOpsAPIClient
from shieldops.dashboard.components import (
    render_risk_badge,
    render_severity_badge,
    render_status_badge,
)
from shieldops.dashboard.config import (
    RISK_COLORS,
    SEVERITY_COLORS,
    STATUS_COLORS,
    confidence_color,
)

# =====================================================================
# Config tests
# =====================================================================


class TestConfig:
    def test_confidence_color_high(self):
        assert confidence_color(0.9) == "#10B981"
        assert confidence_color(0.8) == "#10B981"

    def test_confidence_color_medium(self):
        assert confidence_color(0.6) == "#F59E0B"
        assert confidence_color(0.5) == "#F59E0B"

    def test_confidence_color_low(self):
        assert confidence_color(0.3) == "#EF4444"
        assert confidence_color(0.0) == "#EF4444"

    def test_status_colors_complete(self):
        required = ["idle", "investigating", "error", "success", "failed", "pending"]
        for key in required:
            assert key in STATUS_COLORS

    def test_risk_colors_complete(self):
        for level in ["low", "medium", "high", "critical"]:
            assert level in RISK_COLORS

    def test_severity_colors_complete(self):
        for level in ["info", "low", "warning", "high", "critical"]:
            assert level in SEVERITY_COLORS


# =====================================================================
# Component tests
# =====================================================================


class TestBadges:
    def test_status_badge_contains_color(self):
        html = render_status_badge("success")
        assert STATUS_COLORS["success"] in html
        assert "Success" in html

    def test_status_badge_unknown_status(self):
        html = render_status_badge("nonexistent")
        assert STATUS_COLORS["unknown"] in html

    def test_status_badge_replaces_underscores(self):
        html = render_status_badge("waiting_approval")
        assert "Waiting Approval" in html

    def test_risk_badge_colors(self):
        for level, color in RISK_COLORS.items():
            html = render_risk_badge(level)
            assert color in html
            assert level.upper() in html

    def test_severity_badge_colors(self):
        for level, color in SEVERITY_COLORS.items():
            html = render_severity_badge(level)
            assert color in html
            assert level.upper() in html


# =====================================================================
# API Client tests
# =====================================================================


def _mock_response(json_data: dict, status_code: int = 200) -> httpx.Response:
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    resp.raise_for_status.return_value = None
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message="error",
            request=MagicMock(),
            response=resp,
        )
    return resp


class TestAPIClientAgents:
    def setup_method(self):
        self.client = ShieldOpsAPIClient(base_url="http://test:8000/api/v1")

    @patch("httpx.get")
    def test_list_agents(self, mock_get):
        mock_get.return_value = _mock_response({"agents": [], "total": 0})
        result = self.client.list_agents()
        assert result == {"agents": [], "total": 0}
        mock_get.assert_called_once()

    @patch("httpx.get")
    def test_list_agents_with_filters(self, mock_get):
        mock_get.return_value = _mock_response({"agents": [], "total": 0})
        self.client.list_agents(environment="production", status="idle")
        args, kwargs = mock_get.call_args
        assert kwargs["params"]["environment"] == "production"
        assert kwargs["params"]["status"] == "idle"

    @patch("httpx.get")
    def test_get_agent(self, mock_get):
        mock_get.return_value = _mock_response({"agent_id": "a1", "status": "idle"})
        result = self.client.get_agent("a1")
        assert result["agent_id"] == "a1"

    @patch("httpx.post")
    def test_enable_agent(self, mock_post):
        mock_post.return_value = _mock_response({"agent_id": "a1", "action": "enabled"})
        result = self.client.enable_agent("a1")
        assert result["action"] == "enabled"

    @patch("httpx.post")
    def test_disable_agent(self, mock_post):
        mock_post.return_value = _mock_response({"agent_id": "a1", "action": "disabled"})
        result = self.client.disable_agent("a1")
        assert result["action"] == "disabled"


class TestAPIClientInvestigations:
    def setup_method(self):
        self.client = ShieldOpsAPIClient(base_url="http://test:8000/api/v1")

    @patch("httpx.get")
    def test_list_investigations(self, mock_get):
        mock_get.return_value = _mock_response(
            {
                "investigations": [{"investigation_id": "inv-1"}],
                "total": 1,
            }
        )
        result = self.client.list_investigations()
        assert result["total"] == 1

    @patch("httpx.get")
    def test_get_investigation(self, mock_get):
        mock_get.return_value = _mock_response({"investigation_id": "inv-1", "status": "complete"})
        result = self.client.get_investigation("inv-1")
        assert result["status"] == "complete"

    @patch("httpx.post")
    def test_trigger_investigation(self, mock_post):
        mock_post.return_value = _mock_response({"status": "accepted", "alert_id": "a1"})
        result = self.client.trigger_investigation(
            alert_id="a1",
            alert_name="HighCPU",
            severity="critical",
        )
        assert result["status"] == "accepted"
        payload = mock_post.call_args[1]["json"]
        assert payload["alert_id"] == "a1"
        assert payload["severity"] == "critical"


class TestAPIClientRemediations:
    def setup_method(self):
        self.client = ShieldOpsAPIClient(base_url="http://test:8000/api/v1")

    @patch("httpx.get")
    def test_list_remediations(self, mock_get):
        mock_get.return_value = _mock_response({"remediations": [], "total": 0})
        result = self.client.list_remediations()
        assert result["total"] == 0

    @patch("httpx.get")
    def test_get_remediation(self, mock_get):
        mock_get.return_value = _mock_response({"remediation_id": "rem-1"})
        result = self.client.get_remediation("rem-1")
        assert result["remediation_id"] == "rem-1"

    @patch("httpx.post")
    def test_trigger_remediation(self, mock_post):
        mock_post.return_value = _mock_response({"status": "accepted"})
        result = self.client.trigger_remediation(
            action_type="restart_pod",
            target_resource="my-pod",
            risk_level="low",
        )
        assert result["status"] == "accepted"

    @patch("httpx.post")
    def test_approve_remediation(self, mock_post):
        mock_post.return_value = _mock_response({"action": "approved"})
        result = self.client.approve_remediation("rem-1", approver="admin")
        assert result["action"] == "approved"

    @patch("httpx.post")
    def test_deny_remediation(self, mock_post):
        mock_post.return_value = _mock_response({"action": "denied"})
        result = self.client.deny_remediation("rem-1", approver="admin", reason="too risky")
        assert result["action"] == "denied"

    @patch("httpx.post")
    def test_rollback_remediation(self, mock_post):
        mock_post.return_value = _mock_response({"action": "rollback_initiated"})
        result = self.client.rollback_remediation("rem-1")
        assert result["action"] == "rollback_initiated"


class TestAPIClientAnalytics:
    def setup_method(self):
        self.client = ShieldOpsAPIClient(base_url="http://test:8000/api/v1")

    @patch("httpx.get")
    def test_get_mttr_trends(self, mock_get):
        mock_get.return_value = _mock_response({"current_mttr_minutes": 15})
        result = self.client.get_mttr_trends(period="7d")
        assert result["current_mttr_minutes"] == 15

    @patch("httpx.get")
    def test_get_resolution_rate(self, mock_get):
        mock_get.return_value = _mock_response({"automated_rate": 0.8})
        result = self.client.get_resolution_rate()
        assert result["automated_rate"] == 0.8

    @patch("httpx.get")
    def test_get_agent_accuracy(self, mock_get):
        mock_get.return_value = _mock_response({"accuracy": 0.92})
        result = self.client.get_agent_accuracy()
        assert result["accuracy"] == 0.92

    @patch("httpx.get")
    def test_get_cost_savings_analytics(self, mock_get):
        mock_get.return_value = _mock_response({"hours_saved": 100})
        result = self.client.get_cost_savings_analytics(period="30d", engineer_hourly_rate=100.0)
        assert result["hours_saved"] == 100


class TestAPIClientSecurity:
    def setup_method(self):
        self.client = ShieldOpsAPIClient(base_url="http://test:8000/api/v1")

    @patch("httpx.get")
    def test_get_security_posture(self, mock_get):
        mock_get.return_value = _mock_response({"overall_score": 85})
        result = self.client.get_security_posture()
        assert result["overall_score"] == 85

    @patch("httpx.get")
    def test_list_cves(self, mock_get):
        mock_get.return_value = _mock_response({"cves": [], "total": 0})
        result = self.client.list_cves(severity="critical")
        assert result["total"] == 0

    @patch("httpx.get")
    def test_get_compliance(self, mock_get):
        mock_get.return_value = _mock_response({"framework": "SOC2", "score": 0.95})
        result = self.client.get_compliance("SOC2")
        assert result["score"] == 0.95

    @patch("httpx.post")
    def test_trigger_scan(self, mock_post):
        mock_post.return_value = _mock_response({"status": "accepted"})
        result = self.client.trigger_scan(scan_type="cve_only")
        assert result["status"] == "accepted"

    @patch("httpx.get")
    def test_list_scans(self, mock_get):
        mock_get.return_value = _mock_response({"scans": [], "total": 0})
        result = self.client.list_scans()
        assert result["total"] == 0


class TestAPIClientCost:
    def setup_method(self):
        self.client = ShieldOpsAPIClient(base_url="http://test:8000/api/v1")

    @patch("httpx.get")
    def test_get_savings_summary(self, mock_get):
        mock_get.return_value = _mock_response({"total_monthly_spend": 50000})
        result = self.client.get_savings_summary()
        assert result["total_monthly_spend"] == 50000

    @patch("httpx.get")
    def test_list_anomalies(self, mock_get):
        mock_get.return_value = _mock_response({"anomalies": [], "total": 0})
        result = self.client.list_anomalies()
        assert result["total"] == 0

    @patch("httpx.get")
    def test_list_optimizations(self, mock_get):
        mock_get.return_value = _mock_response({"optimizations": [], "total": 0})
        result = self.client.list_optimizations()
        assert result["total"] == 0

    @patch("httpx.post")
    def test_trigger_cost_analysis(self, mock_post):
        mock_post.return_value = _mock_response({"status": "accepted"})
        result = self.client.trigger_cost_analysis(analysis_type="anomaly_only")
        assert result["status"] == "accepted"


class TestAPIClientLearning:
    def setup_method(self):
        self.client = ShieldOpsAPIClient(base_url="http://test:8000/api/v1")

    @patch("httpx.get")
    def test_list_patterns(self, mock_get):
        mock_get.return_value = _mock_response({"patterns": [], "total": 0})
        result = self.client.list_patterns()
        assert result["total"] == 0

    @patch("httpx.get")
    def test_list_playbook_updates(self, mock_get):
        mock_get.return_value = _mock_response({"playbook_updates": [], "total": 0})
        result = self.client.list_playbook_updates()
        assert result["total"] == 0

    @patch("httpx.get")
    def test_list_threshold_adjustments(self, mock_get):
        mock_get.return_value = _mock_response({"threshold_adjustments": [], "total": 0})
        result = self.client.list_threshold_adjustments()
        assert result["total"] == 0

    @patch("httpx.post")
    def test_trigger_learning_cycle(self, mock_post):
        mock_post.return_value = _mock_response({"status": "accepted"})
        result = self.client.trigger_learning_cycle(learning_type="pattern_only")
        assert result["status"] == "accepted"


class TestAPIClientSupervisor:
    def setup_method(self):
        self.client = ShieldOpsAPIClient(base_url="http://test:8000/api/v1")

    @patch("httpx.get")
    def test_list_sessions(self, mock_get):
        mock_get.return_value = _mock_response({"sessions": [], "total": 0})
        result = self.client.list_sessions()
        assert result["total"] == 0

    @patch("httpx.get")
    def test_get_session(self, mock_get):
        mock_get.return_value = _mock_response({"session_id": "s1"})
        result = self.client.get_session("s1")
        assert result["session_id"] == "s1"

    @patch("httpx.get")
    def test_get_session_tasks(self, mock_get):
        mock_get.return_value = _mock_response({"tasks": [], "total": 0})
        result = self.client.get_session_tasks("s1")
        assert result["total"] == 0

    @patch("httpx.get")
    def test_get_session_escalations(self, mock_get):
        mock_get.return_value = _mock_response({"escalations": [], "total": 0})
        result = self.client.get_session_escalations("s1")
        assert result["total"] == 0

    @patch("httpx.post")
    def test_submit_event(self, mock_post):
        mock_post.return_value = _mock_response({"status": "accepted"})
        result = self.client.submit_event(event_type="alert", severity="high")
        assert result["status"] == "accepted"


class TestAPIClientErrorHandling:
    def setup_method(self):
        self.client = ShieldOpsAPIClient(base_url="http://test:8000/api/v1")

    @patch("httpx.get")
    def test_http_error_returns_error_dict(self, mock_get):
        mock_get.return_value = _mock_response({"detail": "Not Found"}, status_code=404)
        result = self.client.list_agents()
        assert "error" in result
        assert "404" in result["error"]

    @patch("httpx.get")
    def test_connection_error_returns_error_dict(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("Connection refused")
        result = self.client.list_agents()
        assert "error" in result
        assert "Connection" in result["error"]

    @patch("httpx.post")
    def test_post_connection_error(self, mock_post):
        mock_post.side_effect = httpx.ConnectError("Connection refused")
        result = self.client.trigger_investigation(alert_id="a1", alert_name="test")
        assert "error" in result

    @patch("httpx.get")
    def test_timeout_error(self, mock_get):
        mock_get.side_effect = httpx.ReadTimeout("Timeout")
        result = self.client.list_agents()
        assert "error" in result

    @patch("httpx.get")
    def test_none_params_filtered(self, mock_get):
        mock_get.return_value = _mock_response({"agents": [], "total": 0})
        self.client.list_agents(environment=None, status=None)
        _, kwargs = mock_get.call_args
        # None values should be filtered out
        for v in kwargs["params"].values():
            assert v is not None
