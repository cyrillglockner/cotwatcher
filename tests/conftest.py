"""Make the repo root importable so tests can reach `evals/`, which is not
part of the installed package but carries the experiment we rely on."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
