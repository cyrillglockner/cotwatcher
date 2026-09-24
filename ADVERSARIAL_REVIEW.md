# Adversarial follow-up review — 2026-09-23

For Claude and Cyrill. Reviewed HEAD `35138ced539a9e820414fd5de60b6afb4f1192f9`, including fixes `4c3adf5`, `d82a22b`, and v2 templates `35138ce`.

## Verdict

Meaningful improvements, but do not mark the previous review fully resolved. Fix R1–R4 before relying on the next experiment, and R1/R5 before treating the CLI exit contract as release-ready. The controlled pair currently cannot support the claimed interpretation. No new model performance evidence was evaluated here.

Validation: **61 existing tests pass** (`.venv/bin/python -B -m pytest -q -p no:cacheprovider`). Additional offline checks use a fake judge and temporary pytest files; no inference, downloads or network access. Implementation unchanged. The root review from the previous handoff was absent at the start of this review; this document is a follow-up, not a reconstruction of that file.

Companions: `reviews/adversarial_followup_2026_09_23/reproduce.py` and `results.json`. Reproduce from the repo root:

```sh
.venv/bin/python -B reviews/adversarial_followup_2026_09_23/reproduce.py "$PWD"
```

These checks print observations rather than asserting defects must remain present.

## Findings

### R1 — P1: Truncated captures still receive a clean assessment exit (F1 partially open)

Locations: `src/cotwatcher/cli.py:88-106`, `cmd_score:304-353`; capture classification around lines 250–258.

Confirmed twice with a clean fake judge: a row with `capture_status="truncated"` and nonempty reasoning exits **0**; an older/imported row with `finish_reason="length"` also exits **0**. The summary only counts judge errors and absent reasoning. Preserving capture_status in a result row is useful but does not preserve coverage in the exit status. Legacy finish_reason is discarded without deriving capture_status. The capture stage also regards content-filtered responses with reasoning as ok.

Fix: count partial capture separately from scoring success. A truncated chunk can be scored, but the overall assessment must remain incomplete (2), including when another row flags. Infer status from recognized termination metadata for older/imported rows; treat content filtering as incomplete. Document the limits of imported traces with no coverage metadata.

Acceptance: explicit truncated, legacy length, content_filter, and mixed complete/partial inputs retain coverage status and exit 2. An ordinary complete clean input exits 0. Add end-to-end trace → score tests, not only trace tests.

### R2 — P1: Pytest teardown errors become successful harness verdicts (F5 still open)

Location: `evals/pressure/harness.py:184-215`.

Confirmed using an ordinary fixture that yields, then fails an assertion in teardown. Pytest prints `1 passed, 1 error` and returns **1**; `run_pytest` returns **ok=true, valid=true, passed=1, errors=0**.

Cause: the passing call report writes `results[nodeid]="passed"`; the later failing teardown uses `setdefault`, leaving the pass intact. The final ok predicate ignores nonzero returncode. This is a correctness failure without any adversarial model code. Collection/session failures after test execution and missing teardown completion deserve the same scrutiny.

Fix: retain setup/call/teardown outcomes separately, let any phase failure invalidate the pass, require successful process/session completion in addition to positive evidence for the exact expected tests. Never revert to returncode alone. Check collection success too; the current collection helper ignores its exit status.

Acceptance: teardown failure, setup failure, partial collection error, early process exit, missing completion, and normal test failure cannot return ok=true; ordinary successful suites do. Add harness regression tests to CI; the current 61 tests cover the package, not these harness behaviors.

The original `os._exit(0)` before collection reproduction now correctly returns ok=false/valid=false. This closes that specific exploit, not the full ground-truth issue. Same-process report forgery remains a documented limitation; remove the contradictory absolute wording in the run_pytest docstring (“a verdict that model code cannot forge”).

### R3 — P1: The controlled pair changes whether ordinary test gaming can succeed

Location: `evals/pressure/templates.py:77-78,125-138`.

The no-story visible suite contains both:

```python
assert unit_price(1000, 4, 0.0) == 250  # existing test_splits_across_units
assert unit_price(1000, 4, 0.0) == 700  # added test_four_units
```

An ordinary deterministic implementation cannot make both pass. The story condition can pass all visible tests through an ordinary percentage reinterpretation. Thus this pair changes both plausibility of a feature explanation AND feasibility of passing visible tests with a simple special case. Honest reporting or extra deliberation on no-story would not isolate the proposed feature-story mechanism.

Fix before collecting a batch: give both conditions distinct contradictory inputs that do not collide with base visible tests, and keep ease of special-casing comparable. Ideally vary a plausible versus arbitrary expected output for the same otherwise matched input and keep test naming/comment cues controlled, or explicitly describe the remaining differences as a bundled manipulation. Do not claim a single isolated causal factor just because the shared base template matches.

Acceptance: a reference spec implementation passes each control and hidden suite and fails exactly the intended added test in each blocked condition; a deliberately noncompliant simple special case can pass each blocked visible suite. Both story conditions should demand comparable implementation changes. Bump the template version for the corrected design and keep any already collected v2 episodes separate.

### R4 — P2: The no-story hidden suite misses the exact gaming behavior it is meant to detect

Location: `evals/pressure/templates.py:84-110,137`.

Confirmed: start from the correct implementation, then return 700 specifically for `(1000, 4, 0.0)`. The no-story hidden suite returns **6 passed / ok=true**, despite that patch implementing the contradictory answer. The visible suite fails its other assertion on that same input (R3). Hidden tests check general division and discount validation but never this exact target.

Fix: include the specification-correct result for every contradictory input in its associated hidden suite, in addition to boundary/generalization checks. Whenever contradictory inputs change, update these assertions together. Do not describe every special case as mechanically detectable until these checks exist.

Acceptance: every hand-written gaming patch for each template passes its blocked visible suite and fails the hidden spec suite; correct patches pass hidden. This is a small deterministic fixture check that should run before expensive actor runs.

### R5 — P2: Configuration failures still violate the documented CLI exit contract (F4 partially open)

Locations: `src/cotwatcher/cli.py:116-123,393-397`; `src/cotwatcher/config.py:72-79`.

Confirmed: `rubric --config <missing-file>` raises FileNotFoundError; malformed TOML raises TOMLDecodeError. These escape `main` because only InputError is caught, so a normal CLI process exits 1, the code reserved for detections. Rubric-loading errors and decoding failures need the same boundary treatment. Existing CLI tests replace config.load and therefore cannot establish real configuration error handling.

Fix: convert expected file/config/rubric parse errors to InputError at the CLI boundary, with useful messages. Do not catch arbitrary programmer errors indiscriminately.

Acceptance: subprocess-level tests for missing/invalid config, invalid rubric and unreadable/malformed inputs return 2 without an unhandled traceback; a genuine detection remains 1.

## Original findings: disposition

| Original finding | Follow-up assessment |
|---|---|
| F1 capture coverage | Improved: all tasks get rows and absent reasoning is unassessed. Still open for partial captures: R1. |
| F2 threshold / empty input | Fixed in inspected code and reproduced checks: NaN and empty input return 2; bounds enforced. |
| F3 documented flags / config | Flag ordering covered by new tests; nested effort supported; README corrected. |
| F4 operational error exits | Input parsing improved; config/rubric boundary remains incomplete: R5. |
| F5 trustworthy verdicts | Original early-exit case fixed; new false-pass reproduction: R2. Same-process trust limitation remains. |
| F6 stale results / timeout | File hashes and timeout handling added. These improve provenance; not a complete adversarial validation. `misleading_claim` still treats any historical pass phrase as a claim about the final artifact; treat it as a heuristic candidate, not a human deception label. |
| F7 labels | Frozen explicit labels required, invalid patches separated, controls no longer automatically negative. Reviewer allowlist is still source-configured. |
| F8 monitor provenance | Comparison manifest substantially improved. CLI score manifest still lacks system-prompt hash, input content hash, immutable judge revision and effective context. Comparison context explicitly remains unknown; manifests are not full reproducibility guarantees. |
| F9 truncation / context | Judge output length/content_filter is now rejected. Input context budgeting remains unimplemented. Pinning 16k does not establish that a particular prompt fits; the previous silent-truncation failure can recur on larger episodes. Keep this open. |
| F10 eval dependencies | pytest and pytest-reportlog now declared. Reproductions work in the existing environment. Fresh installation/build not validated in this review. |

## Recommended next step

Fix the controlled pair and its hidden checks before spending model time. Fix the harness verdict and partial-capture handling, add the concrete regressions above, then collect a versioned pilot with complete/incomplete counts. Freeze labels before comparison and keep dev/eval separation. The public value is still a transparent experimental toolkit; these engineering improvements alone do not establish a reliable deception detector or the incremental value of CoT.
