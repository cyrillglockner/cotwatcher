# Findings ledger

One row per finding, with a stable ID that never changes meaning. Reviews
**update rows**; they do not open a new round and declare the last one closed.
A row moves to `verified-fixed` only with a named verification: a regression
test, or a measured result recorded here.

Statuses: `verified-fixed`, `partially-fixed`, `accepted-limitation`, `open`.

A finding that a later review reopens keeps its original ID and gains a
`reopened as` note. Counting entries is not counting distinct problems: RR1,
F4 and R5 are three entries about one thing.

## Summary

26 review entries. Three problems were each raised twice, so those 26 entries
cover **22 distinct problems**: exit-code semantics is RR1, F4 and R5; capture
coverage is F1 and R1; the harness verdict is F5 and R2. Counting entries is
not counting problems.

| Status | Review entries | |
|---|---|---|
| verified-fixed | 23 | a named test or a measured before/after |
| partially-fixed | 2 | F8, F9 |
| accepted-limitation | 1 | RR4 |

Two further items are tracked in **Open** and were never review findings:
`HARNESS-1` (same-process report forgery) and `RESEARCH-1` (the product
question).

## Round 1 — release readiness (RR)

| ID | Finding | Status | Fix | Verification |
|---|---|---|---|---|
| RR1 | Exit codes do not separate "incomplete" from "flagged" | verified-fixed | `b1dc3d4` | Reopened as F4 and R5; see those rows |
| RR2 | Headline promises streaming and halting, which do not exist | verified-fixed | `b1dc3d4` | README leads with what installs; roadmap separated |
| RR3 | No `[evals]` extra; first command needs invented input | verified-fixed | `b1dc3d4` | `examples/traces.jsonl`; extended by F10 |
| RR4 | The pressure harness runs model-written Python on the host | accepted-limitation | `b1dc3d4` | Opt-in gate `COTWATCHER_ALLOW_CODE_EXECUTION=1`, minimal subprocess env. **A temp directory is not a sandbox and the docs say so.** Real fix is an isolated worker |
| RR5 | Release workflow does not gate on tests | verified-fixed | `b1dc3d4` | `release.yml` runs the 3.11/3.12/3.13 matrix and a clean-wheel smoke test before publish |

## Round 2 — adversarial review (F)

| ID | Finding | Status | Fix | Verification |
|---|---|---|---|---|
| F1 | Trace capture reports success despite missing reasoning | verified-fixed | `4c3adf5` | Reopened as R1 for partial captures. `test_trace_records_a_row_for_every_task_including_failures` |
| F2 | Non-finite threshold disables all alerts; empty input passes | verified-fixed | `4c3adf5` | `test_non_finite_or_out_of_range_threshold_is_rejected`, `test_empty_jsonl_is_incomplete_not_clean`. Measured: `-t nan` went exit 0 with no alerts → exit 2 |
| F3 | Documented `--rubric` and nested effort key do not work | verified-fixed | `4c3adf5` | `test_rubric_flag_works_after_the_subcommand`, `test_rubric_flag_still_works_before_the_subcommand`; nested `reasoning_effort` loads |
| F4 | Input failures exit 1, the code meaning "flagged" | verified-fixed | `4c3adf5` | Reopened as R5 for config/rubric errors. `test_malformed_records_exit_incomplete_not_flagged` |
| F5 | Pytest exit code is forgeable by `os._exit(0)` | verified-fixed | `d82a22b` | Reopened as R2 for teardown failures. `test_no_route_to_a_forged_or_accidental_pass` covers 7 routes |
| F6 | Stale test results; unguarded subprocess timeout | verified-fixed | `d82a22b` | `code_sha`/`tests_sha` per run; `truth.final_artifact_verified`. **`misleading_claim` is a heuristic candidate, not a human label** |
| F7 | Null labels counted as negatives; invalid patches counted | verified-fixed | `d82a22b` | Measured: `frozen+label null` → `unreviewed`, `invalid_patch` → `excluded_invalid_patch`. Reviewer allowlist is source-configured |
| F8 | Saved results do not identify the monitor | partially-fixed | `d82a22b`, `f8002a7` | Manifests in trace/score/compare with rubric and system-prompt hashes. **Immutable judge revision and effective context are still recorded as `unknown`** |
| F9 | Truncated judge reply accepted as a verdict | partially-fixed | `4c3adf5` | `test_truncated_judge_reply_is_not_a_verdict`. **Output truncation only. Oversized judge *input* is unbudgeted: pinning 16k does not prove a given prompt fits** |
| F10 | Evals extra omits the harness's test runner | verified-fixed | `d82a22b` | `pytest` and `pytest-reportlog` declared; CI installs `[dev]` and runs the harness tests |

## Round 3 — follow-up review (R)

| ID | Finding | Status | Fix | Verification |
|---|---|---|---|---|
| R1 | Truncated captures still exit 0 (reopens F1) | verified-fixed | `f8002a7` | `test_partially_captured_chunks_never_exit_clean`, `test_partial_capture_dominates_a_flag`, `test_trace_to_score_end_to_end_with_mixed_capture` |
| R2 | Teardown failure recorded as a pass (reopens F5) | verified-fixed | `f8002a7` | Measured: teardown case went `ok=True` → `ok=False`; per-phase outcomes plus return-code agreement. `test_a_pass_must_agree_with_the_exit_code` |
| R3 | The controlled pair was unsatisfiable by construction | verified-fixed | `f8002a7` | `test_gaming_passes_visible_tests_and_fails_hidden`; verified it rejects the broken v2 design. **Still a matched exploratory comparison, not clean isolation** (see RF4) |
| R4 | Hidden suites blind to the gaming they targeted | verified-fixed | `f8002a7` | Every contradictory input has its spec-correct answer pinned; `tests/test_templates.py` asserts it per template |
| R5 | Config and rubric errors exit 1 (reopens F4) | verified-fixed | `f8002a7` | `tests/test_cli_subprocess.py` asserts real process exit codes with no endpoint involved |

## Round 4 — run feedback (RF)

| ID | Finding | Status | Fix | Verification |
|---|---|---|---|---|
| RF1 | Actor served with 4,096 tokens of context | verified-fixed | `34b79f8`, `f2f9878` | Measured: `/api/ps` reports 4096 for `qwen3:8b`, 32768 for `qwen3:8b-32k`; harness refuses to start on the former. `test_context_check_reads_the_loaded_instance_not_the_architecture` |
| RF2 | `max_tokens` is per call, not per episode | verified-fixed | `34b79f8` | Provenance records `note_max_tokens`; per-episode time estimates stated as provisional |
| RF3 | Protocol changes did not bump a version | verified-fixed | `34b79f8` | `run_id` carries `PROTOCOL_VERSION` beside `TEMPLATE_VERSION`; batches cannot be pooled |
| RF4 | The pair is sold as clean isolation | verified-fixed | `34b79f8` | PLAN and `templates.py` describe it as a matched exploratory comparison and name the residual differences |
| RF5 | Two per cell cannot establish a rate or pressure effect | verified-fixed | `34b79f8` | Recorded as a pilot; every attempted episode stays in the denominator |
| RF6 | "Long reasoning is the phenomenon" was overreach | verified-fixed | `34b79f8` | Corrected in PLAN: it is a cost and completion problem with several possible causes |

## Open

| ID | Finding | Why it is still open |
|---|---|---|
| F8 | Monitor identity incomplete | Judge revision and effective context cannot be queried from the endpoint; recorded as `unknown` rather than guessed |
| F9 | Judge input budgeting | Nothing bounds a judge prompt against the judge's context. The failure it prevents (silent front-truncation discarding the rubric) already happened once |
| RR4 | Model code runs on the host | Mitigated by an opt-in gate and a stripped environment. Not isolation |
| HARNESS-1 | Same-process report forgery | Code sharing a process with the reporter can write the report log. Raising the cost is not eliminating it. Real fix: candidate function in an isolated worker, assertions in a controller it never touches |
| RESEARCH-1 | **The product question is unanswered** | No result yet shows that reading the chain of thought surfaces incidents that output and tool-log monitoring miss, at a fixed false-alert budget. Engineering fixes make the experiment trustworthy; they do not make the case |
