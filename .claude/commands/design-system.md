# System Design Skill

Design new ShieldOps components, APIs, or agent workflows.

## Usage
`/design-system <component> [--depth <shallow|deep>]`

## Process

1. **Requirements Gathering**:
   - Read relevant PRDs from `docs/prd/`
   - Identify stakeholders and constraints
   - Map dependencies on existing components

2. **Architecture Design**:
   - Define component boundaries and interfaces
   - Choose patterns (event-driven, request-response, CQRS)
   - Design data models (Pydantic schemas)
   - Plan LangGraph workflow (if agent-related)

3. **API Design** (if applicable):
   - Define REST endpoints with OpenAPI spec
   - Design request/response schemas
   - Plan authentication and authorization
   - Define rate limits and quotas

4. **Safety Analysis**:
   - Identify failure modes and blast radius
   - Design circuit breakers and fallbacks
   - Plan OPA policies needed (leverage `PolicyCodeGenerator` for Rego stubs)
   - Define rollback procedures
   - Assess deployment risk via `DeploymentRiskPredictor`
   - Verify compliance gaps via `ComplianceGapAnalyzer`
   - Simulate service dependency impact via `ServiceDependencyImpactAnalyzer` (`src/shieldops/topology/impact_analyzer.py`)
   - Evaluate compliance automation rules via `ComplianceAutomationEngine` (`src/shieldops/compliance/automation_rules.py`)
   - Check license compliance via `DependencyLicenseScanner` (`src/shieldops/compliance/license_scanner.py`)
   - Verify service catalog completeness via `ServiceCatalogManager` (`src/shieldops/topology/service_catalog.py`)
   - Validate API contracts via `APIContractTestingEngine` (`src/shieldops/api/contract_testing.py`)
   - Detect orphaned resources via `OrphanedResourceDetector` (`src/shieldops/billing/orphan_detector.py`)
   - Score change risk via `ChangeIntelligenceAnalyzer` (`src/shieldops/changes/change_intelligence.py`)
   - Predict SLO burn rate via `SLOBurnRatePredictor` (`src/shieldops/sla/burn_predictor.py`)
   - Score dependency health via `DependencyHealthScorer` (`src/shieldops/topology/dependency_scorer.py`)
   - Enforce tag governance via `ResourceTagGovernanceEngine` (`src/shieldops/billing/tag_governance.py`)
   - Analyze team performance via `TeamPerformanceAnalyzer` (`src/shieldops/analytics/team_performance.py`)

5. **Documentation**:
   - Write Architecture Decision Record (ADR) in `docs/architecture/`
   - Include diagrams (Mermaid format)
   - Document trade-offs and alternatives considered

## Output
- ADR document in `docs/architecture/adr-{number}-{name}.md`
- Updated component diagram
- API spec (if applicable)
