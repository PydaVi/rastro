# Architecture Note (MVP)

This MVP implements a minimal vertical slice of a controlled pentest agent with strict scope enforcement, deterministic behavior, and auditable execution.

## Core Components
- CLI: `src/app/main.py` orchestrates a bounded run.
- Domain models: `src/core/domain.py` defines objectives, actions, decisions, and observations.
- Planner interface: `src/planner/interface.py` abstracts decision logic.
- Deterministic planner: `src/planner/mock_planner.py` provides a safe, predictable backend.
- Scope enforcer: `src/execution/scope_enforcer.py` validates every action against allowed actions/resources.
- Executor: `src/execution/executor.py` applies simulated transitions only.
- Fixture: `src/core/fixture.py` provides the synthetic IAM lab and deterministic transitions.
- Attack graph: `src/core/attack_graph.py` keeps an explicit, inspectable graph.
- Audit logger: `src/core/audit.py` writes append-only JSONL events.
- Report generator: `src/reporting/report.py` compiles JSON and Markdown outputs.

## Execution Loop
The CLI runs a bounded loop:
1. Enumerate available actions from the fixture.
2. Planner selects the next action.
3. Scope enforcer validates the action.
4. Executor applies a safe simulated transition.
5. Attack graph is updated.
6. Audit event is logged.

Loop stops on objective completion or max steps.
