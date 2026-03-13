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

## Observability & Security Module Patterns

### Observability Engine Module (non-agent)
Use this pattern for standalone analytics/intelligence engines:
```
src/shieldops/{package}/{module_name}.py
```
- Pydantic models with StrEnum enums
- Engine class with: `add_record`, `process`, `generate_report`, `get_stats`, `clear_data`
- Ring-buffer storage with `max_records` eviction
- structlog logging, uuid/time defaults
- Examples: `ebpf_network_flow_analyzer.py`, `ml_anomaly_detection_engine.py`

### GitOps & Infrastructure Intelligence
- GitOps reconciliation: `src/shieldops/changes/gitops_reconciliation_engine.py`
- IaC validation: `src/shieldops/changes/iac_validation_engine.py`
- DORA metrics: `src/shieldops/analytics/deployment_analytics_engine.py`
- DR intelligence: `src/shieldops/operations/disaster_recovery_intelligence.py`

### Security Operations Automation
- Purple team campaigns: `src/shieldops/security/purple_team_campaign_engine.py`
- Detection engineering: `src/shieldops/security/detection_engineering_pipeline_v2.py`
- SOAR workflow intelligence: `src/shieldops/security/soar_workflow_intelligence.py`
- Identity analytics: `src/shieldops/security/identity_analytics_engine.py`

### AIOps & Cognitive Automation
- ML root cause analysis: `src/shieldops/analytics/aiops_root_cause_engine.py`
- Causal inference: `src/shieldops/analytics/causal_inference_engine.py`
- Self-learning anomaly detection: `src/shieldops/observability/anomaly_self_learning_engine.py`
- Adaptive thresholds: `src/shieldops/observability/adaptive_threshold_engine.py`
- Cognitive triage: `src/shieldops/incidents/cognitive_incident_triage_engine.py`

### Developer Experience & Platform Engineering
- Service catalog: `src/shieldops/topology/service_catalog_intelligence_engine.py`
- API lifecycle: `src/shieldops/topology/api_lifecycle_engine.py`
- Service readiness: `src/shieldops/changes/service_readiness_engine.py`
- Developer portal: `src/shieldops/topology/internal_developer_portal_engine.py`

### Resilience Engineering & Chaos Intelligence
- Chaos experiments: `src/shieldops/operations/resilience_experiment_engine.py`
- Game days: `src/shieldops/operations/chaos_game_day_engine.py`
- Fault propagation: `src/shieldops/topology/fault_propagation_engine.py`
- Resilience debt: `src/shieldops/analytics/resilience_debt_engine.py`

### Next-Gen Observability & Telemetry Intelligence
- Edge telemetry processing: `src/shieldops/observability/edge_telemetry_processor.py`
- Observability ROI optimization: `src/shieldops/observability/observability_roi_optimizer.py`
- Distributed query acceleration: `src/shieldops/observability/distributed_query_accelerator.py`
- Telemetry compliance: `src/shieldops/observability/telemetry_compliance_engine.py`
- Hybrid cloud telemetry: `src/shieldops/observability/hybrid_cloud_telemetry_bridge.py`
- Intelligent sampling: `src/shieldops/observability/intelligent_sampling_coordinator.py`
- Real-time SLI calculation: `src/shieldops/observability/realtime_sli_calculator.py`
- Service level intelligence: `src/shieldops/observability/service_level_intelligence.py`
- Multi-tenant observability: `src/shieldops/observability/multi_tenant_observability_engine.py`

### Security Intelligence & Threat Automation
- Threat prediction: `src/shieldops/security/threat_prediction_engine.py`
- Adversary emulation: `src/shieldops/security/adversary_emulation_engine.py`
- Security knowledge graph: `src/shieldops/security/security_knowledge_graph_engine.py`
- Incident classification: `src/shieldops/security/automated_incident_classifier.py`
- Exploit prediction: `src/shieldops/security/vulnerability_exploit_predictor.py`
- Cross-domain threat fusion: `src/shieldops/security/cross_domain_threat_fusion.py`
- Attack narratives: `src/shieldops/security/attack_narrative_engine.py`
- Runtime threat analysis: `src/shieldops/security/runtime_threat_analyzer.py`
- Security debt quantification: `src/shieldops/security/security_debt_quantifier.py`

### Autonomous Operations & Intelligent Automation
- Autonomous incident command: `src/shieldops/operations/autonomous_incident_commander.py`
- Predictive maintenance: `src/shieldops/operations/predictive_maintenance_planner_v2.py`
- Workflow intelligence: `src/shieldops/operations/workflow_intelligence_engine.py`
- Autonomous capacity: `src/shieldops/operations/autonomous_capacity_optimizer.py`
- Automation effectiveness: `src/shieldops/analytics/automation_effectiveness_engine.py`
- Root cause ranking: `src/shieldops/analytics/intelligent_root_cause_ranker.py`
- Autonomous triage: `src/shieldops/incidents/autonomous_triage_engine.py`
- Autonomous compliance: `src/shieldops/compliance/autonomous_compliance_engine.py`
- Policy drift intelligence: `src/shieldops/compliance/policy_drift_intelligence.py`
- Intelligent audit planning: `src/shieldops/audit/intelligent_audit_planner.py`

### Auto-Learning & Intelligent Agent Optimization (autoresearch-inspired)
- Agent experiment loops: `src/shieldops/analytics/agent_experiment_engine.py`
- Model self-tuning: `src/shieldops/analytics/model_self_tuning_engine.py`
- Lightweight training: `src/shieldops/analytics/lightweight_training_engine.py`
- Knowledge distillation: `src/shieldops/knowledge/agent_knowledge_distiller.py`
- Experiment replay: `src/shieldops/analytics/experiment_replay_engine.py`
- Hypothesis generation: `src/shieldops/analytics/hypothesis_generator_engine.py`
- Agent fitness scoring: `src/shieldops/analytics/agent_fitness_scorer.py`
- Agent evolution tracking: `src/shieldops/analytics/agent_evolution_tracker.py`
- Resource budget management: `src/shieldops/operations/resource_budget_manager.py`
- Metric convergence: `src/shieldops/analytics/metric_convergence_tracker.py`

### OpenTelemetry Tooling & Pipeline Intelligence (Splunk OTel-inspired)
- Kafka telemetry pipeline: `src/shieldops/observability/kafka_telemetry_pipeline.py`
- OTel collector orchestration: `src/shieldops/observability/otel_collector_orchestrator.py`
- Auto-instrumentation: `src/shieldops/observability/auto_instrumentation_manager.py`
- Exporter management: `src/shieldops/observability/telemetry_exporter_manager.py`
- Signal routing: `src/shieldops/observability/signal_routing_engine.py`
- Collector config validation: `src/shieldops/observability/collector_config_validator.py`
- Schema evolution: `src/shieldops/observability/telemetry_schema_evolution.py`
- OTel service graph: `src/shieldops/topology/otel_service_graph_engine.py`
- Trace context propagation: `src/shieldops/observability/trace_context_propagation.py`

### Risk-Based Security Alerting (Splunk RBA-inspired)
- Entity risk scoring: `src/shieldops/security/entity_risk_scoring_engine.py`
- Risk factor aggregation: `src/shieldops/security/risk_factor_aggregator.py`
- MITRE ATT&CK risk mapping: `src/shieldops/security/mitre_risk_mapper_engine.py`
- Alert risk enrichment: `src/shieldops/security/alert_risk_enrichment_engine.py`
- Risk-based prioritization: `src/shieldops/security/risk_based_prioritizer.py`
- Risk observation consolidation: `src/shieldops/security/risk_observation_engine.py`
- Entity behavior risk: `src/shieldops/security/entity_behavior_risk_engine.py`
- Risk response automation: `src/shieldops/security/risk_response_automator.py`
- Detection risk calibration: `src/shieldops/security/detection_risk_calibrator.py`

## Safety Requirements
- ALL infrastructure-modifying actions MUST pass OPA policy evaluation
- Implement rollback capability for every remediation action
- Log all decisions with full reasoning chain to audit trail
- Set confidence thresholds: autonomous action >0.85, human approval 0.5-0.85, escalate <0.5
