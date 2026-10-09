"""Deterministic validation for version-one work-plan documents."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .model import Finding


_PROJECT_FIELDS = ("project",)
_TASK_FIELDS = ("id", "title", "writes", "depends_on", "verify", "artifact", "deadline", "stop_if")
_OPTIONAL_PATH_FIELDS = ("reads", "forbidden")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _path(value: Any) -> tuple[str | None, str | None]:
    """Return a canonical slash path or a concise reason it is unsupported."""
    if not isinstance(value, str) or not value:
        return None, "must be a non-empty exact relative path"
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        return None, "must be relative"
    parts = normalized.split("/")
    if any(part == "" for part in parts):
        return None, "contains an empty path component"
    if any(part in (".", "..") for part in parts):
        return None, "contains a dot or parent traversal component"
    if any(char in normalized for char in "*?[]"):
        return None, "wildcards are unsupported; use an exact file path"
    if ":" in normalized:
        return None, "contains an unsupported colon"
    return "/".join(parts), None


def check_plan(document: Any) -> list[Finding]:
    """Return stable findings for schema, path, and task-ordering defects."""
    findings: list[Finding] = []
    if not isinstance(document, Mapping):
        return [Finding("invalid_document", "Plan must be a mapping.")]

    for field in _PROJECT_FIELDS:
        if field not in document or not isinstance(document[field], str) or not document[field].strip():
            findings.append(Finding("missing_project_field", f"Project field '{field}' is required and must be a non-empty string."))
    if "version" not in document:
        findings.append(Finding("missing_project_field", "Project field 'version' is required."))
    elif document["version"] != 1:
        findings.append(Finding("invalid_project_field", "Project field 'version' must be 1."))

    raw_tasks = document.get("tasks")
    if not isinstance(raw_tasks, list):
        findings.append(Finding("invalid_tasks", "Project field 'tasks' must be a list."))
        return findings

    # Record usable task identities first so missing-reference checks are independent
    # of the order in which dependencies are declared.
    task_rows: list[tuple[int, Mapping[str, Any], str | None]] = []
    counts: dict[str, int] = {}
    for index, raw_task in enumerate(raw_tasks):
        if not isinstance(raw_task, Mapping):
            findings.append(Finding("invalid_task", f"Task at index {index} must be a mapping."))
            continue
        task_id = raw_task.get("id")
        usable_id = task_id if isinstance(task_id, str) and _ID_RE.fullmatch(task_id) else None
        task_rows.append((index, raw_task, usable_id))
        if usable_id:
            counts[usable_id] = counts.get(usable_id, 0) + 1

    ids = {task_id for _, _, task_id in task_rows if task_id is not None}
    for index, task, task_id in task_rows:
        display_id = task_id or f"<index:{index}>"
        for field in _TASK_FIELDS:
            if field not in task:
                findings.append(Finding("missing_task_field", f"Task '{display_id}' is missing required field '{field}'.", (display_id,)))
                continue
            value = task[field]
            valid = True
            if field in ("id", "title", "artifact", "deadline", "stop_if"):
                valid = isinstance(value, str) and bool(value.strip())
            elif field in ("writes", "depends_on"):
                valid = isinstance(value, list)
            elif field == "verify":
                valid = (
                    isinstance(value, list)
                    and bool(value)
                    and all(isinstance(item, str) and bool(item.strip()) for item in value)
                )
            if not valid:
                findings.append(Finding("invalid_task_field", f"Task '{display_id}' field '{field}' has an invalid value.", (display_id,)))
        if "id" in task and task_id is None:
            findings.append(Finding("invalid_task_id", f"Task at index {index} has an invalid id.", (display_id,)))
        if task_id and counts.get(task_id) > 1:
            # Emit once per duplicate id, attached to all rows with that id below.
            if index == next(i for i, _, candidate in task_rows if candidate == task_id):
                findings.append(Finding("duplicate_task_id", f"Task id '{task_id}' is duplicated.", (task_id,)))

    # Parse path lists and build a dependency graph from resolvable references.
    deps: dict[str, set[str]] = {task_id: set() for task_id in ids}
    writes: dict[str, set[str]] = {task_id: set() for task_id in ids}
    reads: dict[str, set[str]] = {task_id: set() for task_id in ids}
    forbids: dict[str, set[str]] = {task_id: set() for task_id in ids}
    for index, task, task_id in task_rows:
        label = task_id or f"<index:{index}>"
        for field in ("writes", "reads", "forbidden"):
            if field not in task:
                if field in _OPTIONAL_PATH_FIELDS:
                    continue
                continue
            raw_values = task[field]
            if not isinstance(raw_values, list):
                continue
            seen_values: set[str] = set()
            for value in raw_values:
                canonical, error = _path(value)
                if error:
                    findings.append(Finding("unsafe_path", f"Task '{label}' {field} entry {value!r} {error}.", (label,), str(value) if isinstance(value, str) else None))
                    continue
                assert canonical is not None
                if canonical in seen_values:
                    findings.append(Finding("duplicate_path", f"Task '{label}' repeats {field} path '{canonical}'.", (label,), canonical))
                seen_values.add(canonical)
                if field == "writes" and task_id in writes:
                    writes[task_id].add(canonical)
                elif field == "reads" and task_id in reads:
                    reads[task_id].add(canonical)
                elif field == "forbidden" and task_id in forbids:
                    forbids[task_id].add(canonical)

        artifact = task.get("artifact")
        if isinstance(artifact, str) and artifact.strip():
            canonical, error = _path(artifact)
            if error:
                findings.append(Finding("unsafe_path", f"Task '{label}' artifact {artifact!r} {error}.", (label,), artifact))

        raw_deps = task.get("depends_on")
        if task_id in deps and isinstance(raw_deps, list):
            seen_deps: set[str] = set()
            for dependency in raw_deps:
                if not isinstance(dependency, str) or not dependency:
                    findings.append(Finding("invalid_dependency", f"Task '{label}' has a dependency that must be a non-empty task id.", (label,)))
                elif dependency not in ids:
                    findings.append(Finding("missing_dependency", f"Task '{label}' depends on unknown task '{dependency}'.", (label, dependency)))
                elif dependency in seen_deps:
                    findings.append(Finding("duplicate_dependency", f"Task '{label}' repeats dependency '{dependency}'.", (label, dependency)))
                else:
                    deps[task_id].add(dependency)
                if isinstance(dependency, str):
                    seen_deps.add(dependency)

    for task_id in sorted(ids):
        for path in sorted(writes[task_id] & forbids[task_id]):
            findings.append(Finding("forbidden_write", f"Task '{task_id}' writes its own forbidden path '{path}'.", (task_id,), path))

    # Compute transitive prerequisites; duplicate IDs are omitted from the graph
    # above because their references cannot identify a unique task safely.
    ordered: dict[str, set[str]] = {}
    for task_id in sorted(deps):
        reached: set[str] = set()
        stack = list(deps[task_id])
        while stack:
            dependency = stack.pop()
            if dependency == task_id:
                reached.add(task_id)
                continue
            if dependency in reached:
                continue
            reached.add(dependency)
            stack.extend(deps.get(dependency, ()))
        ordered[task_id] = reached
        if task_id in reached:
            findings.append(Finding("dependency_cycle", f"Task '{task_id}' participates in a dependency cycle.", (task_id,)))

    unique_ids = sorted(task_id for task_id in ids if counts.get(task_id) == 1)
    for pos, left in enumerate(unique_ids):
        for right in unique_ids[pos + 1:]:
            shared = writes[left] & writes[right]
            if left in ordered[right] or right in ordered[left]:
                continue
            for path in sorted(shared):
                findings.append(Finding("writes_overlap", f"Tasks '{left}' and '{right}' write the same path without an ordering dependency.", (left, right), path))
    for reader in unique_ids:
        for writer in unique_ids:
            if writer == reader or writer in ordered[reader]:
                continue
            for path in sorted(reads[reader] & writes[writer]):
                findings.append(Finding("read_after_write", f"Task '{reader}' reads path '{path}' written by '{writer}' without depending on it.", (reader, writer), path))

    # Findings follow declaration/schema order, then stable nested traversal order.
    return findings
