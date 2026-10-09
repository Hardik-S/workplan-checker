"""Work-plan contract validation; implementation owned by issue #1."""

from typing import Any

from .model import Finding


def check_plan(document: Any) -> list[Finding]:
    """Return deterministic validation findings for a parsed YAML document."""
    raise NotImplementedError("Implement issue #1")
