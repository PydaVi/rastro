# AGENTS.md

## Purpose

This repository implements a controlled, auditable, LLM-assisted pentest agent.

The goal is NOT to perform real offensive operations.
The goal is to model and reason about attack paths in a safe, bounded, and explainable way.

All agents (human or AI) must follow the constraints defined here.

---

## Core Principles

1. **Control over autonomy**
   - The agent must never act freely without validation.
   - All actions must pass through validation layers.

2. **Strict scope enforcement**
   - Every action MUST be validated against the defined scope.
   - No action may execute outside scope under any circumstance.

3. **Safety first**
   - No real offensive techniques in MVP.
   - Only simulated or synthetic environments are allowed.
   - No real cloud, network, or system access.

4. **Auditability**
   - Every decision must be logged.
   - Every action must be traceable.
   - Logs must be append-only.

5. **Explainability**
   - The system must always explain:
     - why an action was chosen
     - what it expects to achieve
     - what changed after execution

6. **Determinism (for MVP)**
   - Behavior should be predictable and testable.
   - Prefer deterministic logic where possible.

---

## Allowed Actions (MVP)

- Simulated enumeration
- Simulated permission analysis
- Synthetic privilege escalation steps

All actions must:
- operate only on local fixtures
- be deterministic
- not call external systems

---

## Forbidden Actions

- Real network scanning
- Real cloud API calls
- Shell command execution outside controlled simulation
- Exploitation of real systems
- Any action that modifies real infrastructure

If in doubt: DO NOT IMPLEMENT.

---

## Architecture Constraints

- Planner must be abstracted (no hard dependency on a single LLM)
- Scope Enforcer must validate ALL actions before execution
- Executor must be isolated and safe
- Attack Graph must be explicit and inspectable
- Audit Logger must be append-only

---

## Development Guidelines

- Keep implementations small and composable
- Avoid overengineering
- Prefer clarity over cleverness
- Every module should have tests
- No hidden side effects

---

## Testing Rules

- Tests must not require external services
- All scenarios must run locally
- Use synthetic fixtures only

---

## When Extending the System

Before adding any new capability, ask:

1. Does this break scope enforcement?
2. Does this reduce auditability?
3. Does this introduce real-world risk?
4. Is this necessary for the current MVP?

If the answer is unclear: do not proceed.

---

## Agent Behavior Guidelines (for Codex or other AI)

- Do not expand scope beyond the MVP definition
- Do not introduce real offensive capabilities
- Do not remove safety or validation layers
- Prefer minimal, safe implementations
- Stop when the defined MVP is complete

---

## Definition of Done (MVP)

- Controlled execution loop works
- Scope enforcement is active
- All actions are logged
- Attack graph is generated
- Report is produced
- All tests pass