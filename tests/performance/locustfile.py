"""Locust load test scenarios for the ShieldOps API.

Usage:
    locust -f tests/performance/locustfile.py --headless -u 50 -r 10 -t 60s \
        --host http://localhost:8000
"""

import os

from locust import HttpUser, between, task


class ShieldOpsUser(HttpUser):
    """Simulates a typical ShieldOps dashboard user session."""

    wait_time = between(0.5, 2.0)
    host = os.getenv("LOCUST_HOST", "http://localhost:8000")

    def on_start(self) -> None:
        """Login and store JWT token for authenticated requests."""
        email = os.getenv("TEST_USER_EMAIL", "admin@shieldops.dev")
        password = os.getenv("TEST_USER_PASSWORD", "shieldops-admin")

        resp = self.client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        if resp.status_code == 200:
            self.token = resp.json().get("access_token", "")
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            # Fall back to unauthenticated if login fails
            self.token = ""

    @task(5)
    def health_check(self) -> None:
        """High-frequency health check."""
        self.client.get("/health")

    @task(3)
    def fleet_overview(self) -> None:
        """Dashboard fleet overview: summary + agent list."""
        self.client.get("/api/v1/analytics/summary")
        self.client.get("/api/v1/agents/")

    @task(2)
    def list_investigations(self) -> None:
        """Browse investigations list."""
        self.client.get("/api/v1/investigations/")

    @task(2)
    def list_remediations(self) -> None:
        """Browse remediations list."""
        self.client.get("/api/v1/remediations/")

    @task(1)
    def trigger_investigation(self) -> None:
        """Trigger a new investigation (write path)."""
        self.client.post(
            "/api/v1/investigations/",
            json={
                "alert_id": "load-test-alert",
                "alert_name": "HighCPU",
                "severity": "warning",
                "source": "locust",
                "resource_id": "load-test-node",
            },
        )

    @task(1)
    def security_scans(self) -> None:
        """Browse security scans."""
        self.client.get("/api/v1/security/scans")

    @task(1)
    def cost_summary(self) -> None:
        """Fetch cost summary."""
        self.client.get("/api/v1/cost/summary")

    @task(1)
    def learning_cycles(self) -> None:
        """Fetch learning cycles."""
        self.client.get("/api/v1/learning/cycles")
