# Build Agent Skill

Build a new ShieldOps agent or extend an existing one.

## Usage
`/build-agent <agent-type> [--playbook <name>] [--connector <provider>]`

## Process

1. **Read the PRD**: Check `docs/prd/` for relevant requirements
2. **Understand the agent architecture**: Read `docs/architecture/agent-design.md`
3. **Check existing agents**: Review `src/shieldops/agents/` for patterns to follow
4. **Implement the agent**:
   - Create agent module in `src/shieldops/agents/{type}/`
   - Define LangGraph state and nodes in `graph.py`
   - Implement tool functions in `tools.py`
   - Add Pydantic models in `models.py`
   - Wire OPA policy checks in `policy.py`
5. **Add playbooks**: Create YAML playbook in `playbooks/`
6. **Write tests**: Unit tests + agent simulation tests
7. **Update orchestration**: Register agent with supervisor in `src/shieldops/orchestration/`

## Agent Template Structure
```
src/shieldops/agents/{type}/
  __init__.py
  graph.py      # LangGraph workflow definition
  nodes.py      # Node implementations (investigate, act, validate)
  tools.py      # Tool functions (API calls, infra operations)
  models.py     # Pydantic state/input/output models
  policy.py     # OPA policy integration
  prompts.py    # LLM prompt templates
```

## Safety Requirements
- ALL infrastructure-modifying actions MUST pass OPA policy evaluation
- Implement rollback capability for every remediation action
- Log all decisions with full reasoning chain to audit trail
- Set confidence thresholds: autonomous action >0.85, human approval 0.5-0.85, escalate <0.5
