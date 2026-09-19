"""cotwatcher: watch the chain of thought of open-weight reasoning models."""

from .judge import Judge, LLMJudge, Score, parse_score
from .rubric import Category, Rubric

__all__ = ["Category", "Judge", "LLMJudge", "Rubric", "Score", "parse_score"]
__version__ = "0.1.0"
