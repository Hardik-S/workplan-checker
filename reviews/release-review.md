# Independent Release Review

**Reviewed commit:** `2f296358f20c53534976983f987e31c5ad1443c0`

**Recommendation: BLOCK.** The normal suite and documented examples pass, but malformed YAML/path declarations can be accepted as valid or conceal conflicting ownership. These are actionable pre-dispatch validation gaps.

## Verification performed

- `git -C <repo> status --short` — clean before review; no tracked or untracked changes reported.
- `gh issue view 4 --repo Hardik-S/workplan-checker --json title,body,state,url` — issue #4 is open and matches the independent review scope.
- `python -m pytest -q` from the repository — collection failed because `workplan_check` was not importable in the ambient environment.
- `PYTHONPATH=<repo>\src python -m pytest -q` — **27 passed**.
- Built and installed the commit from a `git archive` copy in `%TEMP%` with `python -m pip install --no-deps --no-build-isolation --target <temp-site> <temp-copy>` — wheel built and installed. With that target on `PYTHONPATH`, `python -m workplan_check examples/valid.yaml` exited 0 and the adversarial example exited 1 with `writes_overlap`. Dependencies were intentionally excluded from this isolated packaging check; the environment already supplied PyYAML.
- Probed adversarial YAML/path cases directly through `check_plan`; results are recorded below. No `verify` command from any plan was executed.

## Findings

### P1 — Duplicate YAML keys silently hide declarations

**Location:** `src/workplan_check/cli.py:46-48`

`yaml.safe_load` uses PyYAML's default mapping construction, which silently keeps the last value for a duplicate key. As a result, a duplicate `writes` declaration can erase a conflicting path before validation, and the CLI reports the plan valid. This is a false negative in the core pre-dispatch conflict check.

**Reproduction:** use this plan (all omitted contract fields are included):

```yaml
version: 1
project: p
tasks:
  - id: a
    title: A
    writes: [shared.py]
    writes: [a.py]
    depends_on: []
    verify: []
    artifact: a.py
    deadline: d
    stop_if: s
  - id: b
    title: B
    writes: [shared.py]
    depends_on: []
    verify: []
    artifact: b.py
    deadline: d
    stop_if: s
```

Run `workplan-check plan.yaml` (or call `check_plan(yaml.safe_load(text))`): it exits 0 / returns `[]`, although task `a`'s first declared write conflicts with task `b`. Reject duplicate mapping keys during parsing and add a regression test asserting input-error status or a finding.

### P2 — Windows alternate data stream syntax passes as a repository file path

**Location:** `src/workplan_check/validation.py:22-32`

The path checker rejects drive prefixes and traversal, but allows `:` inside a later component. On Windows, `src/app.py:metadata` addresses an NTFS alternate data stream associated with `src/app.py`, rather than an exact ordinary repository file. It passes the exact-path gate, so downstream workers can receive a path with different filesystem semantics than the plan claims.

**Reproduction:** set a valid task's `writes` and `artifact` to `src/app.py:metadata`; `check_plan` returns no findings. Reject colons in path components (and cover Windows-specific path aliases) or explicitly define and enforce a platform-neutral path grammar.

### P2 — `verify` list members are not validated as commands

**Location:** `src/workplan_check/validation.py:77-82`

The validator checks only that `verify` is a list. A non-command member such as `null` is accepted, despite the plan contract describing these as recorded verification commands. A plan with no usable verification command can therefore pass as valid and give a false assurance about its acceptance evidence.

**Reproduction:** use an otherwise valid task with `verify: [null]`; `check_plan` returns no findings and the CLI exits 0. Require each member to be a non-empty string (and add malformed-member tests). The checker should continue recording these strings without executing them.

## Scope notes

Dependency references, cycles, ordered writes, read-after-write ordering, the documented overlap example, CLI JSON/text output, and status behavior for the covered cases are implemented and exercised by tests. The duplicate-key, Windows path grammar, and malformed `verify` member cases are absent from the suite.

## Follow-up review — 2026-10-09

**Reviewed commit:** `8ad426e25da0223949f7985d750de660ff810556`

**Recommendation: PASS for the three previously reported release blockers.** All three are addressed in this commit, with focused regression tests, and the checks below passed. This supersedes the prior BLOCK recommendation for those findings.

- Duplicate YAML keys: `src/workplan_check/cli.py` now uses a `SafeLoader` subclass that rejects duplicate mapping keys. The added CLI regression test asserts duplicate `writes` keys exit with input-error status 2 and report `duplicate key`. The previously missed overlapping-write plan is therefore rejected during parsing before validation.
- Windows alternate data stream syntax: `src/workplan_check/validation.py` now rejects colons in paths. The unsafe-path parametrized regression test includes `src/app.py:metadata`; a direct check returned `unsafe_path` for both `writes` and `artifact`.
- Verification command members: `verify` now must be a non-empty list of non-empty strings. Added cases cover empty lists, `null`, whitespace-only strings, mixed types, and null members. A direct `[null]` check returned `invalid_task_field`.

**Read-only checks:** `git rev-parse HEAD` returned the reviewed SHA. `PYTHONPATH=<repo>\src python -m pytest -q` reported **34 passed**. The duplicate-key regression exercised the CLI input-error path; no plan verification command was executed. The worktree had only the already-owned untracked `reviews/` artifact before this follow-up; no other path was changed.
