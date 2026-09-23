"""Settings: where the watched model and the judge live, and which rubric to use.

Resolution order, later wins: built-in defaults, `cotwatcher.toml`, environment.
The defaults match the baseline (local Ollama serving gpt-oss:20b for both roles)
so a fresh install works with no config file at all.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .judge import LLMJudge
from .rubric import Rubric

OLLAMA_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "gpt-oss:20b"
CONFIG_FILE = "cotwatcher.toml"


@dataclass(frozen=True)
class Endpoint:
    """One OpenAI-compatible server plus the model to ask it for."""

    url: str = OLLAMA_URL
    api_key: str = "ollama"  # Ollama ignores the key, the client still needs one
    model: str = DEFAULT_MODEL

    def client(self) -> Any:
        from openai import OpenAI

        return OpenAI(base_url=self.url, api_key=self.api_key)


@dataclass(frozen=True)
class Settings:
    model: Endpoint = field(default_factory=Endpoint)
    judge: Endpoint = field(default_factory=Endpoint)
    judge_reasoning_effort: str | None = "low"
    rubric_path: Path | None = None

    def rubric(self) -> Rubric:
        return Rubric.load(self.rubric_path) if self.rubric_path else Rubric.default()

    def make_judge(self) -> LLMJudge:
        return LLMJudge(
            self.judge.client(),
            model=self.judge.model,
            rubric=self.rubric(),
            reasoning_effort=self.judge_reasoning_effort,
        )


# env var -> (section, field). "" means top-level.
_ENV = {
    "COTWATCHER_MODEL_URL": ("model", "url"),
    "COTWATCHER_MODEL_API_KEY": ("model", "api_key"),
    "COTWATCHER_MODEL": ("model", "model"),
    "COTWATCHER_JUDGE_URL": ("judge", "url"),
    "COTWATCHER_JUDGE_API_KEY": ("judge", "api_key"),
    "COTWATCHER_JUDGE_MODEL": ("judge", "model"),
    "COTWATCHER_JUDGE_EFFORT": ("", "judge_reasoning_effort"),
    "COTWATCHER_RUBRIC": ("", "rubric_path"),
}


def load(path: str | Path | None = None, env: dict[str, str] | None = None) -> Settings:
    """Build Settings from defaults, then the TOML file, then the environment.

    `path` defaults to `$COTWATCHER_CONFIG`, then `./cotwatcher.toml` if present.
    A missing file is fine; a file that fails to parse is not.
    """
    env = os.environ if env is None else env
    data: dict[str, Any] = {}
    p = Path(path) if path else _default_path(env)
    if p is not None:
        with open(p, "rb") as f:
            data = tomllib.load(f)

    for var, (section, key) in _ENV.items():
        if var in env:
            target = data.setdefault(section, {}) if section else data
            target[key] = env[var]

    return _from_dict(data)


def _default_path(env: dict[str, str]) -> Path | None:
    if "COTWATCHER_CONFIG" in env:
        return Path(env["COTWATCHER_CONFIG"])
    p = Path(CONFIG_FILE)
    return p if p.is_file() else None


def _endpoint(d: dict[str, Any]) -> Endpoint:
    known = {k: str(v) for k, v in d.items() if k in ("url", "api_key", "model")}  # other keys ignored
    return replace(Endpoint(), **known)


def _from_dict(data: dict[str, Any]) -> Settings:
    # Accept the key under [judge] as well as at top level: that is where it
    # reads naturally in the file, and a nested key the loader ignored would
    # silently leave the effort at its default.
    judge_section = data.get("judge", {})
    if isinstance(judge_section, dict) and "reasoning_effort" in judge_section:
        data.setdefault("judge_reasoning_effort", judge_section["reasoning_effort"])
    if isinstance(judge_section, dict) and "judge_reasoning_effort" in judge_section:
        data.setdefault("judge_reasoning_effort", judge_section["judge_reasoning_effort"])
    effort = data.get("judge_reasoning_effort", "low")
    if effort in ("", "none", "None", None):
        effort = None
    rubric = data.get("rubric_path")
    return Settings(
        model=_endpoint(data.get("model", {})),
        judge=_endpoint(data.get("judge", {})),
        judge_reasoning_effort=effort,
        rubric_path=Path(rubric) if rubric else None,
    )
