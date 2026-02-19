# Run Agent Skill

Test-run a ShieldOps agent workflow locally with mock data.

## Usage
`/run-agent <agent-type> [--environment <env>] [--mock]`

Agent types: `investigation`, `remediation`, `security`, `cost`, `learning`, `supervisor`

## Process

1. **Check agent runner exists**: Look in `src/shieldops/agents/{type}/runner.py`
2. **Create a test script** that:
   - Instantiates the runner with mock dependencies (no real DB/cloud needed)
   - Uses mock connectors, mock policy engine, mock repository
   - Provides realistic test input (alert context, remediation action, etc.)
   - Runs the agent workflow end-to-end
   - Prints results in structured format
3. **Run and validate**:
   - Execute the script with `python3 -m pytest` or direct invocation
   - Verify the agent graph executes all nodes
   - Check reasoning chain is populated
   - Validate output model is well-formed

## Agent Test Inputs

### Investigation
```python
alert_context = {"alert_id": "test-001", "alert_name": "High CPU", "severity": "warning", "environment": "staging", "resource_id": "web-server-1"}
```

### Remediation
```python
action = {"action_type": "restart_instance", "target_resource": "web-1", "environment": "staging", "risk_level": "low"}
```

### Security
```python
scan_config = {"scan_type": "full", "environment": "production", "targets": ["web-1"]}
```

### Learning
```python
learn_params = {"learning_type": "full", "period": "7d"}
```

## Tips
- Set `ANTHROPIC_API_KEY` if you want real LLM calls (otherwise agents use mock/fallback)
- Use `--mock` flag to force mock mode for all external dependencies
