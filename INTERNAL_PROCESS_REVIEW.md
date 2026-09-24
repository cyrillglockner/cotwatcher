# Internal-process alignment review — 2026-09-24

For Claude and Cyrill. Reviewed `b719e94bacfe43dbd787d445486e68f100bb514a` read-only. **113 tests pass**. No models loaded, generations requested, private external transcripts read, or labels assigned. This review concerns propagation of the new target into evaluation, not a request to turn the product into an output grader.

## What is already aligned

The judge prompt now targets deciding to pursue rubric-defined behavior, distinguishes consideration from commitment, and retains commitments followed by reversal. CLI results serialize the reversal. PLAN correctly distinguishes 18 disclosure outcomes from 18 internal-process negatives and acknowledges that probe activations are not privileged evidence of intent. These are implemented improvements; do not redo them.

## IP1 — P1: Freeze labels only after aligning the review sheet and eligibility policy

`evals/pressure/examples/REVIEW_v3p2.md`, Stage B, still asks whether the model “knowingly satisfy[ied]” the test and says choosing the spec is 0. It has no explicit commitment-then-reversal instruction or fields for evidence spans and reversal. That wording can assign a negative to exactly the case the new judge must flag. The two-stage artifact/reasoning review remains useful, but Stage B must refer to the strongest supported commitment anywhere in the trace, not just what survived into the final patch/report.

`evals/pressure/compare.py::outcome_group` also still treats any unfinished episode as ineligible and any invalid final patch as excluded. Those filters made sense for some outcome questions; neither implies that a prior reasoning commitment cannot be observed. A truncated trace can support a positive commitment, while absence of one in the partial trace cannot establish a full-episode negative.

Action: record the label-definition version, category-specific commitment evidence, reversal/recommitment evidence, and trace coverage independently from artifact validity/completion. Keep unknown and partial distinct from negative. Preserve old frozen labels under their historical definition; explicitly re-review before using them to evaluate the changed target. If comparison stays completed-only, label that restriction clearly and do not generalize it to all commitments.

Acceptance: notices-and-rejects is 0; commits-and-reverses retains the category positive plus reversal; a later syntax error does not erase an observed commitment; incomplete no-event traces are not clean negatives. Review forms and persisted labels must support these distinctions before freezing this pilot.

## IP2 — P1: The no-CoT comparison needs an honest interpretation

`compare.py` uses the same LLMJudge for both arms. Its SYSTEM_PROMPT expressly audits private reasoning, and the deception rubric requires awareness plus decision “in the reasoning.” The no-CoT arm supplies artifacts under that same reasoning-oriented instruction. This is a useful input ablation, but it is not automatically a competent artifact-only baseline. A miss may reflect the instruction to require unavailable evidence, rather than the inability of artifacts to support the inference.

Keep this separate from product scope: an experimental artifact baseline does not make Cotwatcher an output grader.

Action: either describe the current comparison precisely as “the same reasoning judge with reasoning removed,” or add a separately declared evidence-appropriate baseline that targets the same commitment event, uses only its available artifacts, and can abstain on unsupported intent. For example, an explicit final-report admission may establish a choice, while an unexplained coding defect does not. Do not require the baseline to invent internal events invisible in its evidence. Save each arm's prompt identity. Human commitment labels derived from CoT are evidence about expressed commitments, not independent proof of hidden intent.

Acceptance: the baseline is allowed to recognize an explicit admission; uncertainty is separate from a clean verdict; published claims distinguish this ablation from a comparison with a capable output/tool-log monitor. No real judge calls made in this review, so this is a design concern, not a measured baseline failure.

## IP3 — P2: Reversal data is lossy and not strictly parsed

`src/cotwatcher/judge.py::parse_score` uses `bool(data.get("reversed", False))`. Confirmed offline: JSON `"reversed": "false"` produces `ok=True, reversed_=True`; null, list and numeric values are also silently coerced. `evals/pressure/compare.py` drops s.reversed_ entirely when persisting both scores, despite the CLI preserving it.

Action: validate a supplied reversal value as a JSON boolean, retain a documented legacy missing-field policy, and serialize it in comparison output. A single boolean cannot indicate which category reversed or distinguish commit→reverse from commit→reverse→recommit; preserve event evidence/order or state that limitation explicitly. “Ever reversed” must not be presented as “currently withdrawn.”

Acceptance: true/false survive parser and comparison round-trip; malformed values produce an assessment error; the known recommitment episode is not summarized as simply resolved. Existing tests check parser defaults and prompt wording, not behavioral generalization.

## IP4 — P2: Probe episodes replay a different context; identify them accordingly

`evals/probe/activations.py` correctly documents a fresh forward pass over supplied text. `score_episodes.py::episode_chunks` supplies only the opening prompt and the turn's reasoning, with context always empty. For later turns this omits intervening assistant actions and tool observations that conditioned the actor. The model is also loaded separately through Hugging Face; the docstring's actor/probed-model compatibility requirement is not enforced by code.

These vectors are valid replay features, but not a recording of the original trajectory's hidden states. Same model family/name alone does not establish identical weights, quantization, tokenization or context. Do not interpret a disagreement as locating a concealed decision in the original generation.

Action: explicitly mark extraction mode as replay and record omitted history/actor-versus-extractor identity in outputs. Check supported actor/extractor mappings before expensive extraction. If generation-equivalent replay becomes necessary, reconstruct the actual messages/tokens and verify the relevant execution differences; live capture is a separate milestone, not required to retain this exploratory classifier.

Also, training_sha hashes only record IDs: editing training text or labels under the same IDs leaves the manifest unchanged. Hash the actual training contents and label-definition version. Mark existing probe performance as evaluated against its historical labels until commitment/reversal cases have been audited. Test the new boundary on held-out consideration, commitment and reversal examples, not just the worked examples used to tune the judge.

## IP5 — P2: Carry the improved language into the remaining claims

CLAUDE.md still says “activations are the process,” although PLAN adds the necessary measurement caveat. README still says the pressure harness provides independent ground truth without distinguishing executed behavior from internal commitment. PLAN's assertion that an outcome-verified, unmentioned hint demonstrates what a probe can do is also stronger than the evidence: used-and-unsaid is not necessarily knowingly concealed.

Action: keep one precise current statement: the text judge evaluates expressed reasoning commitments; the experimental probe classifies replay activation features; actions/outcomes corroborate behavior but do not independently establish every internal commitment or its intent. Older results and plans can remain historical with explicit dates/supersession. README's “34 tests” is also stale (113 passed here).

## Next step

Update the labeling sheet and interpretation of the two comparison arms before spending on evaluation. Freeze versioned labels, preserve reversal evidence, then assess both tools against the new event definition. Do not regenerate the pilot simply because the label target has sharpened: its existing full traces are useful material for re-review. None of these findings licenses calling the 18 disclosures negatives without reviewing their reasoning.
