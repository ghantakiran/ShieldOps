# Quick Start

Get ShieldOps running locally in under 5 minutes.

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (24+) with Docker Compose
- [Python](https://www.python.org/downloads/) 3.12+
- [Node.js](https://nodejs.org/) 20+

---

## Steps

### 1. Clone the repository

```bash
git clone https://github.com/ghantakiran/ShieldOps.git
cd ShieldOps
```

### 2. Start infrastructure services

This starts PostgreSQL, Redis, Kafka, and OPA in Docker containers:

```bash
make dev
```

Wait about 10 seconds for all services to become healthy.

### 3. Install dependencies and run migrations

```bash
make setup
```

This creates a Python virtual environment, installs all backend and frontend dependencies,
runs database migrations, and seeds demo data.

### 4. Configure your LLM provider (optional)

Copy the example environment file and add your API key:

```bash
cp .env.example .env
```

Edit `.env` and set:

```
SHIELDOPS_ANTHROPIC_API_KEY=sk-ant-your-key-here
```

!!! tip
    Without an API key, the platform runs in demo mode -- you can explore the dashboard
    and API, but agent workflows will return simulated results.

### 5. Start the application

```bash
make run
```

This starts both the API server (port 8000) and the frontend dev server (port 3000).

### 6. Open the dashboard

Navigate to **http://localhost:3000** in your browser.

### 7. Log in

Use the default demo credentials:

| Field    | Value                  |
|----------|------------------------|
| Email    | `admin@shieldops.dev`  |
| Password | `shieldops-admin`      |

!!! warning
    Change the default credentials before any non-local deployment. See the
    [Configuration](configuration.md) page for security settings.

### 8. Trigger a demo investigation

From the dashboard, navigate to **Investigations** and click **New Investigation**.
Or use the API directly:

```bash
# Get a JWT token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@shieldops.dev", "password": "shieldops-admin"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Trigger an investigation
curl -X POST http://localhost:8000/api/v1/investigations \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "alert_id": "demo-001",
    "alert_name": "High CPU on web-server-01",
    "severity": "critical",
    "source": "prometheus",
    "description": "CPU usage sustained above 95% for 15 minutes"
  }'
```

### 9. Watch the agent workflow

The investigation agent works through these stages in real-time:

1. **Context gathering** -- Pulls logs, metrics, and traces from connected sources
2. **Historical pattern check** -- Compares against known incident patterns
3. **Log analysis** -- Extracts error signals from log data
4. **Metric analysis** -- Identifies anomalies in time-series metrics
5. **Trace analysis** -- Follows distributed request paths (if needed)
6. **Correlation** -- Cross-references all findings
7. **Hypothesis generation** -- Produces ranked root cause hypotheses
8. **Action recommendation** -- Suggests remediation if confidence is high

Connect to `ws://localhost:8000/ws/investigations` for real-time WebSocket updates,
or watch the dashboard update automatically.

---

## Useful URLs

| URL | Description |
|-----|-------------|
| http://localhost:3000 | Dashboard |
| http://localhost:8000/health | API health check |
| http://localhost:8000/ready | Readiness check (DB, Redis, OPA) |
| http://localhost:8000/api/v1/docs | Swagger UI (interactive API docs) |
| http://localhost:8000/api/v1/openapi.json | OpenAPI spec |
| http://localhost:8000/metrics | Prometheus metrics |

---

## Available Make Commands

```
make dev              Start infrastructure (PostgreSQL, Redis, Kafka, OPA)
make setup            Install dependencies + run migrations + seed data
make run              Start API server + frontend dev server
make test             Run full test suite with coverage
make lint             Run ruff + mypy
make clean            Stop all services and remove volumes
```

Run `make help` for the full list.

---

## Stopping everything

```bash
make clean
```

This stops all Docker containers and removes volumes. Database data will be lost.

---

## Next steps

- [Installation](installation.md) -- Detailed setup options (Docker Compose, manual)
- [Configuration](configuration.md) -- All environment variables explained
- [Architecture Overview](../architecture/overview.md) -- Understand how the system fits together
- [API Reference](../api/authentication.md) -- Explore all API endpoints
