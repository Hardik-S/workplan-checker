"""Data structures shared by the parser, validator, and CLI."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Finding:
    code: str
    message: str
    task_ids: tuple[str, ...] = ()
    path: str | None = None

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["task_ids"] = list(self.task_ids)
        return result
