# Task 2.7 — Controlled retrieval experiment contract

Change exactly one approved retrieval parameter, measure both configurations against the same
golden evaluation set, compare the deterministic metric with the cached judge evidence, add one
regression test, and record a decision the evidence supports.

## The two approved parameters

| Parameter | What it changes | Range |
|---|---|---|
| `top_k` | How many fused candidates the retriever returns | whole number, 1 to 12 |
| `fusion_weight` | The weight the dense arm carries in reciprocal-rank fusion; the sparse arm carries the remainder | number, 0.0 to 1.0 |

Change **one** of them, in `config/student/retrieval.yaml`, and leave the other exactly as it is.
Nothing else is an approved variable: not the embedding, not the chunking, not the candidate pool.

`top_k`'s upper bound is the fixed candidate pool each arm fetches before fusion. A larger value
could not be satisfied, so the configuration loader rejects it rather than quietly returning fewer
results than you asked to measure.

## Why one variable

With two parameters moving at once, no measured shift can be attributed to either. That is not a
style preference: the harness refuses to report a comparison when both differ from the baseline,
and names both.

## The two evaluation signals

**Deterministic Recall@K is authoritative.** For each published query, every chunk of that query's
target document is labelled relevant and no other chunk is. Recall@K is the proportion of those
labelled chunks that the arm retrieved, averaged over the golden set. No literal word or token
matching is involved, and the result does not vary between runs.

**The cached judge evidence is comparison-only.** `infra/judge/cached-judgements.jsonl` holds a
relevance and a faithfulness score for each (query, chunk) pair, produced once by a recorded
heuristic and never recomputed. It is a stand-in for a model-based evaluator so that a local run
can show two evaluation signals diverging without a billable API call. It is never authoritative,
and it has no vote in the adoption policy below.

The two measure different things. The deterministic metric asks how much of the labelled relevant
material was found; the judge asks how well each retrieved passage covers the question. Expect them
to disagree under some configurations. That is a finding to classify, not a defect to fix, and
neither signal is a correction of the other.

No test may call a live, external, or billable model API.

## Commands

```shell
poe start                  # rebuild and start the stack
poe ingest                 # load the corpus
poe benchmark-baseline     # measure the supplied baseline, retain .benchmark/baseline.json
poe benchmark-experiment   # measure your configuration, retain .benchmark/experiment.json
poe compare                # read both retained reports, add the judge comparison, apply the rule
poe benchmark-reproduce    # re-measure and print the drift; writes nothing, grades nothing
poe experiment             # start, ingest, then this Task's assessed checks
```

## The two retained reports

Each capture writes exactly one report, and the two paths are fixed:

| Path | Written by | What it is |
|---|---|---|
| `.benchmark/baseline.json` | `poe benchmark-baseline` | The supplied control arm, measured |
| `.benchmark/experiment.json` | `poe benchmark-experiment` | Your configuration, measured |

**Commit both.** They are required run artifacts: every numeric answer is graded against them, and
the CMS grading integration reads them too. They are *generated*, not written by hand — the harness
produces them and nothing else should. That is why they are listed apart from the student-editable
paths at the end of this page, and why `docs/contracts/benchmark-report.schema.json` publishes
exactly what a valid report contains.

An experiment capture never writes the baseline path. Neither capture overwrites an existing report
for its own arm unless you pass `--recapture`, and recapturing the baseline discards the experiment
report with it — a baseline measured now and an experiment measured before it are not a comparison.

The order is: capture the baseline **before** you change anything, then change one approved
parameter, then capture the experiment.

**Missing or invalid reports fail validation.** They do not quietly become a `revert`. A report is
rejected when it is absent, unreadable, produced by another template or an older harness, records a
failed query, describes a configuration your files no longer contain, ran against a different
golden set, or disagrees with its own per-query rows. Every one of those cases names itself.

What that validation establishes is *consistency*: these figures, this template, these fixtures,
that configuration, and the published rule applied to them. It does not authenticate a wall-clock
measurement, and nothing here claims to.

Re-measuring with `poe benchmark-reproduce` is safe and never changes what you are graded against.
Recall@K should reproduce exactly, because it is deterministic. The latency percentiles will not,
and exact equality across runs is not required anywhere.

## How latency is measured

Twenty-two requests are executed against the configuration and discarded, because the first
requests of a run pay for connection setup, query planning, and byte compilation rather than for
retrieval. Each of the 11 published queries is then measured 15 times, and the percentiles are
taken over all 165 samples of that arm — nearest-rank, with no interpolation, so a reported
percentile is a sample that was actually measured.

The report prints **p50, p95, and p99 as separately labelled columns**. Record the **p95** column,
in **milliseconds**.

Your recorded value is compared with the retained report **exactly**, at the published precision of
one decimal place. That is possible because it is compared with the report you captured rather than
with a measurement taken at grading time — so recording the median where the p95 was asked for is a
mistake the check catches: both figures are in the report under their own names, and only one of
them matches.

The p95 itself is not reproducible between captures. Measured repeatedly on one idle machine, this
harness produced p95 values from 8.4 ms to 50.6 ms for the *same* configuration: the whole
distribution moves with whatever else the host is doing. The two arms are captured by separate
commands, minutes apart, so that drift sits between them. Nothing here pretends otherwise — it is
exactly why the published latency tolerance below has to be calibrated from repeated runs on the
supported environments rather than guessed.

On this corpus, changing either parameter is expected to leave p95 latency roughly unchanged: both
arms issue the same two queries and fetch the same fixed candidate pool, so only what fusion
selects differs. The latency axis is measured and recorded anyway, so that a change which *does*
cost latency would be visible rather than invisible.

## The comparison classification

`poe compare` reports how the two aggregate signals moved relative to each other. Record the
outcome it names:

| Classification | Meaning |
|---|---|
| `agreement` | Both signals moved, in the same direction |
| `disagreement` | Both signals moved, in opposite directions |
| `mixed_or_no_change` | Neither moved, or only one did |

"Moved" means moved by at least half a unit in the last published decimal place — the smallest
difference a three-decimal report can express. Nothing in this classification infers *why* the
signals moved; direction is all it claims.

## The published decision rule

There is one decision rule, it is published in `config/adoption-policy.yaml`, and it is not a
matter of judgment. With `R0`/`R1` the two arms' Recall@K and `L0`/`L1` their p95 latencies in
milliseconds:

```text
keep = (R1 >= R0) and (L1 <= B) and ((R1 > R0) or ((L0 - L1) > T))
```

and `revert` for every other valid comparison. `B` is the published latency budget and `T` the
published positive latency tolerance.

Three parts of that are worth reading twice:

- **Equality with the budget is allowed.** An experiment that lands exactly on `B` has met it.
- **Equality with the tolerance is not.** With recall unchanged, a latency improvement has to
  *exceed* `T` to carry a keep on its own.
- **A recall loss is never accepted**, however much faster the experiment is.

Every figure enters the rule at the published precision — three decimals for recall, one for
latency — so a difference in a place the report does not print cannot decide the outcome. The
rounding convention is published in the same file.

The cached judge has no vote. `policy.decide` takes no judge argument at all, which is the
guarantee rather than a promise about it.

This is a bounded teaching policy, not a claim that it is the best production decision in every
setting. The broader trade-off is where Task 2.9 picks the subject up.

### `B` and `T` are not published yet

The benchmark owner calibrates them from repeated runs on the supported environment profiles and
publishes them, with the procedure and the variability observed, before release. Until then
`config/adoption-policy.yaml` records `published: false`, `poe compare` prints `BLOCKED` instead of
a decision, and the check that grades `answers.adoption_decision` fails for **every** submission,
correct or not.

That is a release gate on this Task, not a mistake in your work. It is deliberate: grading a
decision against an invented budget would teach a number nobody stands behind, and defaulting an
ungradeable comparison to `revert` would award whichever answer happens to be more common. Record
the decision the rule gives for your own figures, and say in your pull request which constants you
assumed.

## The regression test

Add one test under `tests/student/` that pins the ranking of a query your experiment affected, and
make the assertion through the supplied helper:

```python
from tests.regression import assert_expected_ranking


def test_spill_notification_still_ranks_the_hazmat_rule() -> None:
    assert_expected_ranking(
        "q-spill-notification",
        ["rule-hazmat-spill#0000", "playbook-vehicle-breakdown#0001"],
    )
```

The expected value is the **complete ranked list of chunk identifiers**, in order, that the query
returns under your experimental configuration. Read it from the `retrieved_chunk_ids` field for
that query in the retained `.benchmark/experiment.json`.

Writing the whole ranking down is the point. A test asserting only that something came back would
still pass after a change that reordered the answer, which is exactly the degradation a regression
test exists to catch.

The check requires three things: `pytest tests/student` passes, at least one assertion was made
through the helper, and at least one of the queries asserted on is a query your change actually
affected. `poe compare` prints that list of affected queries. A query is
affected when the change altered either what was retrieved for it or its deterministic recall.

## The answers

| Field | Type | Evidence source |
|---|---|---|
| `selected_parameter` | `top_k` or `fusion_weight` | `config/student/retrieval.yaml`, compared with the baseline |
| `parameter_value` | number | the value in that file |
| `baseline_recall_at_k` | 0.000 to 1.000 | `recall_at_k` in `.benchmark/baseline.json` |
| `experiment_recall_at_k` | 0.000 to 1.000 | `recall_at_k` in `.benchmark/experiment.json` |
| `baseline_latency_ms` | milliseconds, 1 decimal | `latency_p95_ms` in `.benchmark/baseline.json` |
| `experiment_latency_ms` | milliseconds, 1 decimal | `latency_p95_ms` in `.benchmark/experiment.json` |
| `agreement_classification` | `agreement`, `disagreement`, `mixed_or_no_change` | the observed comparison outcome from `poe compare` |
| `adoption_decision` | `keep` or `revert` | the published rule above, applied to your two retained reports |

## What the checks verify

| Check | What it looks at |
|---|---|
| `test_exactly_one_approved_parameter_was_tuned` | The two configuration files, and whether the recorded parameter and value are the ones that actually differ |
| `test_the_retained_reports_describe_the_configurations_on_disk` | Each retained report against the configuration file it claims to have measured |
| `test_both_retained_reports_measured_the_published_golden_set` | The fixture digest, the measured query identifiers, and that the two reports are two captures |
| `test_the_experiment_capture_did_not_overwrite_the_baseline_report` | That the baseline path still holds a baseline report |
| `test_recorded_quality_metrics_match_the_retained_reports` | Both recorded Recall@K values against the retained reports, exactly |
| `test_recorded_latency_metrics_match_the_retained_reports` | Both recorded p95 values against the retained reports, exactly at one decimal place |
| `test_recorded_classification_matches_the_retained_evidence` | The classification recomputed from the two retained signals |
| `test_a_regression_test_asserts_the_ranking_of_an_impacted_query` | Your `tests/student/` run, the assertions it recorded, and whether their queries were affected |
| `test_the_adoption_decision_follows_the_published_rule` | The recorded decision against the published rule. **Blocked until `B` and `T` are published**, and until then it fails for every submission |

`tests/contract/test_benchmark_reports.py` is separate and assesses nothing: it checks that a
missing, malformed, stale, or self-inconsistent report is rejected rather than turned into a
decision. `poe report-contract` runs it, and it needs no container.

## Student-editable paths

- `config/student/retrieval.yaml`
- anything you add under `tests/student/`
- `submission.yaml`

Those three are written by hand. Two more paths are permitted in your pull request but are
**generated**, not editable:

- `.benchmark/baseline.json`
- `.benchmark/experiment.json`

The harness writes them and nothing else should. Editing one by hand is not a boundary the checks
can police, and they say so plainly rather than implying otherwise — what they do police is that a
report matches the published contract, this template, this pinned harness version, the live golden
set, and the configuration on disk, and that it agrees with its own per-query rows.

`config/adoption-policy.yaml`, `config/benchmark-template.yaml`, `config/retrieval-baseline.yaml`,
`infra/corpus/`, `infra/judge/`, `tests/benchmark/`, `tests/regression.py`, `tests/golden.py`, and
the whole of `src/` are protected. The harness is what makes two configurations comparable, so
changing it would change the measurement rather than the system being measured. The policy file
carries the published rule and is calibrated by the benchmark owner, not tuned per submission.
