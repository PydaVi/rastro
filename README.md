# Rastro MVP

Controlled, auditable, LLM-assisted pentest agent MVP focused on attack path reasoning in a synthetic IAM lab.

## What This Demo Does
- Accepts a scoped objective and scope policy
- Loads a synthetic IAM fixture (no real cloud access)
- Runs a bounded loop: enumerate -> reason -> validate -> execute -> observe -> update graph
- Logs every decision to an append-only JSONL audit log
- Produces a Markdown and JSON report

## Quick Start
```
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the demo:
```
python -m app.main run \
  --fixture fixtures/iam_lab.json \
  --objective examples/objective.json \
  --scope examples/scope.json \
  --out outputs \
  --max-steps 5
```

Outputs:
- `outputs/audit.jsonl`
- `outputs/report.json`
- `outputs/report.md`

## Notes
- All actions are simulated and constrained to the fixture.
- No real network, cloud, or system access is used.

## Docs
- `docs/architecture.md`
- `docs/adr/0001-planner-scope.md`
