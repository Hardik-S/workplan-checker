# Workplan Checker 0.1.0

Workplan Checker is an offline Python CLI for checking a multi-agent coding plan before dispatch. It reports missing task details, unsafe paths, dependency cycles, unordered write conflicts, and read-after-write gaps in YAML plans.

Install from a clean checkout with `python -m pip install -e .`, then run `workplan-check examples/valid.yaml`. Use `workplan-check examples/adversarial-overlap.yaml` to see a conflicting plan rejected with both task IDs and the shared path.

The checker never executes commands listed under `verify`, contacts GitHub, starts agents, or reserves files. It checks declared exact paths and dependencies; it does not prove the plan is complete or prevent runtime conflicts.
