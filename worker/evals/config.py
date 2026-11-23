from __future__ import annotations

from dataclasses import asdict, dataclass, field

from evals.hashing import content_hash


@dataclass(frozen=True)
class Settings:
    temperature: float = 0.0
    max_steps: int = 15
    max_tokens: int = 8000
    token_budget: int = 300_000
    memory: bool = False
    skills: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "temperature", float(self.temperature))
        object.__setattr__(self, "skills", tuple(sorted(self.skills)))
        object.__setattr__(self, "tools", tuple(sorted(self.tools)))


@dataclass(frozen=True)
class Config:
    harness: str
    model: str
    settings: Settings = field(default_factory=Settings)
    label: str = field(default="", compare=False)

    @property
    def id(self) -> str:
        payload = asdict(self)
        payload.pop("label")
        return content_hash(payload)
