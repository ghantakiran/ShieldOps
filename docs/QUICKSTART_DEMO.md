# ShieldOps Quickstart Demo

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

Without an API key, the platform runs in demo mode -- you can explore the dashboard and API,
but agent workflows will return simulated results.

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

### 8. Trigger a demo investigation

From the dashboard:

1. Navigate to **Investigations** in the sidebar
2. Click **New Investigation**
3. Select an environment (e.g., `development`)
4. Enter a sample alert:
   ```
   High CPU usage detected on web-server-01, sustained above 95% for 15 minutes
   ```
5. Click **Start Investigation**

Or via the API:

```bash
# First, get a JWT token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@shieldops.dev", "password": "shieldops-admin"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Trigger an investigation
curl -X POST http://localhost:8000/api/v1/investigations/ \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "High CPU on web-server-01",
    "environment": "development",
    "alert_data": {
      "source": "prometheus",
      "severity": "critical",
      "metric": "cpu_usage_percent",
      "value": 97.3,
      "threshold": 90,
      "host": "web-server-01"
    }
  }'
```

### 9. Watch the agent workflow

The investigation agent works through these stages in real-time:

1. **Alert parsing** -- Extracts structured data from the alert
2. **Context gathering** -- Pulls logs, metrics, and traces from connected observability sources
3. **Root cause analysis** -- Uses the LLM to correlate signals and identify the root cause
4. **Recommendation** -- Suggests remediation actions with confidence scores
5. **Report** -- Generates a structured investigation report

You can watch progress live via WebSocket. Connect to `ws://localhost:8000/ws/investigations`
to receive real-time status updates, or watch the dashboard update automatically.

---

## Useful URLs

| URL                                        | Description             |
|--------------------------------------------|-------------------------|
| http://localhost:3000                       | Dashboard               |
| http://localhost:8000/health               | API health check        |
| http://localhost:8000/ready                | Readiness check         |
| http://localhost:8000/api/v1/docs          | Swagger UI (API docs)   |
| http://localhost:8000/api/v1/openapi.json  | OpenAPI spec            |
| http://localhost:8000/metrics              | Prometheus metrics      |

---

## Available Make Commands

Run `make help` to see all available commands:

```
make dev              Start infrastructure (PostgreSQL, Redis, Kafka, OPA)
make setup            Install dependencies + run migrations + seed data
make run              Start API server + frontend dev server
make test             Run full test suite with coverage
make lint             Run ruff + mypy
make clean            Stop all services and remove volumes
```

---

## Stopping everything

```bash
make clean
```

This stops all Docker containers and removes volumes (database data will be lost).

---

## Next steps

- Read the full [Deployment Guide](DEPLOYMENT.md) for production deployments
- Explore the [API docs](http://localhost:8000/api/v1/docs) to understand all endpoints
- Check out `playbooks/` for YAML remediation playbook definitions
- Review `playbooks/policies/` for OPA policy rules that gate agent actions
