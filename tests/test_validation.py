from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from workplan_check.validation import check_plan


ROOT = Path(__file__).resolve().parents[1]


def load_example(name: str) -> dict:
    return yaml.safe_load((ROOT / "examples" / name).read_text(encoding="utf-8"))


def findings_for(mutator) -> list:
    plan = load_example("valid.yaml")
    mutator(plan)
    return check_plan(plan)


def test_independent_disjoint_example_is_valid():
    assert check_plan(load_example("valid.yaml")) == []


def test_adversarial_example_reports_both_tasks_and_shared_path():
    findings = check_plan(load_example("adversarial-overlap.yaml"))
    overlap = [finding for finding in findings if "overlap" in finding.code]
    assert overlap
    assert any(
        set(finding.task_ids) == {"parser", "formatter"}
        and finding.path == "src/shared.py"
        for finding in overlap
    )


@pytest.mark.parametrize(
    "field",
    ["id", "title", "writes", "depends_on", "verify", "artifact", "deadline", "stop_if"],
)
def test_required_task_fields_are_reported(field: str):
    findings = findings_for(lambda plan: plan["tasks"][0].pop(field))
    assert findings, f"missing {field} should produce a finding"


def test_duplicate_task_ids_are_reported():
    findings = findings_for(lambda plan: plan["tasks"][1].update(id="parser"))
    assert any("duplicate" in finding.code for finding in findings)


@pytest.mark.parametrize("unsafe", ["../outside.py", "/absolute.py", "src/*.py", "src/../outside.py"])
def test_unsafe_or_non_exact_paths_are_reported(unsafe: str):
    findings = findings_for(lambda plan: plan["tasks"][0].update(writes=[unsafe], artifact=unsafe))
    assert findings


def test_missing_dependency_is_reported():
    findings = findings_for(lambda plan: plan["tasks"][0].update(depends_on=["absent"]))
    assert any("depend" in finding.code for finding in findings)


def test_dependency_cycle_is_reported():
    def create_cycle(plan):
        plan["tasks"][0]["depends_on"] = ["formatter"]
        plan["tasks"][1]["depends_on"] = ["parser"]

    findings = findings_for(create_cycle)
    assert any("cycle" in finding.code for finding in findings)


def test_ordered_shared_write_is_allowed():
    def order_tasks(plan):
        plan["tasks"][1]["writes"] = ["src/parser.py"]
        plan["tasks"][1]["depends_on"] = ["parser"]

    findings = findings_for(order_tasks)
    assert not any("overlap" in finding.code for finding in findings)


def test_unordered_shared_write_is_reported():
    def share_path(plan):
        plan["tasks"][1]["writes"] = ["src/parser.py"]

    findings = findings_for(share_path)
    assert any("overlap" in finding.code for finding in findings)


def test_read_after_write_requires_dependency_order():
    def read_shared_path(plan):
        plan["tasks"][1]["reads"] = ["src/parser.py"]

    findings = findings_for(read_shared_path)
    assert any("read" in finding.code and "write" in finding.code for finding in findings)


def test_read_after_write_is_allowed_when_ordered():
    def order_read(plan):
        plan["tasks"][1]["reads"] = ["src/parser.py"]
        plan["tasks"][1]["depends_on"] = ["parser"]

    findings = findings_for(order_read)
    assert not any("read" in finding.code and "write" in finding.code for finding in findings)
