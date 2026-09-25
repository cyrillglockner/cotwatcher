# Status

Last updated 2026-09-25.

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
placement, and one check test can now call a real watched endpoint. These remain
open pending verification of fixes. The review ran 195 tests successfully and
excluded that endpoint-contacting test. No new detection measurement was made.
