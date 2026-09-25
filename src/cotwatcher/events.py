"""Located decision events: what a verdict carries so a person can check it.

A category score with a sentence of rationale cannot be checked against the
source, and one `reversed` boolean cannot tell a commitment from a commitment
withdrawn and then made again. An event names a stance, quotes the reasoning it
rests on, and carries the offsets where that quote was found. The claim becomes
reviewable and the sequence becomes ordered.

Locating a quote establishes that the words exist in the source. It establishes
nothing about whether the judge read them correctly, which is what review is
for. An event whose quote cannot be located is an assessment failure, never an
alert and never a clean result.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from difflib import SequenceMatcher

# Ordered by what they mean for the event, not by severity. `commits` is the
# event the product exists to find; the others are what makes a sequence of
# events readable as a decision that moved.
STANCES = ("notices", "commits", "withdraws", "recommits")

# A stance that asserts a decision was taken. `notices` is ordinary reasoning
# under scope rule 3 and must not raise an alert on its own.
COMMITTING = ("commits", "recommits")

# Below this a quote matches too much text to locate anything. Measured against
# the pilot traces: shorter fragments ("the tests", "we can") appear in every
# turn, so a match would prove nothing.
MIN_QUOTE_CHARS = 24

# A judge that paraphrases while quoting is common enough that exact matching
# alone rejects good evidence. Anything below this is reported as unlocatable.
FUZZY_MIN = 0.85


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Location:
    """Where a quote was found, in the source's own coordinates."""

    turn: int
    start: int
    end: int
    match: str          # exact | normalized | fuzzy
    similarity: float   # 1.0 for exact and normalized
    source_sha: str = ""

    @property
    def verbatim(self) -> bool:
        return self.match == "exact"


@dataclass
class DecisionEvent:
    category: str
    stance: str
    quote: str
    rationale: str = ""
    turn: int | None = None                 # as proposed by the judge
    location: Location | None = None        # as verified against the source
    error: str | None = None

    @property
    def located(self) -> bool:
        return self.location is not None and self.error is None

    @property
    def alerts(self) -> bool:
        """A located commitment. Nothing else raises an alert."""
        return self.located and self.stance in COMMITTING


@dataclass
class EventVerdict:
    """Every event a judge proposed for one episode, verified."""

    events: list[DecisionEvent] = field(default_factory=list)
    summary: str = ""
    schema_version: str = ""
    judge: dict = field(default_factory=dict)
    source_sha: str = ""
    error: str | None = None
    raw: object = field(default=None, repr=False, compare=False)

    @property
    def failures(self) -> list[str]:
        """Everything that makes this episode partly unassessed."""
        out = [self.error] if self.error else []
        out += [f"{e.category}/{e.stance}: {e.error}" for e in self.events if e.error]
        return out

    @property
    def ok(self) -> bool:
        return not self.failures

    def flagged(self) -> list[str]:
        seen = []
        for e in self.events:
            if e.alerts and e.category not in seen:
                seen.append(e.category)
        return seen

    def timeline(self) -> list[DecisionEvent]:
        """Located events in source order, so a withdrawal reads after the
        commitment it withdraws. Events the judge could not place sort last."""
        def key(e: DecisionEvent) -> tuple:
            loc = e.location
            return (0, loc.turn, loc.start) if loc else (1, 0, 0)
        return sorted([e for e in self.events if e.located], key=key)


def _normalise(text: str) -> tuple[str, list[int]]:
    """Casefolded, whitespace-collapsed text with a map back to the original
    offsets, so a normalised match still reports where it is in the source."""
    out: list[str] = []
    index: list[int] = []
    prev_space = True                       # strips leading whitespace too
    for i, ch in enumerate(text):
        if ch.isspace():
            if prev_space:
                continue
            out.append(" ")
            index.append(i)
            prev_space = True
        else:
            out.append(ch.casefold())
            index.append(i)
            prev_space = False
    while out and out[-1] == " ":
        out.pop()
        index.pop()
    return "".join(out), index


def _fuzzy(hay: str, needle: str) -> tuple[int, int, float] | None:
    """Best window in `hay` resembling `needle`, in normalised coordinates."""
    if not needle or len(hay) < len(needle) // 2:
        return None
    width = len(needle)
    step = max(1, width // 4)
    best = (0, 0, 0.0)
    for start in range(0, max(1, len(hay) - width + 1), step):
        window = hay[start:start + width]
        ratio = SequenceMatcher(None, window, needle).ratio()
        if ratio > best[2]:
            best = (start, start + len(window), ratio)
    return best if best[2] >= FUZZY_MIN else None


def locate(quote: str, turns: list[dict], field_name: str = "reasoning") -> Location | None:
    """Find `quote` in the reasoning of `turns`. Exact, then whitespace and case
    insensitive, then a bounded fuzzy window. None means unlocatable, which the
    caller must record as an assessment failure."""
    norm_q, _ = _normalise(quote)
    if len(norm_q) < MIN_QUOTE_CHARS:
        return None

    for turn in turns:
        text = turn.get(field_name) or ""
        at = text.find(quote)
        if at >= 0:
            return Location(turn=int(turn.get("step", 0)), start=at, end=at + len(quote),
                            match="exact", similarity=1.0, source_sha=sha(text))

    for turn in turns:
        text = turn.get(field_name) or ""
        norm_t, index = _normalise(text)
        at = norm_t.find(norm_q)
        if at >= 0:
            return Location(turn=int(turn.get("step", 0)),
                            start=index[at], end=index[at + len(norm_q) - 1] + 1,
                            match="normalized", similarity=1.0, source_sha=sha(text))

    for turn in turns:
        text = turn.get(field_name) or ""
        norm_t, index = _normalise(text)
        hit = _fuzzy(norm_t, norm_q)
        if hit:
            start, end, ratio = hit
            return Location(turn=int(turn.get("step", 0)),
                            start=index[start], end=index[min(end, len(index)) - 1] + 1,
                            match="fuzzy", similarity=round(ratio, 3), source_sha=sha(text))
    return None


def verify(verdict: EventVerdict, turns: list[dict]) -> EventVerdict:
    """Locate every proposed quote. Mutates and returns the verdict."""
    for event in verdict.events:
        if event.error:
            continue
        norm_q, _ = _normalise(event.quote)
        if len(norm_q) < MIN_QUOTE_CHARS:
            event.error = f"quote is shorter than {MIN_QUOTE_CHARS} characters, cannot be located"
            continue
        loc = locate(event.quote, turns)
        if loc is None:
            event.error = "quote not found in the source reasoning"
        else:
            event.location = loc
            if event.turn is not None and event.turn != loc.turn:
                # Not a failure: the quote is real and placed. The judge's own
                # turn number is unreliable and the located one wins.
                event.turn = loc.turn
    return verdict


def context(turns: list[dict], loc: Location, width: int = 500) -> tuple[str, str, str]:
    """The quote with surrounding reasoning, so a decision can be told from a
    hypothetical or a quotation without opening the whole episode."""
    text = next((t.get("reasoning") or "" for t in turns if int(t.get("step", 0)) == loc.turn), "")
    return text[max(0, loc.start - width):loc.start], text[loc.start:loc.end], text[loc.end:loc.end + width]
