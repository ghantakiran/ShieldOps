# Security Scan Skill

Run security audits on ShieldOps codebase and agent configurations.

## Usage
`/scan-security [--scope <area>] [--severity <level>]`

## Scopes
- `code` — Static analysis of Python code (ruff, bandit, safety)
- `deps` — Dependency vulnerability scan
- `policies` — OPA policy completeness check (includes PolicyCodeGenerator output)
- `agents` — Agent blast-radius and permission audit (includes AgentDecisionExplainer)
- `compliance` — Compliance gap analysis via `ComplianceGapAnalyzer` + `ComplianceAutomationEngine`
- `audit` — Configuration audit trail via `ConfigurationAuditTrail`
- `isolation` — Tenant resource isolation checks via `TenantResourceIsolationManager`
- `licenses` — Dependency license compliance via `DependencyLicenseScanner`
- `access` — Access certification review via `AccessCertificationManager`
- `contracts` — API contract drift and breaking changes via `APIContractTestingEngine`
- `incidents` — Security incident response tracking via `SecurityIncidentResponseTracker`
- `vulns` — Vulnerability lifecycle and exploit risk via `VulnerabilityLifecycleManager`
- `api-threats` — API endpoint threat detection via `APISecurityMonitor`
- `infra` — Infrastructure-as-code security scan (checkov, tfsec)
- `all` — Full security audit

## Process

1. **Code Security**: Run bandit for Python security issues, check for hardcoded secrets
2. **Dependency Audit**: Check all dependencies against CVE databases
3. **OPA Policy Review**: Verify all agent actions have corresponding policy rules
4. **Agent Permissions**: Audit blast-radius limits per environment
5. **Compliance Gap Analysis**: Run `ComplianceGapAnalyzer` from `src/shieldops/compliance/gap_analyzer.py`
6. **Compliance Automation**: Check auto-remediation rules via `ComplianceAutomationEngine` (`src/shieldops/compliance/automation_rules.py`)
7. **Configuration Audit**: Review config change trail via `ConfigurationAuditTrail` (`src/shieldops/audit/config_audit.py`)
8. **Tenant Isolation**: Verify resource boundaries via `TenantResourceIsolationManager` (`src/shieldops/policy/tenant_isolation.py`)
9. **Infrastructure**: Scan Terraform/K8s configs for misconfigurations
10. **License Compliance**: Scan dependency licenses via `DependencyLicenseScanner` (`src/shieldops/compliance/license_scanner.py`)
11. **Access Certification**: Review expired/uncertified grants via `AccessCertificationManager` (`src/shieldops/compliance/access_certification.py`)
12. **API Contract Testing**: Detect breaking changes and schema drift via `APIContractTestingEngine` (`src/shieldops/api/contract_testing.py`)
13. **Security Incident Review**: Check active incidents via `SecurityIncidentResponseTracker` (`src/shieldops/security/incident_response.py`)
14. **Vulnerability Lifecycle**: Review overdue patches and exploit risk via `VulnerabilityLifecycleManager` (`src/shieldops/security/vuln_lifecycle.py`)
15. **API Threat Detection**: Assess endpoint risk and suspicious patterns via `APISecurityMonitor` (`src/shieldops/security/api_security.py`)
16. **Certificate Expiry**: Check for expiring/expired TLS certs via `CertificateExpiryMonitor` (`src/shieldops/security/cert_monitor.py`)
17. **Network Flow Analysis**: Detect anomalies and exfiltration via `NetworkFlowAnalyzer` (`src/shieldops/security/network_flow.py`)
18. **Container Image Scanning**: Scan images for vulnerabilities via `ContainerImageScanner` (`src/shieldops/security/container_scanner.py`)
19. **Cloud Posture Management**: Detect cloud misconfigurations via `CloudSecurityPostureManager` (`src/shieldops/security/cloud_posture_manager.py`)
20. **Secrets Sprawl Detection**: Detect hardcoded credentials via `SecretsSprawlDetector` (`src/shieldops/security/secrets_detector.py`)
21. **Alert Correlation Rules**: Evaluate alert correlation patterns via `AlertCorrelationRuleEngine` (`src/shieldops/observability/alert_correlation_rules.py`)
22. **Incident Review Board**: Review incident response quality via `IncidentReviewBoard` (`src/shieldops/incidents/review_board.py`)
23. **Compliance Evidence Chain**: Verify evidence integrity via `ComplianceEvidenceChain` (`src/shieldops/compliance/evidence_chain.py`)
24. **Alert Fatigue Scoring**: Assess alert fatigue risk via `AlertFatigueScorer` (`src/shieldops/observability/alert_fatigue.py`)
25. **Compliance Drift Detection**: Detect compliance policy drift via `ComplianceDriftDetector` (`src/shieldops/compliance/compliance_drift.py`)
26. **Alert Rule Linting**: Validate alert rule quality via `AlertRuleLinter` (`src/shieldops/observability/alert_rule_linter.py`)
27. **Credential Expiry Forecasting**: Forecast credential renewal timelines via `CredentialExpiryForecaster` (`src/shieldops/security/credential_expiry_forecaster.py`)
28. **Policy Violation Tracking**: Track OPA policy violations via `PolicyViolationTracker` (`src/shieldops/compliance/policy_violation_tracker.py`)
29. **Security Posture Trend Analysis**: Track posture over time via `SecurityPostureTrendAnalyzer` (`src/shieldops/security/posture_trend.py`)
30. **Access Anomaly Detection**: Detect anomalous access patterns via `AccessAnomalyDetector` (`src/shieldops/security/access_anomaly.py`)
31. **Audit Trail Analysis**: Analyze audit trail for suspicious patterns via `ComplianceAuditTrailAnalyzer` (`src/shieldops/compliance/audit_trail_analyzer.py`)
32. **Alert Tuning Feedback**: Evaluate alert rule effectiveness via `AlertTuningFeedbackLoop` (`src/shieldops/observability/alert_tuning_feedback.py`)
33. **Discount Coverage**: Identify uncovered resources via `CloudDiscountOptimizer` (`src/shieldops/billing/discount_optimizer.py`)
34. **Knowledge Decay**: Detect stale knowledge articles via `KnowledgeDecayDetector` (`src/shieldops/knowledge/knowledge_decay.py`)
35. **Permission Drift Detection**: Detect IAM/RBAC permission creep via `PermissionDriftDetector` (`src/shieldops/security/permission_drift.py`)
36. **Feature Flag Lifecycle**: Track stale/risky feature flags via `FeatureFlagLifecycleManager` (`src/shieldops/config/flag_lifecycle.py`)
37. **Cache Effectiveness**: Analyze cache health and hit rates via `CacheEffectivenessAnalyzer` (`src/shieldops/analytics/cache_effectiveness.py`)
38. **License Risk Analysis**: Analyze transitive dependency license risks via `DependencyLicenseRiskAnalyzer` (`src/shieldops/compliance/license_risk.py`)
39. **Rate Limit Policy**: Evaluate service-to-service rate limit policies via `RateLimitPolicyManager` (`src/shieldops/topology/rate_limit_policy.py`)
40. **Permission Drift Detection**: Detect IAM/RBAC permission creep via `PermissionDriftDetector` (`src/shieldops/security/permission_drift.py`)
41. **Data Pipeline Reliability**: Monitor data pipeline health via `DataPipelineReliabilityMonitor` (`src/shieldops/observability/data_pipeline.py`)
42. **Generate Report**: Severity-rated findings with remediation guidance
43. **Audit Intelligence**: AI-powered audit analysis via `AuditIntelligenceAnalyzer` (`src/shieldops/audit/audit_intelligence.py`)
44. **Policy Impact Scoring**: Analyze impact of policy changes via `PolicyImpactScorer` (`src/shieldops/compliance/policy_impact.py`)
45. **Dependency Risk Scoring**: Score dependency failure risk via `DependencyRiskScorer` (`src/shieldops/topology/dependency_risk.py`)
46. **Automation Gap Analysis**: Identify manual security processes via `AutomationGapIdentifier` (`src/shieldops/operations/automation_gap.py`)
47. **Attack Surface Monitoring**: Monitor exposed endpoints and services via `AttackSurfaceMonitor` (`src/shieldops/security/attack_surface.py`)
48. **Incident Cost Analysis**: Calculate financial impact of security incidents via `IncidentCostCalculator` (`src/shieldops/incidents/incident_cost.py`)
49. **Resource Contention Detection**: Detect resource contention from security events via `ResourceContentionDetector` (`src/shieldops/analytics/resource_contention.py`)
50. **Cross-Team Collaboration Scoring**: Assess security collaboration across teams via `CrossTeamCollaborationScorer` (`src/shieldops/analytics/collaboration_scorer.py`)
51. **Decision Audit Logging**: Review agent decision audit trails via `DecisionAuditLogger` (`src/shieldops/audit/decision_audit.py`)
52. **Data Retention Policy**: Validate data retention compliance via `DataRetentionPolicyManager` (`src/shieldops/observability/retention_policy.py`)
53. **Tenant Resource Quotas**: Verify per-tenant resource quota enforcement via `TenantResourceQuotaManager` (`src/shieldops/operations/tenant_quota.py`)
54. **LLM Cost Tracking**: Audit AI/LLM token usage and costs via `LLMTokenCostTracker` (`src/shieldops/billing/llm_cost_tracker.py`)
55. **Risk Signal Aggregation**: Aggregate multi-domain risk signals via `RiskSignalAggregator` (`src/shieldops/security/risk_aggregator.py`)
56. **Dynamic Risk Scoring**: Real-time risk scoring via `DynamicRiskScorer` (`src/shieldops/analytics/dynamic_risk_scorer.py`)
57. **Predictive Alerting**: Pre-incident alerting via `PredictiveAlertEngine` (`src/shieldops/observability/predictive_alert.py`)
58. **Threat Hunting**: Automated threat hunting campaigns via `ThreatHuntOrchestrator` (`src/shieldops/security/threat_hunt.py`)
59. **Security Response Automation**: Automated containment via `SecurityResponseAutomator` (`src/shieldops/security/response_automator.py`)
60. **Zero Trust Verification**: Continuous trust verification via `ZeroTrustVerifier` (`src/shieldops/security/zero_trust_verifier.py`)
61. **Agent Compliance Audit**: Audit agent actions against compliance via `AgentComplianceAuditor` (`src/shieldops/agents/compliance_auditor.py`)
62. **Security Posture Simulation**: Simulate attack scenarios via `SecurityPostureSimulator` (`src/shieldops/security/posture_simulator.py`)
63. **Credential Rotation**: Automated credential rotation via `CredentialRotationOrchestrator` (`src/shieldops/security/credential_rotator.py`)
64. **Compliance Evidence Automation**: Auto-collect compliance evidence via `ComplianceEvidenceAutomator` (`src/shieldops/compliance/evidence_automator.py`)
65. **Breach Prediction**: Predict imminent security breaches via `BreachPredictor` (`src/shieldops/security/breach_predictor.py`)
66. **Compliance Posture Scoring**: Score overall compliance posture via `GovernanceDashboard` (`src/shieldops/compliance/governance_dashboard.py`)
67. **Alert Routing Optimization**: Optimize alert routing to correct responders via `AlertRoutingOptimizer` (`src/shieldops/observability/alert_routing.py`)
68. **DNS Health Monitoring**: Detect DNS misconfigurations and anomalies via `DNSHealthMonitor` (`src/shieldops/observability/dns_health_monitor.py`)
69. **Configuration Drift Analysis**: Detect infrastructure and config drift via `DriftAnalyzer` (`src/shieldops/operations/drift_analyzer.py`)
70. **Attack Surface Assessment**: Map and monitor exposed attack surfaces via `AttackSurfaceMonitor` (`src/shieldops/security/attack_surface.py`)
71. **Deployment Impact Analysis**: Assess security impact of deployments via `DeploymentImpactAnalyzer` (`src/shieldops/changes/deployment_impact.py`)
72. **Configuration Validation**: Validate configuration consistency and security via `ConfigurationValidator` (`src/shieldops/config/config_validator.py`)
73. **Observability Gap Detection**: Identify missing observability and monitoring via `ObservabilityGapAnalyzer` (`src/shieldops/observability/observability_gap.py`)
74. **Change Freeze Policy Enforcement**: Monitor and enforce change freeze windows via `ChangeFreezePolicyManager` (`src/shieldops/changes/change_freeze.py`)
75. **Service Ownership Tracking**: Verify service ownership and accountability via `ServiceOwnershipTracker` (`src/shieldops/operations/ownership_tracker.py`)
76. **Policy Enforcement Monitoring**: Monitor real-time policy enforcement across agents and infrastructure via `PolicyEnforcementMonitor` (`src/shieldops/compliance/policy_enforcer.py`)
77. **Compliance Evidence Validation**: Validate compliance evidence completeness and freshness via `ComplianceEvidenceValidator` (`src/shieldops/compliance/evidence_validator.py`)
78. **Audit Readiness Scoring**: Score audit readiness across all compliance frameworks via `AuditReadinessScorer` (`src/shieldops/audit/audit_readiness.py`)
79. **Vendor Lock-in Analysis**: Analyze vendor lock-in risk and portability across cloud providers via `VendorLockinAnalyzer` (`src/shieldops/billing/vendor_lockin.py`)
80. **Security Compliance Bridge**: Map security findings to compliance control failures via `SecurityComplianceBridge` (`src/shieldops/security/compliance_bridge.py`)
81. **Alert Deduplication**: Deduplicate noisy alerts and surface unique security incidents via `AlertDeduplicationEngine` (`src/shieldops/observability/alert_dedup.py`)
82. **Compliance Automation Scoring**: Score automation coverage for each compliance control via `ComplianceAutomationScorer` (`src/shieldops/compliance/automation_scorer.py`)
83. **Error Pattern Classification**: Classify error patterns by type and detect novel security-related error signatures via `ErrorPatternClassifier` (`src/shieldops/analytics/error_classifier.py`)
84. **Dependency Vulnerability Mapping**: Map vulnerabilities across service dependencies via `DependencyVulnerabilityMapper` (`src/shieldops/topology/dep_vuln_mapper.py`)
85. **Security Posture Benchmarking**: Benchmark security posture against industry standards via `SecurityPostureBenchmarker` (`src/shieldops/security/posture_benchmark.py`)
86. **Alert Noise Classification**: Classify alerts as actionable vs noise to reduce alert fatigue via `AlertNoiseClassifier` (`src/shieldops/observability/noise_classifier.py`)
87. **Compliance Report Automation**: Automate compliance report generation and evidence aggregation via `ComplianceReportAutomator` (`src/shieldops/compliance/report_automator.py`)
88. **Alert Escalation Analysis**: Analyze alert escalation patterns, timing, and outcomes via `AlertEscalationAnalyzer` (`src/shieldops/observability/escalation_analyzer.py`)
89. **Security Compliance Mapping**: Map security controls to compliance frameworks and detect gaps via `SecurityComplianceMapper` (`src/shieldops/security/compliance_mapper.py`)
90. **Config Drift Monitoring**: Monitor configuration drift and detect unauthorized changes via `ConfigDriftMonitor` (`src/shieldops/operations/config_drift_monitor.py`)
91. **Service Dependency Risk**: Score dependency risk across services via `ServiceDependencyRiskScorer` (`src/shieldops/topology/service_dep_risk.py`)
92. **Threat Intelligence Correlation**: Correlate threat intelligence feeds and detect relevant threats via `ThreatIntelligenceCorrelator` (`src/shieldops/security/threat_correlator.py`)
93. **Compliance Control Testing**: Test compliance controls for effectiveness via `ComplianceControlTester` (`src/shieldops/compliance/control_tester.py`)
94. **Alert Suppression Management**: Track alert suppression effectiveness via `AlertSuppressionManager` (`src/shieldops/observability/alert_suppression.py`)
95. **Metric Anomaly Scoring**: Score and classify metric anomalies via `MetricAnomalyScorer` (`src/shieldops/analytics/anomaly_scorer.py`)
96. **Incident Noise Filtering**: Filter incident noise and identify false alarms via `IncidentNoiseFilter` (`src/shieldops/incidents/noise_filter.py`)
97. **Dependency Validation**: Validate service dependencies against traffic via `ServiceDependencyValidator` (`src/shieldops/topology/dep_validator.py`)
98. **Alert Priority Optimization**: Optimize alert priority levels via `AlertPriorityOptimizer` (`src/shieldops/observability/alert_priority.py`)
99. **Cost Allocation Validation**: Validate cost allocations via `CostAllocationValidator` (`src/shieldops/billing/cost_alloc_validator.py`)
100. **Change Correlation**: Correlate changes with incidents via `ChangeCorrelationEngine` (`src/shieldops/changes/change_correlator.py`)
101. **SLO Dependency Mapping**: Map SLO dependencies via `SLODependencyMapper` (`src/shieldops/sla/slo_dep_mapper.py`)
102. **Security Event Correlation**: Correlate security events via `SecurityEventCorrelator` (`src/shieldops/security/event_correlator.py`)
103. **Evidence Consolidation**: Consolidate compliance evidence via `ComplianceEvidenceConsolidator` (`src/shieldops/compliance/evidence_consolidator.py`)
104. **Audit Compliance Reporting**: Generate audit compliance reports via `AuditComplianceReporter` (`src/shieldops/audit/compliance_reporter.py`)
105. **Vulnerability Prioritization**: Prioritize vulnerabilities by exploitability and impact via `VulnerabilityPrioritizer` (`src/shieldops/security/vuln_prioritizer.py`)
106. **Compliance Risk Scoring**: Score compliance risk across frameworks and detect high-risk areas via `ComplianceRiskScorer` (`src/shieldops/compliance/risk_scorer.py`)
107. **Audit Evidence Tracking**: Track audit evidence collection and monitor freshness via `AuditEvidenceTracker` (`src/shieldops/audit/evidence_tracker.py`)
108. **Performance Benchmarking**: Track performance benchmarks and detect regressions via `PerformanceBenchmarkTracker` (`src/shieldops/analytics/perf_benchmark.py`)
109. **Alert Correlation Optimization**: Optimize alert correlation rules and reduce false correlations via `AlertCorrelationOptimizer` (`src/shieldops/observability/alert_correlation_opt.py`)

## Severity Levels
- **CRITICAL**: Hardcoded secrets, SQL injection, unauthenticated endpoints
- **HIGH**: Missing OPA policies, overly permissive agent actions
- **MEDIUM**: Outdated dependencies with known CVEs
- **LOW**: Code style issues, missing type hints

## Output
Security report saved to `docs/security/scan-{date}.md`
