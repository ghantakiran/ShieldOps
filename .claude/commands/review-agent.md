# Review Agent Skill

Review ShieldOps agent code for correctness, safety, and reliability.

## Usage
`/review-agent [--scope <file|module|all>]`

## Review Checklist

### Safety (Critical)
- [ ] All infrastructure-modifying actions pass through OPA policy evaluation
- [ ] Rollback capability exists for every write operation
- [ ] Confidence thresholds correctly gate autonomous vs. approval-required actions
- [ ] Blast radius limits enforced per environment
- [ ] No hardcoded credentials or secrets
- [ ] Audit trail logging for every action

### Reliability
- [ ] Error handling at every external call (APIs, connectors, LLM)
- [ ] Timeout configuration for all async operations
- [ ] Graceful degradation (agent fails safe, not destructive)
- [ ] State persistence across retries (LangGraph checkpointing)
- [ ] Idempotent actions (safe to retry)

### Agent Architecture
- [ ] LangGraph state schema matches PRD requirements
- [ ] Node functions are pure (input → output, no hidden side effects)
- [ ] Conditional edges have complete coverage (no missing branches)
- [ ] Tool functions properly typed and documented
- [ ] Reasoning chain captures every decision point

### Testing
- [ ] Unit tests for all node functions
- [ ] Integration tests for connector operations
- [ ] Agent simulation tests with historical incidents
- [ ] Policy evaluation tests for all action types
- [ ] Edge cases: timeout, partial failure, concurrent operations

## Severity Levels
- **P0 (Block):** Safety violation, missing policy check, data loss risk
- **P1 (Must Fix):** Missing error handling, untested code path, reliability gap
- **P2 (Should Fix):** Code style, missing type hints, documentation gaps
- **P3 (Nice to Have):** Performance optimization, refactoring suggestions
