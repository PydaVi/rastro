# PLANS.md

## Phase 0 — MVP (Synthetic IAM Attack Path)

### Objective
Build a minimal vertical slice that proves:
- bounded agent loop
- scope enforcement
- auditable execution
- attack path reasoning

---

## Step 0 — Project Bootstrap

- Create project structure
- Setup CLI with Typer
- Setup Pydantic models
- Setup pytest
- Add basic README

DONE WHEN:
- CLI runs
- tests run successfully

---

## Step 1 — Domain Models

Implement:
- Objective model
- Scope model
- Action model
- ActionResult model
- State model

DONE WHEN:
- models are defined and validated
- unit tests exist

---

## Step 2 — Synthetic IAM Fixture

Implement:
- fake users
- fake roles
- fake permissions
- deterministic relationships

DONE WHEN:
- fixture loads locally
- no external dependencies
- test validates fixture structure

---

## Step 3 — Planner (Mock)

Implement:
- Planner interface
- Deterministic planner (no LLM yet)
- Select next action based on current state

DONE WHEN:
- planner returns predictable actions
- unit tests validate decisions

---

## Step 4 — Scope Enforcer

Implement:
- validation of every action against scope
- allow/deny logic

DONE WHEN:
- invalid actions are blocked
- tests cover allow + deny cases

---

## Step 5 — Executor (Safe Simulation)

Implement:
- simulated execution of actions
- deterministic state changes

DONE WHEN:
- execution updates state correctly
- no real external calls

---

## Step 6 — Attack Graph

Implement:
- nodes = states
- edges = actions
- simple in-memory structure

DONE WHEN:
- graph updates each step
- graph is inspectable

---

## Step 7 — Audit Logger

Implement:
- append-only JSONL logs
- log:
  - decision
  - action
  - result
  - timestamp

DONE WHEN:
- logs are written per step
- format is consistent

---

## Step 8 — Execution Loop

Implement bounded loop:

enumerate → plan → validate → execute → observe → update graph

Constraints:
- max_steps = 5

DONE WHEN:
- full loop runs end-to-end
- no infinite loops

---

## Step 9 — Report Generator

Implement:
- markdown report
- json report

Include:
- objective
- steps taken
- allowed/blocked actions
- attack path
- final outcome

DONE WHEN:
- report is generated after run

---

## Step 10 — CLI Integration

Implement:

rastro run --objective "..."" --scope scope.yaml

DONE WHEN:
- CLI executes full pipeline
- outputs logs + report

---

## Step 11 — Tests & Validation

- unit tests for core modules
- one integration test for full run

DONE WHEN:
- pytest passes
- MVP runs locally

---

## Phase 0 Completion Criteria

The phase is complete only when:

1. CLI runs end-to-end
2. Synthetic attack path is discovered
3. Scope enforcement blocks invalid actions
4. Audit log is complete and readable
5. Attack graph is generated
6. Report is generated
7. All tests pass

---

## Phase 1 — LLM Planner Integration (NEXT)

DO NOT START UNTIL PHASE 0 IS COMPLETE

- replace mock planner with LLM backend
- keep planner interface
- add token/cost tracking
- maintain scope enforcement

Status: pending