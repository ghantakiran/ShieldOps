"""Synchronous API client wrapping all ShieldOps backend endpoints."""

from typing import Any

import httpx

from shieldops.dashboard.config import API_BASE_URL, API_TIMEOUT


class ShieldOpsAPIClient:
    """HTTP client for the ShieldOps REST API.

    Uses sync httpx since Streamlit runs synchronously.
    All methods return dicts; errors are returned as ``{"error": msg}``.
    """

    def __init__(self, base_url: str = API_BASE_URL, timeout: int = API_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        try:
            resp = httpx.get(
                f"{self.base_url}{path}",
                params={k: v for k, v in (params or {}).items() if v is not None},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            return {"error": f"HTTP {exc.response.status_code}: {exc.response.text}"}
        except httpx.RequestError as exc:
            return {"error": f"Connection error: {exc}"}

    def _post(self, path: str, json: dict[str, Any] | None = None) -> dict:
        try:
            resp = httpx.post(
                f"{self.base_url}{path}",
                json=json or {},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            return {"error": f"HTTP {exc.response.status_code}: {exc.response.text}"}
        except httpx.RequestError as exc:
            return {"error": f"Connection error: {exc}"}

    # ------------------------------------------------------------------
    # Agents
    # ------------------------------------------------------------------

    def list_agents(
        self,
        environment: str | None = None,
        status: str | None = None,
    ) -> dict:
        return self._get("/agents", {"environment": environment, "status": status})

    def get_agent(self, agent_id: str) -> dict:
        return self._get(f"/agents/{agent_id}")

    def enable_agent(self, agent_id: str) -> dict:
        return self._post(f"/agents/{agent_id}/enable")

    def disable_agent(self, agent_id: str) -> dict:
        return self._post(f"/agents/{agent_id}/disable")

    # ------------------------------------------------------------------
    # Investigations
    # ------------------------------------------------------------------

    def list_investigations(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        return self._get(
            "/investigations",
            {"status": status, "limit": limit, "offset": offset},
        )

    def get_investigation(self, investigation_id: str) -> dict:
        return self._get(f"/investigations/{investigation_id}")

    def trigger_investigation(
        self,
        alert_id: str,
        alert_name: str,
        severity: str = "warning",
        source: str = "dashboard",
        description: str | None = None,
    ) -> dict:
        return self._post(
            "/investigations",
            {
                "alert_id": alert_id,
                "alert_name": alert_name,
                "severity": severity,
                "source": source,
                "description": description,
            },
        )

    # ------------------------------------------------------------------
    # Remediations
    # ------------------------------------------------------------------

    def list_remediations(
        self,
        environment: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        return self._get(
            "/remediations",
            {"environment": environment, "status": status, "limit": limit, "offset": offset},
        )

    def get_remediation(self, remediation_id: str) -> dict:
        return self._get(f"/remediations/{remediation_id}")

    def trigger_remediation(
        self,
        action_type: str,
        target_resource: str,
        environment: str = "production",
        risk_level: str = "medium",
        parameters: dict | None = None,
        description: str = "",
    ) -> dict:
        return self._post(
            "/remediations",
            {
                "action_type": action_type,
                "target_resource": target_resource,
                "environment": environment,
                "risk_level": risk_level,
                "parameters": parameters or {},
                "description": description,
            },
        )

    def approve_remediation(self, remediation_id: str, approver: str, reason: str = "") -> dict:
        return self._post(
            f"/remediations/{remediation_id}/approve",
            {"approver": approver, "reason": reason},
        )

    def deny_remediation(self, remediation_id: str, approver: str, reason: str = "") -> dict:
        return self._post(
            f"/remediations/{remediation_id}/deny",
            {"approver": approver, "reason": reason},
        )

    def rollback_remediation(self, remediation_id: str) -> dict:
        return self._post(f"/remediations/{remediation_id}/rollback")

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def get_mttr_trends(self, period: str = "30d", environment: str | None = None) -> dict:
        return self._get("/analytics/mttr", {"period": period, "environment": environment})

    def get_resolution_rate(self, period: str = "30d") -> dict:
        return self._get("/analytics/resolution-rate", {"period": period})

    def get_agent_accuracy(self, period: str = "30d") -> dict:
        return self._get("/analytics/agent-accuracy", {"period": period})

    def get_cost_savings_analytics(
        self,
        period: str = "30d",
        engineer_hourly_rate: float = 75.0,
    ) -> dict:
        return self._get(
            "/analytics/cost-savings",
            {"period": period, "engineer_hourly_rate": engineer_hourly_rate},
        )

    # ------------------------------------------------------------------
    # Security
    # ------------------------------------------------------------------

    def list_scans(
        self,
        scan_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        return self._get(
            "/security/scans",
            {"scan_type": scan_type, "limit": limit, "offset": offset},
        )

    def get_scan(self, scan_id: str) -> dict:
        return self._get(f"/security/scans/{scan_id}")

    def trigger_scan(
        self,
        environment: str = "production",
        scan_type: str = "full",
        target_resources: list[str] | None = None,
        compliance_frameworks: list[str] | None = None,
    ) -> dict:
        return self._post(
            "/security/scans",
            {
                "environment": environment,
                "scan_type": scan_type,
                "target_resources": target_resources or [],
                "compliance_frameworks": compliance_frameworks or [],
            },
        )

    def get_security_posture(self) -> dict:
        return self._get("/security/posture")

    def list_cves(self, severity: str | None = None, limit: int = 50) -> dict:
        return self._get("/security/cves", {"severity": severity, "limit": limit})

    def get_compliance(self, framework: str) -> dict:
        return self._get(f"/security/compliance/{framework}")

    # ------------------------------------------------------------------
    # Cost Intelligence
    # ------------------------------------------------------------------

    def list_cost_analyses(
        self,
        analysis_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        return self._get(
            "/cost/analyses",
            {"analysis_type": analysis_type, "limit": limit, "offset": offset},
        )

    def get_cost_analysis(self, analysis_id: str) -> dict:
        return self._get(f"/cost/analyses/{analysis_id}")

    def trigger_cost_analysis(
        self,
        environment: str = "production",
        analysis_type: str = "full",
        target_services: list[str] | None = None,
        period: str = "30d",
    ) -> dict:
        return self._post(
            "/cost/analyses",
            {
                "environment": environment,
                "analysis_type": analysis_type,
                "target_services": target_services or [],
                "period": period,
            },
        )

    def list_anomalies(self, severity: str | None = None, limit: int = 50) -> dict:
        return self._get("/cost/anomalies", {"severity": severity, "limit": limit})

    def list_optimizations(self, category: str | None = None, limit: int = 50) -> dict:
        return self._get("/cost/optimizations", {"category": category, "limit": limit})

    def get_savings_summary(self) -> dict:
        return self._get("/cost/savings")

    # ------------------------------------------------------------------
    # Learning
    # ------------------------------------------------------------------

    def list_learning_cycles(
        self,
        learning_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        return self._get(
            "/learning/cycles",
            {"learning_type": learning_type, "limit": limit, "offset": offset},
        )

    def get_learning_cycle(self, learning_id: str) -> dict:
        return self._get(f"/learning/cycles/{learning_id}")

    def trigger_learning_cycle(
        self,
        learning_type: str = "full",
        period: str = "30d",
    ) -> dict:
        return self._post(
            "/learning/cycles",
            {"learning_type": learning_type, "period": period},
        )

    def list_patterns(self, alert_type: str | None = None, limit: int = 50) -> dict:
        return self._get("/learning/patterns", {"alert_type": alert_type, "limit": limit})

    def list_playbook_updates(self, update_type: str | None = None, limit: int = 50) -> dict:
        return self._get(
            "/learning/playbook-updates",
            {"update_type": update_type, "limit": limit},
        )

    def list_threshold_adjustments(self) -> dict:
        return self._get("/learning/threshold-adjustments")

    # ------------------------------------------------------------------
    # Supervisor
    # ------------------------------------------------------------------

    def list_sessions(
        self,
        event_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        return self._get(
            "/supervisor/sessions",
            {"event_type": event_type, "limit": limit, "offset": offset},
        )

    def get_session(self, session_id: str) -> dict:
        return self._get(f"/supervisor/sessions/{session_id}")

    def get_session_tasks(self, session_id: str) -> dict:
        return self._get(f"/supervisor/sessions/{session_id}/tasks")

    def get_session_escalations(self, session_id: str) -> dict:
        return self._get(f"/supervisor/sessions/{session_id}/escalations")

    def submit_event(
        self,
        event_type: str,
        severity: str = "medium",
        source: str = "dashboard",
        resource_id: str | None = None,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        return self._post(
            "/supervisor/events",
            {
                "type": event_type,
                "severity": severity,
                "source": source,
                "resource_id": resource_id,
                "description": description,
                "metadata": metadata or {},
            },
        )
