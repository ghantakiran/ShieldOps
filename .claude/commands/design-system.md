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
   - Plan OPA policies needed
   - Define rollback procedures

5. **Documentation**:
   - Write Architecture Decision Record (ADR) in `docs/architecture/`
   - Include diagrams (Mermaid format)
   - Document trade-offs and alternatives considered

## Output
- ADR document in `docs/architecture/adr-{number}-{name}.md`
- Updated component diagram
- API spec (if applicable)
