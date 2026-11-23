from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str


def load_skills(root: Path, names: tuple[str, ...]) -> dict[str, Skill]:
    skills = {}
    for name in names:
        path = root / name / "SKILL.md"
        if not path.is_file():
            raise FileNotFoundError(f"unknown skill {name!r}: {path} does not exist")
        skills[name] = parse_skill(name, path.read_text())
    return skills


def parse_skill(name: str, text: str) -> Skill:
    meta: dict[str, str] = {}
    body = text
    if text.startswith("---\n"):
        header, _, body = text[4:].partition("\n---\n")
        for line in header.splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return Skill(
        name=meta.get("name", name),
        description=meta.get("description", ""),
        body=body.strip(),
    )
