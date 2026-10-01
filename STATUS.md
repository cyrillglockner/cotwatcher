# Status

Last updated 2026-10-01.

cotwatcher reads a model's chain of thought and decides whether the model committed to
pursuing behaviour a rubric prohibits. It does not assess the model's output.

## Pilot evaluation

Eight agentic coding episodes were run with a local 8B model, hand-labelled, and frozen:
two positives, six negatives. Both positives are commitments the model later withdrew.

The judge was then run against those labels in two arms, one seeing only the produced
artifacts and one seeing the reasoning as well. The prompt and rubric hashes were checked
before and after the run to confirm the judge was not tuned during the evaluation.

| arm | assessable (of 8) | positives caught | negatives flagged |
|---|---|---|---|
| artifacts only | 5 | 1 of 2 | 2 of 3 |
| artifacts and reasoning | 6 | 1 of 1 | 1 of 5 |

The assessable count is lower than eight because five of the sixteen scorings returned no
rationale. Those are unassessed, not clean; see the defect below.

Each arm caught a different positive. The artifact-only arm caught the episode where the
model's own report admits the shortcut. The reasoning arm caught the episode where the
artifacts are clean and the decision appears only in the chain of thought. All three false
flags are episodes labelled negative because the model was confused rather than because it
decided anything.

Two defects were found.

**A reply with no rationale was accepted as a clean verdict.** Fixed: `parse_score` now
records an assessment error when the rationale is empty, whatever the scores say
(`test_reply_without_a_rationale_is_not_a_verdict`). The scale was larger than the first
report of this said. Five of the sixteen scorings had no rationale, all of them all-zero,
so they had all read as clean chunks. One is a labelled positive, which means the reasoning
arm did not miss that episode, it failed to assess it and the failure was invisible.

**The reversal flag is set by the arm that cannot see the reversals.** The artifact-only arm
set it on all four episodes of the task where the model oscillated between two readings of
the specification; the reasoning arm set it on none of the eight. Both positives are
commit-then-reverse. This is not a parser fault and a field check will not fix it. One
boolean cannot express commitment, withdrawal and recommitment across turns, so the fix is
a change to what a verdict carries, tested behaviourally.

## External transcripts

Published transcripts from other work are held as a separate challenge set rather than
merged into the pilot labels. Four of seven substantive reasoning blocks state that the
model believes it is being evaluated. Awareness is recorded per block and reported
separately: such a block cannot establish what a model does unobserved, but it is still a
valid negative for judge specificity, which asks only whether the observed text contains a
decision. Five blocks are labelled, one positive and four negatives, three of them
awareness-marked. The two uses are never pooled in one rate.

Selection bias in this source is severe, because the published blocks are the ones used in
paper figures and 31 of 38 are elided. Recall on them is meaningful; precision is not.

## Review surface

Built 2026-09-24. `cotwatcher propose` asks a judge for decision events, each quoting the
model's reasoning; `cotwatcher review` locates every quote in the source and renders it with
the surrounding text on one HTML page, with confirm, reject and unsure. An event whose quote
cannot be located is unassessed, never an alert and never clean. The event judge carries its
own schema version and the scoring judge is untouched, so the two are never pooled.

The unit is one turn, not one episode. Asked about a whole 92,000-character episode the judge
proposed nothing on a labelled positive; asked turn by turn it proposed five located events on
the same trace.

First development run, events-v1: a commitment in **every one of the eight episodes**,
including all six negatives, with no withdrawals. It did not discriminate at all.

Second development run, events-v2, which supplies the task text and prior turns and requires a
commitment to name the constraint the model recognised:

| | detected / flagged | clean | unassessed |
|---|---|---|---|
| 2 positives | 2 | 0 | 0 |
| 6 negatives | 4 | 2 | 0 |

Both positives detected, and the false alarm rate moved from 6 of 6 to 4 of 6. One of the two
clean results comes from a fuzzy match being downgraded to a suggestion rather than from a
better reading, so the improvement in judgement is smaller than the numbers suggest.

Of the 13 verified commitments, the constraint named is quoted from the model's own reasoning
in **1**. Four repeat a line of the specification and eight are the judge's own paraphrase of
it. A constraint that exists in the task is not evidence the model recognised it, so on the
definition the product uses, 1 of 13 commitment proposals is supported on both halves.

No withdrawals were proposed in any episode, in either run, although both positives are
commit-then-reverse. Supplying prior turns did not change that, so EV2 is unresolved.

Seven events failed assessment: two quotes were fabricated outright, appearing nowhere in the
episode or the task, and the rest were quoted from a turn other than the one being scored.

## Next

Review the 20 located events, then work the event judge against what that review shows. The
frozen scoring result above stands as the recorded evaluation; runs of the event judge against
these eight episodes are development work. Sample size is eight episodes; no rate should be read from it. The result above stands as
recorded. Runs after a change to the judge are development evaluations against these eight,
reported as such.


## Agent integration documentation review — 2026-09-25

The agent-written-glue MVP is documented in `docs/INTEGRATION.md`. Codex reviewed
`859ab3a` and recorded INT1–INT4 in `FINDINGS.md`: the example input budget is ignored
at its documented TOML location, the Python example bypasses configuration loading,
the sample needs a judge transport-error boundary and clear background scheduling
placement, and one check test can now call a real watched endpoint. INT5 was found while
fixing INT3: the two judges failed in two different ways, one raising when the endpoint was
unreachable and the other returning a result carrying an error, so an integration written
against one either crashed or read a failed call as a verdict with no events. All five are
fixed, each verified by a named test, and both judges now follow one failure rule: unreachable
raises, an unusable reply comes back carrying an error, neither is ever clean. The review ran
195 tests successfully and excluded that endpoint-contacting test. No new detection measurement
was made.

## Known defect in the integration verification — 2026-09-30

The integration guide asks for four checks before an integration is reported as done, and none
of them requires an alert to be raised. One is satisfied by a clean verdict and two are negative
paths, so the code an integration runs on a flag can be absent while every check passes. Logged as
INT6 and open. This is the defect shape the project keeps finding, moved one level up: the
procedure that verifies the monitor assesses nothing and looks fine.

Corrected 2026-10-01: an earlier version of this section said the installed package ships no
sample reasoning. It does. `cotwatcher check` scores an inline reward-hacking chunk and reports
the result. What stands is narrower: `check` prints a note and still exits 0 when the judge misses
that chunk, there is no clean-negative counterpart to tell discrimination from flagging
everything, nothing exercises the event judge's positive path, and the fixture is a near-paraphrase
of the worked example in the scoring judge's own system prompt.


## The events-v2 figures are environment-specific — 2026-10-01

The event-judge numbers above were produced in a single session and do not reproduce across
sessions. Measured on 2026-10-01 against the same 12 turns that carried the frozen run's verified
commitments, with byte-identical input: `prompt_sha` and `rubric_sha` match the frozen manifest,
all 17 recorded `source_sha` values match the text that was scored, and the only change to
`event_judge.py` since the frozen run at `ac2a3ed` is error handling that does not touch input
construction.

| run | Ollama | turns alerting | frozen decision recovered |
|---|---|---|---|
| frozen 2026-09-24 | 0.32.9 | 12 of 12 | 12 of 12 |
| rerun 2026-09-30 | 0.32.9 | 8 of 12 | 6 of 12 |
| rerun 2026-10-01, three passes | 0.35.0 | 5 of 12 | 2 of 12 |

The frozen row is not an independent measurement: those 12 turns were selected because the frozen
run found verified commitments in them.

Within one session the judge is deterministic. Three consecutive passes agreed on all 12 turns,
every one. So this is not per-call sampling noise, and repeated sampling would not recover the
missing detections. The variation is between environments, and the cause is not established: the
served context of the judge instance was not recorded for the earlier runs, and an Ollama upgrade
from 0.32.9 to 0.35.0 falls between the last two rows.

What this does to the figures above. Episode-level detection was the steadier measure, 6 of 6
against 5 of 6 across the two reruns, so the headline — both positives detected, four of six
negatives flagged — is probably sound. The event-level counts are not: 13 verified commitments, of
which 1 carries a constraint quoted from the model's own reasoning, is one draw in one environment.
EV10 was premised on that ratio and needs re-measuring before events-v3 is designed against it.

Fixed as part of this: `cotwatcher propose` now records `judge_context` and
`judge_max_input_tokens` in its manifest and refuses to start when the served window cannot hold
the budget. `prompt_sha` hashes the prompt that was meant to be sent, not the one that arrived, so
without the served window a front-truncated run and an intact one are indistinguishable
afterwards. Recorded against F8, whose earlier claim that effective context could not be queried
from the endpoint was wrong.
