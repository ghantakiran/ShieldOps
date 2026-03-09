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
7. **Update orchestration**: Register agent with supervisor in `src/shieldops/agents/supervisor/`

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
  runner.py     # Agent runner — entry point for execution, lifecycle management
```

## Enterprise Agent Patterns

### ChatOps Agent
- Integrates with Slack/Microsoft Teams via webhook endpoints
- Processes natural language commands from chat channels
- Routes requests to appropriate specialist agents
- Returns structured responses with approval buttons/actions
- Template: `src/shieldops/agents/chatops/`

### Enterprise Integration Agent
- Manages bidirectional integrations with enterprise tools (ITSM, SIEM, CMDB)
- Handles webhook ingestion and outbound event publishing
- Implements retry logic, circuit breakers, and dead-letter queues
- Template: `src/shieldops/agents/enterprise_integration/`

### Automation Orchestrator Agent
- Defines automation rules with trigger conditions and policy gates
- Chains multiple agent actions into automated workflows
- Enforces approval workflows for high-impact automations
- Template: `src/shieldops/agents/automation_orchestrator/`

## API Routes & Dashboard Pages
- Each agent MUST have corresponding API routes in `src/shieldops/api/routes/`
  - Example: `src/shieldops/api/routes/{agent_type}.py`
  - Routes should expose: status, trigger, history, configuration endpoints
- Each agent SHOULD have a dashboard page in `dashboard-ui/src/pages/`
  - Example: `dashboard-ui/src/pages/{AgentType}Page.tsx`
  - Page should display: agent status, recent activity, configuration, metrics

## Webhook & Approval Integration
- Agents that modify infrastructure MUST support webhook notifications (Slack, Teams, PagerDuty)
- High-impact actions require approval workflows:
  - Define approval policies in `playbooks/policies/`
  - Wire approval gates via `src/shieldops/policy/approval_workflow.py`
  - Support async approval via webhook callbacks
- Register webhook endpoints in `src/shieldops/api/routes/webhooks.py`

## Safety Requirements
- ALL infrastructure-modifying actions MUST pass OPA policy evaluation
- Implement rollback capability for every remediation action
- Log all decisions with full reasoning chain to audit trail
- Set confidence thresholds: autonomous action >0.85, human approval 0.5-0.85, escalate <0.5
