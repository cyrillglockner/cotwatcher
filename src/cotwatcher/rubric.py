"""Rubric: the list of things the user worries about, loaded from YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Category:
    name: str
    definition: str
    examples: tuple[str, ...] = ()


@dataclass(frozen=True)
class Rubric:
    categories: tuple[Category, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.categories)

    @classmethod
    def from_dict(cls, data: dict) -> "Rubric":
        cats = data.get("categories") or []
        if not cats:
            raise ValueError("rubric has no categories")
        out = []
        for c in cats:
            if "name" not in c or "definition" not in c:
                raise ValueError(f"category needs a name and a definition: {c!r}")
            out.append(
                Category(
                    name=str(c["name"]).strip(),
                    definition=" ".join(str(c["definition"]).split()),
                    examples=tuple(str(e) for e in c.get("examples", [])),
                )
            )
        names = [c.name for c in out]
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate category names: {names}")
        return cls(categories=tuple(out))

    @classmethod
    def load(cls, path: str | Path) -> "Rubric":
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(yaml.safe_load(f))

    @classmethod
    def default(cls) -> "Rubric":
        text = resources.files("cotwatcher.rubrics").joinpath("default.yaml").read_text("utf-8")
        return cls.from_dict(yaml.safe_load(text))

    def to_prompt(self) -> str:
        """Render the rubric as the judge sees it."""
        parts = []
        for c in self.categories:
            block = [f"### {c.name}", c.definition]
            if c.examples:
                block.append("Examples of reasoning that scores high:")
                block.extend(f"- {e}" for e in c.examples)
            parts.append("\n".join(block))
        return "\n\n".join(parts)
