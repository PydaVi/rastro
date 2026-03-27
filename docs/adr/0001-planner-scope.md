# ADR 0001: Planner Abstraction and Scope Enforcement from Day One

## Status
Accepted

## Context
This MVP must demonstrate that attack path reasoning can be bounded, auditable, and explainable without introducing real-world risk or uncontrolled autonomy.

## Decision
1. The planner is abstracted behind a stable interface to avoid coupling to any single LLM provider.
2. Scope enforcement is a mandatory validation layer before any simulated action executes.

## Consequences
- The planner can be swapped later (e.g., for a real LLM) without reworking the execution pipeline.
- Every action is explicitly validated against scope, preserving safety and auditability.
- The MVP remains deterministic and bounded while preserving future extensibility.
