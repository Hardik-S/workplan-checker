"""Command-line interface for offline work-plan checks."""

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

import yaml

from .validation import check_plan


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_unique_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False):
    loader.flatten_mapping(node)
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="workplan-check",
        description="Check a YAML work plan without executing its commands.",
    )
    parser.add_argument("plan", type=Path, help="path to the YAML work plan")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text)",
    )
    return parser


def _text_output(findings: Sequence[object]) -> str:
    if not findings:
        return "Plan is valid."

    lines = [f"Plan has {len(findings)} finding(s):"]
    for finding in findings:
        code = finding.code
        message = finding.message
        task_ids = ", ".join(finding.task_ids) or "(plan-wide)"
        path = finding.path or "(no path specified)"
        lines.append(f"- [{code}] {message} (tasks: {task_ids}; path: {path})")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the checker and return 0, 1, or 2 for valid, findings, or input errors."""
    args = _parser().parse_args(argv)
    try:
        with args.plan.open("r", encoding="utf-8") as plan_file:
            document = yaml.load(plan_file, Loader=_UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        print(f"workplan-check: cannot read {args.plan}: {error}", file=sys.stderr)
        return 2

    findings = sorted(
        check_plan(document),
        key=lambda finding: (
            finding.code,
            finding.message,
            tuple(finding.task_ids),
            finding.path or "",
        ),
    )
    if args.format == "json":
        print(json.dumps([finding.as_dict() for finding in findings], ensure_ascii=False))
    else:
        print(_text_output(findings))
    return 1 if findings else 0
