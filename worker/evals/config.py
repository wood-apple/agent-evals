from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Settings:
    temperature: float = 0.0
    max_steps: int = 10
    max_tokens: int = 4000
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
        payload_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload_str.encode()).hexdigest()[:12]
