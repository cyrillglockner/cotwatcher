# Status

Last updated 2026-09-24.

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

## Next

A review surface over saved traces, before any live capture. The judge proposes decision
events, each carrying a quoted passage from the reasoning; cotwatcher verifies the quote
exists in the source, renders it with enough surrounding text to tell a decision from a
hypothetical, and records confirm, reject or unsure with a reason. A proposed event whose
quote cannot be located is an assessment failure, not an alert. That addresses the second
defect, because a sequence of located events expresses withdrawal and recommitment where a
boolean cannot, and it is the same event format live reasoning would later feed.

Sample size is eight episodes; no rate should be read from it. The result above stands as
recorded. Runs after a change to the judge are development evaluations against these eight,
reported as such.
