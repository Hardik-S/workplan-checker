from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALID = ROOT / "examples" / "valid.yaml"
ADVERSARIAL = ROOT / "examples" / "adversarial-overlap.yaml"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "workplan_check", *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_text_format_valid_plan_exits_zero():
    result = run_cli(str(VALID), "--format", "text")
    assert result.returncode == 0
    assert "valid" in result.stdout.lower()


def test_cli_text_format_overlap_exits_one_with_both_ids_and_path():
    result = run_cli(str(ADVERSARIAL))
    assert result.returncode == 1
    assert "parser" in result.stdout
    assert "formatter" in result.stdout
    assert "src/shared.py" in result.stdout


def test_cli_json_format_emits_machine_readable_findings():
    result = run_cli(str(ADVERSARIAL), "--format", "json")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert any(
        set(item["task_ids"]) == {"parser", "formatter"}
        and item["path"] == "src/shared.py"
        for item in payload
    )


def test_cli_missing_input_exits_two(tmp_path: Path):
    result = run_cli(str(tmp_path / "does-not-exist.yaml"))
    assert result.returncode == 2


def test_verify_strings_are_never_executed(tmp_path: Path):
    marker = tmp_path / "verification-was-executed"
    plan = VALID.read_text(encoding="utf-8").replace(
        "python -m pytest tests/test_parser.py",
        f"python -c \"from pathlib import Path; Path(r'{marker}').write_text('executed')\"",
    )
    plan_path = tmp_path / "plan.yaml"
    plan_path.write_text(plan, encoding="utf-8")

    result = run_cli(str(plan_path))

    assert result.returncode == 0, result.stderr
    assert not marker.exists()


def test_cli_reports_malformed_yaml_with_input_error_status(tmp_path: Path):
    plan_path = tmp_path / "malformed.yaml"
    plan_path.write_text("version: [unterminated", encoding="utf-8")
    result = run_cli(str(plan_path), "--format", "json")
    assert result.returncode == 2
    assert result.stderr
