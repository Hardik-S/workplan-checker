# Workplan Checker

Workplan Checker is an offline CLI that reviews a YAML plan before parallel coding tasks are dispatched. It checks task-contract completeness, dependency references and cycles, and conflicting read/write ownership so obvious integration hazards appear before workers start.

It does not create or assign GitHub issues, launch agents, reserve files, run verification commands, or prove that a task breakdown is correct. Version 0.1 accepts exact repository-relative file paths; glob syntax is rejected rather than guessed.

## Quickstart

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
workplan-check examples/valid.yaml
```

The valid example exits `0`. The adversarial example has two concurrently eligible tasks claiming the same output and exits `1` with a `writes_overlap` finding.

## Plan format

Each task declares `id`, `title`, exact `writes`, optional `reads`, optional `forbidden`, `depends_on`, `verify`, `artifact`, `deadline`, and `stop_if`. Verification commands are recorded and checked for presence; they are never executed by this tool.

```yaml
version: 1
project: example
tasks:
  - id: parser
    title: Parse the work plan
    writes: [src/plan.py]
    reads: [README.md]
    forbidden: [src/cli.py]
    depends_on: []
    verify: [python -m pytest tests/test_plan.py]
    artifact: src/plan.py
    deadline: "2026-10-10T09:32:00-04:00"
    stop_if: Stop after the parser API and its focused tests pass.
```

## Limits

This is a deterministic pre-dispatch lint, not an agent orchestrator or a guarantee of conflict-free integration. It checks declared exact paths and dependency order only. It does not inspect future diffs, infer implicit dependencies, or evaluate whether acceptance tests are meaningful.
