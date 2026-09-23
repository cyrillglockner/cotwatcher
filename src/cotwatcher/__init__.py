"""cotwatcher: watch the chain of thought of open-weight reasoning models."""

from .config import Endpoint, Settings, load
from .judge import Judge, LLMJudge, Score, parse_score
from .rubric import Category, Rubric

__all__ = ["Category", "Endpoint", "Judge", "LLMJudge", "Rubric", "Score", "Settings", "load", "parse_score"]
__version__ = "0.1.0a1"
