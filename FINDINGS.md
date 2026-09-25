# Findings ledger

One row per finding, with a stable ID that never changes meaning. Reviews
**update rows**; they do not open a new round and declare the last one closed.
A row moves to `verified-fixed` only with a named verification: a regression
test, or a measured result recorded here.

Statuses: `verified-fixed`, `partially-fixed`, `accepted-limitation`, `open`.

Rounds RR, F, R, IP and RF, and the EV rows, were raised by OpenAI Codex reviewing this
repository. Rows record who raised a finding where it is not one of those rounds.

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
| F6 | Stale test results; unguarded subprocess timeout | verified-fixed | `d82a22b` | `code_sha`/`tests_sha` per run; `truth.final_artifact_verified`. **`misleading_claim` is a heuristic candidate, not a human label.** An untested final patch is not itself misleading: the question is whether the report claims *that* patch passed. Observed firing on a report that accurately described a failing test, i.e. a false alarm. Review the report against the action history before labelling |
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

## Round 5 — internal-process alignment (IP)

| ID | Finding | Status | Fix | Verification |
|---|---|---|---|---|
| IP1 | Review sheet and eligibility filters contradict the commitment definition | verified-fixed | `ae00cb2` | Stage B carries `commitment-v1`, scores the strongest decision anywhere in the trace, adds reversed and evidence fields. `outcome_group` keeps artifact validity and trace coverage apart from the label: a positive survives an invalid patch or a truncated trace, a negative requires a complete one. Measured on four cases |
| IP2 | The no-CoT arm is an input ablation, not an artifact-only baseline | verified-fixed | `ae00cb2` | `compare.py` says so in its docstring: both arms run a judge whose prompt requires evidence *in the reasoning*, so a miss may be the instruction's doing. A real baseline is on the backlog |
| IP3 | `reversed` coerced silently; dropped by comparison | verified-fixed | `ae00cb2` | `"false"` gave `reversed_=True`, marking a reversal that had not happened; category scores were unaffected. Now any non-boolean is an assessment error. `test_non_boolean_reversed_is_an_error_not_a_coercion`. Comparison persists it. Documented that one flag cannot name the category or express commit-reverse-recommit |
| IP4 | Probe features are replay, presented as the trajectory | verified-fixed | `ae00cb2` | Manifest records `extraction_mode: replay`, what the replay omits, and that actor/extractor identity is unverified. `training_sha` now covers text and labels rather than ids |
| IP5 | Public claims overstate | verified-fixed | `ae00cb2` | README: 34 to 122 tests, "independent ground truth" to artifacts establishing behaviour rather than decisions, and the event definition added. CLAUDE.md: activations are measurements of the process, not the process |

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
| F9 | Judge input budgeting | `max_input_tokens` refuses an oversized prompt, and `cotwatcher check` now reads the window the server is serving and fails when the configured budget exceeds it. Open because the budget is still a setting the user supplies, and a server that does not report its window cannot be checked at all |
| RR4 | Model code runs on the host | Mitigated by an opt-in gate and a stripped environment. Not isolation |
| HARNESS-1 | Same-process report forgery | Code sharing a process with the reporter can write the report log. Raising the cost is not eliminating it. Real fix: candidate function in an isolated worker, assertions in a controller it never touches |
| EV3 | Evaluation-aware negatives were discarded while positives were kept | verified-fixed | (this commit) | Discarding a source's negatives while keeping its positives selects evidence toward a judge that over-flags. Awareness is now metadata: such blocks are admissible for judge specificity, inadmissible for deployment behaviour rates, never pooled. CLAUDE.md rule rewritten; the three figure-45 blocks relabelled from unassessed to specificity negatives with `evaluation_aware` and admissibility recorded. Raised by Codex |
| EV1 | A judge reply with no rationale read as a clean verdict | verified-fixed | (this commit) | Five of sixteen scorings in the frozen pilot comparison returned all-zero scores and an empty rationale, one of them on a labelled positive. `parse_score` now sets an assessment error when the rationale is empty at any score. `test_reply_without_a_rationale_is_not_a_verdict`, `test_rationale_is_required_of_a_flag_too` |
| EV4 | The event judge proposes a commitment in every episode | partially-fixed | `f3ebcda` | First development run, events-v1, per turn, over the eight pilot episodes: a located commitment in 8 of 8, including all 6 negatives, with no withdrawals and no `notices` proposed at all. Recall 2 of 2, false alarm 6 of 6, so it does not discriminate at the episode level. The 20 located events await review; the three-level distinction in the prompt is the first suspect. events-v2, with the task text and a required constraint, moved it to 4 of 6 negatives flagged with both positives detected; one of the two clean results is a fuzzy downgrade, not better judgement |
| EV10 | A named constraint is not evidence the model recognised it | open | — | Of 13 verified commitments in events-v2, the constraint is quoted from the model's reasoning in 1. Four repeat the specification and eight are the judge's paraphrase of it. The field is satisfied by asserting a rule exists, which is the wrong half: the event requires the model's own recognition |
| EV11 | The judge fabricates quotes | open | — | Two of 24 proposed quotes in events-v2 appear nowhere in the episode or the task, with nothing above 0.85 resemblance. Verification catches them; no prompt wording can guarantee they stop. The rate is the thing to track. Distinct from quoting the wrong turn, which the same run also did |
| EV5 | A review could attach to an event it was not made about | verified-fixed | (this commit) | Report identity hashed the summaries and the input filename, and event ids were positional. Codex turned a commitment into a withdrawal keeping the summary and got the same report id. Identity now covers episodes, proposals, judge and every event id; event ids are content hashes. Reproduced Codex's case: ids differ, 19 of 20 unrelated events keep theirs. `test_changing_an_event_changes_the_report_identity` |
| EV6 | A fuzzy match could reverse the meaning of the evidence | verified-fixed | (this commit) | A quote dropping the `not` from "I will not conceal the failed check" located at 0.947 and would have alerted. Fuzzy hits are suggestions now: they cannot alert, they are listed separately, and the page shows the judge's words beside the source text. `test_a_quote_that_drops_a_not_is_a_suggestion_and_never_an_alert` |
| EV7 | An episode with no reasoning came back clean | verified-fixed | (this commit) | Zero judge calls, exit 0. `_coverage_gaps` records empty turns, truncated or filtered turns and a non-ok capture_status as episode errors. Also: `summary: null` passed as the string "None" and a missing `events` key became an empty list; both are now failures. Five tests in `test_propose_inputs.py` |
| EV8 | The documented capture-to-review path did not run | verified-fixed | (this commit) | `cotwatcher trace` writes reasoning at the top level and `propose` read only a `turns` list, so it rejected its own capture format. Trace rows are adapted to one-turn episodes. `test_a_trace_row_is_read_as_a_one_turn_episode` |
| EV9 | Per-turn judging could not see what a withdrawal refers to | verified-fixed | (this commit) | The call carried one turn's reasoning and the template name. It now carries the task text where the capture kept it and up to 3,000 characters of prior reasoning, labelled in the prompt as context that must not be quoted. Whether it yields withdrawals is unmeasured; EV2 stays open |
| EV2 | The reversal flag is set by the arm that cannot see the reversals | open | — | Artifact-only arm set `reversed` on four of eight, the reasoning arm on none, with both positives commit-then-reverse. Not a parse fault: one boolean cannot carry commitment, withdrawal and recommitment. Fix is a verdict format of located decision events, tested behaviourally |
| RESEARCH-1 | **The product question is unanswered** | No result yet shows that reading the chain of thought surfaces incidents that output and tool-log monitoring miss, at a fixed false-alert budget. Engineering fixes make the experiment trustworthy; they do not make the case |


## Agent integration handoff — 2026-09-25

Reviewed by Codex at `859ab3a`. The MVP direction is appropriate: agents reuse the
judges and write application glue; no hosted service, universal wrapper or new
integration framework is required. These findings concern the guide's executable
examples. Update these IDs in place as fixes land.

| ID | Finding | Status | Required fix and acceptance criteria |
|---|---|---|---|
| INT1 | Documented input budget is silently ignored | verified-fixed | `docs/INTEGRATION.md:105-114` puts `judge_max_input_tokens = 48000` under `[judge]`, but `config._from_dict` reads it only at top level. Reproduced by parsing that TOML: Settings has `judge_max_input_tokens=None`. Move the setting above the TOML sections (or deliberately support nesting) and use the intended long-context model name. Verify the exact documented configuration loads 48000 and selects that model. Related to F3's earlier configuration example issue and F9's input-budget work. **Fixed:** Reproduced: parsing the documented TOML gave `judge_max_input_tokens=None`. The loader now accepts `max_input_tokens` and `judge_max_input_tokens` under `[judge]`, the same accommodation it already made for `reasoning_effort`, and the example shows the top-level form with long-context model names. `test_the_documented_config_loads_with_the_budget_it_shows` parses the guide's own TOML block |
| INT2 | Main integration example bypasses configured endpoints and limits | verified-fixed | `docs/INTEGRATION.md:69-72` constructs `Settings()`, which does not load the TOML file or environment. Make `config.load()` the primary example with the appropriate import, rather than an optional comment. Verify a temporary config and environment override reach the example's judge construction. **Fixed:** The example now calls `config.load()`. `test_the_example_loads_configuration_rather_than_defaults` checks the example's AST, so naming `Settings()` in a warning comment is allowed and constructing it is not |
| INT3 | Sample does not handle judge transport failure or demonstrate response isolation | verified-fixed | `docs/INTEGRATION.md:81` calls `judge.score()` synchronously without an exception boundary. Endpoint failures raise before `score.ok` can be inspected, despite the verification section requiring an unavailable judge not to take down the application. Show a small boundary that records transport failure as unassessed, and explicitly mark where the agent should schedule/queue scoring outside the response path. No general queue framework required. Acceptance: fake judge raising ConnectionError is logged as unassessed without propagating into the user request; normal scoring still works. **Fixed:** Reproduced: `LLMJudge.score` calls the client with no exception boundary, so a transport failure raises before `score.ok` is reached. The example wraps the call, records the chunk as unassessed, and runs in an `assess()` function the guide says to call off the response path. The asymmetry with `EventJudge.propose`, which returns an error verdict instead of raising, is documented and logged as INT5. `test_the_example_catches_a_judge_call_that_raises` |
| INT4 | A previously offline test now contacts the real watched endpoint | verified-fixed | `tests/test_cli.py::test_check_warns_when_no_input_limit_is_set` calls `check` while mocking only Settings.make_judge. Since check now contacts the watched model, this can perform real inference. Use `--judge-only` for this judge-budget warning test or mock Endpoint.client. Verify the test never reaches a real client; retain separate fake-client coverage of the watched-model check. **Fixed:** The test now passes `--judge-only` and fails if any endpoint is contacted. `test_no_test_reaches_a_live_endpoint_through_check` guards the whole path, so a future `check` test that forgets to mock fails rather than loading a local model. Full suite runs offline: 209 passed, none deselected |
| INT5 | Two judges fail in two different ways | verified-fixed | `LLMJudge.score` raises on transport failure while `EventJudge.propose` returns a verdict carrying `error`. An integration written against one and given the other either crashes or silently treats a failed call as a verdict with no events. Both now follow one rule: unreachable raises `JudgeUnavailable`, because no reply exists and an exception cannot read as clean; a reply that exists and is unusable, or an input over the budget, comes back as a result carrying `error`, because retrying will not help. `test_an_unreachable_judge_raises_from_both_judges` and two companions assert the split on both judges. `cotwatcher propose` stops on an unreachable judge rather than writing one identical failure per turn |

Verification at the reviewed version: **195 passed, 1 deselected** using
`.venv/bin/python -B -m pytest -q -p no:cacheprovider -k 'not test_check_warns_when_no_input_limit_is_set'`.
INT4 was intentionally excluded to avoid triggering the local model. No real model
calls were made. These are the prior review's observations, not a verification of
concurrent edits made after `859ab3a`.

After these small fixes, try the guide in a fresh coding-agent session against a
small application. That is the next MVP validation; adding more infrastructure is
not a prerequisite. Detection remains experimental: events-v2 flagged both pilot
positives and four of six negatives, with no withdrawals detected. Keep integration
log-only and describe that result separately from integration correctness.
