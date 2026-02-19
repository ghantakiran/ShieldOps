# Add Connector Skill

Scaffold a new infrastructure connector following the `InfraConnector` protocol.

## Usage
`/add-connector <provider-name>`

## Process

1. **Read the base protocol**: Review `src/shieldops/connectors/base.py` for the `InfraConnector` ABC
2. **Study existing connectors**: Review `src/shieldops/connectors/aws/connector.py` for the reference pattern
3. **Create the connector module**:
   - Create directory: `src/shieldops/connectors/{provider}/`
   - Create `__init__.py` with connector export
   - Create `connector.py` implementing all 7 `InfraConnector` methods:
     - `get_health(resource_id)` — Check resource health status
     - `list_resources(resource_type, environment, filters)` — List resources with filtering
     - `get_events(resource_id, time_range)` — Query audit/activity events
     - `execute_action(action)` — Execute remediation action
     - `create_snapshot(resource_id)` — Snapshot current state for rollback
     - `rollback(snapshot_id)` — Restore from snapshot
     - `validate_health(resource_id, timeout)` — Post-action health validation
4. **Register in factory**: Add to `src/shieldops/connectors/factory.py`
5. **Add settings**: Add provider config to `src/shieldops/config/settings.py`
6. **Write tests**: Unit tests in `tests/unit/test_{provider}_connector.py`
7. **Create fake connector**: Integration test fake in `tests/integration/fakes/{provider}_fake.py`

## Conventions
- Use lazy client initialization (don't create SDK clients in `__init__`)
- All methods are async
- Use `asyncio.get_event_loop().run_in_executor()` for sync SDK calls
- Set `provider` class attribute to the provider string
- Use structlog for all logging
- Handle ImportError gracefully for optional SDK dependencies
