# Code Style

ShieldOps follows consistent coding conventions enforced by automated tooling.

---

## Python

### Linting and Formatting

ShieldOps uses [Ruff](https://docs.astral.sh/ruff/) for both linting and formatting:

```bash
# Check for lint errors
ruff check src/ tests/

# Auto-fix lint errors
ruff check --fix src/ tests/

# Format code
ruff format src/ tests/
```

Configuration is in `pyproject.toml`:

- **Line length:** 100 characters
- **Target Python:** 3.12+
- **Ruff rules:** Default rules plus import sorting

### Type Checking

[mypy](https://mypy-lang.org/) is used for static type analysis:

```bash
mypy src/shieldops/
```

**Requirements:**

- Type hints are required on all public functions
- Use `from __future__ import annotations` for forward references
- Use `TYPE_CHECKING` guard for import-only type dependencies

### Async-First

All I/O operations must use `async/await`:

```python
# Correct
async def get_health(self, resource_id: str) -> HealthStatus:
    result = await self._client.get(f"/api/resources/{resource_id}")
    return HealthStatus(**result.json())

# Incorrect - blocks the event loop
def get_health(self, resource_id: str) -> HealthStatus:
    result = requests.get(f"/api/resources/{resource_id}")
    return HealthStatus(**result.json())
```

### Pydantic v2 Models

All data structures use Pydantic v2 models:

```python
from pydantic import BaseModel, Field

class AlertContext(BaseModel):
    alert_id: str
    alert_name: str
    severity: str = "warning"
    labels: dict[str, str] = Field(default_factory=dict)
```

### Structured Logging

Use `structlog` for all logging:

```python
import structlog

logger = structlog.get_logger()

logger.info("investigation_started", alert_id=alert.alert_id, severity=alert.severity)
logger.error("policy_evaluation_failed", error=str(e), action=action.action_type)
```

### Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Modules | `snake_case` | `investigation_runner.py` |
| Classes | `PascalCase` | `InvestigationRunner` |
| Functions | `snake_case` | `gather_context()` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRIES` |
| Private members | `_prefix` | `_runner`, `_client` |

---

## TypeScript / React

### Frontend conventions

The dashboard uses React + TypeScript + Tailwind CSS:

- **Linting:** ESLint with the project config
- **Formatting:** Prettier (via ESLint integration)
- **Components:** Functional components with hooks
- **State:** React Query for server state, React context for UI state

```bash
# Lint frontend
make lint-frontend

# Or directly
cd dashboard-ui && npm run lint
```

---

## Git Conventions

### Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add PagerDuty notification channel
fix: handle null OPA response during circuit break
chore: upgrade Pydantic to 2.6
docs: add Helm chart configuration reference
refactor: extract policy evaluation into separate module
test: add integration tests for remediation rollback
```

### Branch Naming

```
feat/add-pagerduty-notifications
fix/opa-circuit-breaker-null-response
chore/upgrade-pydantic
docs/helm-chart-reference
```

---

## Code Organization

### Agent modules

Each agent lives in `src/shieldops/agents/{type}/` with a consistent structure:

```
agents/{type}/
  __init__.py
  graph.py       # LangGraph StateGraph definition
  nodes.py       # Async node implementations
  models.py      # Pydantic state models
  prompts.py     # LLM prompts
  tools.py       # Agent tools (connector wrappers)
  runner.py      # Public runner class
```

### API routes

Each API resource has its own route module in `src/shieldops/api/routes/`:

```python
# Standard pattern for route modules
router = APIRouter()
_runner: SomeRunner | None = None

def set_runner(runner: SomeRunner) -> None:
    global _runner
    _runner = runner

@router.get("/resource")
async def list_resource(
    _user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    ...
```

### Dependency injection

Runners and services are wired in `src/shieldops/api/app.py` during the `lifespan`
startup phase. Route modules expose `set_runner()` / `set_repository()` functions
for dependency injection.
