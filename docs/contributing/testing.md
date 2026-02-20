# Testing

ShieldOps uses [pytest](https://docs.pytest.org/) with `pytest-asyncio` for async
test support. The minimum coverage threshold is **80%** on all new code.

---

## Running Tests

```bash
# Full test suite with coverage
make test

# Unit tests only
make test-unit

# Integration tests (requires infrastructure)
make test-integration

# Agent simulation tests
make test-agents

# Run with verbose output
.venv/bin/pytest tests/ -v --cov=src/shieldops --cov-report=term-missing
```

---

## Test Structure

Tests mirror the source structure:

```
tests/
  unit/
    agents/
      investigation/
        test_graph.py
        test_nodes.py
        test_runner.py
      remediation/
        test_graph.py
        test_nodes.py
      security/
        ...
    connectors/
      test_base.py
      test_kubernetes.py
      test_aws.py
    policy/
      test_opa_client.py
      test_approval_workflow.py
      test_rollback_manager.py
    api/
      test_auth.py
      test_investigations.py
      test_remediations.py
  integration/
    test_database.py
    test_redis.py
    test_kafka.py
  agents/
    test_investigation_replay.py
    test_remediation_replay.py
```

---

## Writing Tests

### Unit test pattern

```python
import pytest
from unittest.mock import AsyncMock, patch

from shieldops.agents.investigation.runner import InvestigationRunner
from shieldops.models.base import AlertContext


@pytest.fixture
def mock_runner():
    runner = InvestigationRunner()
    runner._connector_router = AsyncMock()
    runner._log_sources = [AsyncMock()]
    return runner


@pytest.mark.asyncio
async def test_investigate_returns_hypotheses(mock_runner):
    alert = AlertContext(
        alert_id="test-001",
        alert_name="HighCPU",
        severity="critical",
        source="test",
    )
    result = await mock_runner.investigate(alert)

    assert result.status in ("complete", "error")
    assert isinstance(result.hypotheses, list)
```

### Mocking guidelines

- **Patch where it's used**, not where it's defined:

    ```python
    # Correct - patch in the module that imports it
    @patch("shieldops.agents.investigation.nodes.llm_structured")

    # Incorrect - patching the source module
    @patch("shieldops.utils.llm.llm_structured")
    ```

- Use `AsyncMock` for async functions
- Use mock connectors instead of real cloud resources for unit tests

### Testing async code

```python
import pytest

@pytest.mark.asyncio
async def test_policy_evaluation():
    engine = PolicyEngine(opa_url="http://fake:8181")
    # ... test async methods
```

### Testing API endpoints

```python
from httpx import ASGITransport, AsyncClient
from shieldops.api.app import create_app

@pytest.fixture
def app():
    return create_app()

@pytest.mark.asyncio
async def test_health_check(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
```

---

## Test Categories

### Unit tests (`tests/unit/`)

- Test individual functions and classes in isolation
- Mock all external dependencies
- Fast, no infrastructure required
- Run with `make test-unit`

### Integration tests (`tests/integration/`)

- Test against real PostgreSQL, Redis, and OPA instances
- Require `make dev` to be running
- Marked with `@pytest.mark.integration`
- Run with `make test-integration`

### Agent simulation tests (`tests/agents/`)

- Replay historical incident data through agent workflows
- Verify that agents produce reasonable results
- Run with `make test-agents`

---

## Coverage

The CI pipeline enforces 80% minimum coverage:

```bash
pytest tests/ \
  --cov=src/shieldops \
  --cov-report=term-missing \
  --cov-fail-under=80
```

!!! tip
    Focus coverage on critical paths: policy evaluation, approval workflow,
    rollback logic, and graph conditional edges. High coverage on these paths
    matters more than 100% coverage on boilerplate.

---

## CI Pipeline

The CI workflow runs five parallel jobs on every push/PR:

| Job | What it checks |
|-----|---------------|
| lint | `ruff check` and `ruff format --check` |
| typecheck | `mypy src/shieldops/` |
| test | Full test suite with PostgreSQL and Redis containers |
| terraform | `terraform fmt`, `init`, `validate` for all providers |
| security | `bandit` static analysis + `pip-audit` dependency scan |
