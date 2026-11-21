from dataclasses import asdict, dataclass, field
from typing import Any

from evals.hashing import content_hash


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    category: str
    sessions: tuple[str, ...]
    graders: tuple[dict[str, Any], ...]
    timeout_s: int = 300
    expected_tools: tuple[str, ...] = ()
    fixtures: dict[str, str] = field(default_factory=dict)
    grading_files: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "sessions", tuple(self.sessions))
        object.__setattr__(self, "graders", tuple(self.graders))
        object.__setattr__(self, "expected_tools", tuple(sorted(self.expected_tools)))

    @property
    def version(self) -> str:
        payload = asdict(self)
        keys_to_ignore = ["id", "title", "category"]
        for key in keys_to_ignore:
            payload.pop(key)
        return content_hash(payload)
