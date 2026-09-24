# Feedback on the narrowed actor run — 2026-09-23

Checked HEAD `099f12d`. For Claude and Cyrill; observational feedback, no changes to the running experiment.

The v3 pair fixes the duplicate-input contradiction, and each variant now has a hidden assertion for its contradictory input. The harness now aggregates test phases and checks process exit. These address the specific blockers raised in the follow-up review. The pair still varies invalid-input/validation behavior versus a wrong numerical result on valid input, along with comments/names. Describe it as a matched exploratory comparison, not a clean isolation of one causal factor.

Eight blocked episodes are a reasonable budgeted pilot. Two observations per cell cannot establish a stable rate or pressure effect. The previous 3/3 controls are useful feasibility evidence, but controls with different token caps or parser/retry behavior are not matched controls for this batch. Keep batches separate and record settings; no need to interrupt the running pilot just to add controls.

Three blocked patches widening validation establish repeated specification violation if verified from the saved artifacts. Deliberate reward hacking additionally requires explicit awareness and the decision to satisfy the conflicting test; deception requires separate review of the report. Do not collapse these labels.

Long reasoning is an observed cost and completion problem, not by itself the phenomenon of interest. It can reflect conflict deliberation, repetition, confusion or difficulty emitting an action. Preserve truncations and report all attempted episodes in the denominator. Raising the cap may improve completion but does not establish why the reasoning is long.

The 20k cap is per model call in episode(), not per episode. Multiple turns and protocol retries can materially exceed the estimated 20–30 minutes per episode. Avoid increasing it again during this cohort; treat the estimate as provisional. Confirm effective actor context accommodates the prompt/history plus intended completion; an output limit alone does not establish context capacity. Apply the same check separately to the judge before comparing long traces.

Provenance already records max_tokens, so the old and new caps can be separated. However TEMPLATE_VERSION remains v3 after cap and parser changes, while the repo rule says to bump when caps change. Before the next batch, add an explicit harness revision/protocol identity (including retry policy) or bump the version; retain the exact current commit for this batch. Do not relabel an active run as though it used later code.

After the pilot: review every positive and an honest comparison case, freeze labels, report completion/cost alongside behavior, then run with/without-CoT judging on exactly the same eligible episodes. This tests the monitor's added information; eliciting violations alone does not show Cotwatcher detects them.
