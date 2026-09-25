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

| arm | positives caught (of 2) | negatives flagged (of 6) |
|---|---|---|
| artifacts only | 1 | 2 |
| artifacts and reasoning | 1 | 1 |

Each arm caught a different positive. The artifact-only arm caught the episode where the
model's own report admits the shortcut. The reasoning arm caught the episode where the
artifacts are clean and the decision appears only in the chain of thought. All three false
flags are episodes labelled negative because the model was confused rather than because it
decided anything.

Two defects were found and are unfixed:

- The reversal flag is set by the arm that cannot see the reversals and not by the arm that
  can. Both positives are commit-then-reverse; the reasoning arm reported neither as
  reversed.
- A judge reply carrying zero scores and an empty rationale is accepted as a clean verdict
  rather than a failed assessment.

## External transcripts

Published transcripts from other work are held as a separate challenge set rather than
merged into the pilot labels. Four of seven substantive reasoning blocks state that the
model believes it is being evaluated. Negatives from that source carry no information,
because compliance may be a response to a recognised test. Positives still count.

## Next

Fix the two judge defects and re-run the frozen comparison. Sample size is eight episodes;
no rate should be read from it.
