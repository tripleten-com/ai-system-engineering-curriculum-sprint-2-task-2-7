"""Coldline.

===================

File:              tests/contract/test_retrieval_experiment.py
Component:         Contract tests — Controlled retrieval experiment
Purpose:           Verify the tuned parameter, the retained reports, and the decision.
Interacts With:    The retained benchmark reports, the published rule, tests/student
Sprint/Task:       Sprint 2 — Project 2 / Task 2.7
Concepts:          Controlled experiment, retained evidence, published decision rule
Tools:             Python 3.12, pytest

Every numeric answer is graded against the two retained reports, at the
published rounding precision, and never against a measurement taken now. A
report is validated against the supplied contract first, so a missing,
malformed, stale, or self-inconsistent report fails validation instead of
quietly becoming a decision.

What that establishes is consistency: these figures, this template, these
fixtures, that configuration, and the published rule applied to them. It is not
an authentication of the timings themselves, and no check here claims to detect
a self-consistent forgery of a local timing record.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.benchmark import policy
from tests.benchmark.compare import classification, decision
from tests.benchmark.config import (
    APPROVED_PARAMETERS,
    ConfigurationError,
    baseline_config,
    changed_parameter,
    experiment_config,
)
from tests.benchmark.metrics import CLASSIFICATIONS
from tests.benchmark.reports import (
    BASELINE_ARM,
    EXPERIMENT_ARM,
    ReportError,
    RetainedReport,
    impacted_query_ids,
    load_pair,
    report_path,
)
from tests.golden import query_ids
from tests.regression import CALL_LOG, recorded_calls

TASK_ROOT = Path(__file__).resolve().parents[2]
# `assessed`: a fresh starter has captured no reports, tuned nothing, and
# written no regression test.
# `runtime`: the reports these checks read are produced by a running system,
# and the student regression suite queries one.
pytestmark = [pytest.mark.runtime, pytest.mark.assessed]


def retained_reports() -> tuple[RetainedReport, RetainedReport]:
    """Return the two validated retained reports, or fail with what is wrong.

    Deliberately a function rather than a fixture. A starter has captured
    nothing, and that must show up as each check *failing* - the exercise state
    - rather than as a fixture error, which would look like broken
    infrastructure. Reading and validating two JSON documents is cheap enough to
    do per check.
    """
    try:
        return load_pair()
    except ReportError as exc:
        pytest.fail(str(exc))


def answers() -> dict[str, Any]:
    """Return the recorded answer mapping, or fail with what is missing."""
    document = yaml.safe_load((TASK_ROOT / "submission.yaml").read_text(encoding="utf-8"))
    mapping = document.get("answers") if isinstance(document, dict) else None
    if not isinstance(mapping, dict):
        pytest.fail("submission.yaml must define an answers mapping")
    return mapping


def recorded_text(field: str, permitted: tuple[str, ...]) -> str:
    """Return one recorded enumerated answer."""
    value = answers().get(field)
    if not isinstance(value, str) or value not in permitted:
        pytest.fail(f"answers.{field} must be one of {list(permitted)}; found {value!r}")
    return value


def recorded_number(field: str) -> float:
    """Return one recorded numeric answer."""
    value = answers().get(field)
    if isinstance(value, bool) or not isinstance(value, int | float):
        pytest.fail(f"answers.{field} must be a number read from a retained benchmark report")
    return float(value)


def test_exactly_one_approved_parameter_was_tuned() -> None:
    """One approved parameter differs from the baseline, and it is the one recorded."""
    recorded_parameter = recorded_text("selected_parameter", APPROVED_PARAMETERS)
    recorded_value = recorded_number("parameter_value")
    try:
        changed, value = changed_parameter(baseline_config(), experiment_config())
    except ConfigurationError as exc:
        pytest.fail(str(exc))

    assert changed == recorded_parameter, (
        f"config/student/retrieval.yaml changes {changed}, but answers.selected_parameter "
        f"records {recorded_parameter}"
    )
    assert value == pytest.approx(recorded_value), (
        f"config/student/retrieval.yaml sets {changed} to {value:g}, but "
        f"answers.parameter_value records {recorded_value:g}"
    )


def test_the_retained_reports_describe_the_configurations_on_disk() -> None:
    """Catch reports captured before the configuration files were last edited."""
    baseline, experiment = retained_reports()
    assert baseline.config == baseline_config().as_mapping(), (
        f"the retained baseline report measured {baseline.config}, and the supplied baseline "
        f"is {baseline_config().as_mapping()}"
    )
    assert experiment.config == experiment_config().as_mapping(), (
        f"the retained experiment report measured {experiment.config}, and "
        f"config/student/retrieval.yaml now says {experiment_config().as_mapping()}. Capture "
        "the experiment arm again after editing it."
    )


def test_both_retained_reports_measured_the_published_golden_set() -> None:
    """A comparison across two different evaluation sets would measure nothing."""
    baseline, experiment = retained_reports()
    assert baseline.fixture_id == experiment.fixture_id, (
        "the two retained reports ran against different golden evaluation sets"
    )
    assert baseline.query_ids == experiment.query_ids == query_ids(), (
        "the measured queries are not the published golden set"
    )
    assert baseline.run_id != experiment.run_id, (
        "both retained reports carry the same run identifier, so they are one capture "
        "presented as two"
    )


def test_the_experiment_capture_did_not_overwrite_the_baseline_report() -> None:
    """The baseline report must be the one its own capture wrote.

    The commands write one arm each, so this holds by construction. It is
    checked anyway: the retained baseline is the evidence an already recorded
    decision was graded against, and a later capture replacing it would change
    that evidence after the fact.
    """
    baseline, experiment = retained_reports()
    assert baseline.arm == BASELINE_ARM and experiment.arm == EXPERIMENT_ARM
    assert report_path(BASELINE_ARM) != report_path(EXPERIMENT_ARM), (
        "both arms resolve to one retained path, so an experiment capture would overwrite "
        "the baseline evidence"
    )
    assert baseline.document["arm"] == BASELINE_ARM, (
        f"{report_path(BASELINE_ARM).name} holds a report for the "
        f"{baseline.document['arm']!r} arm, so an experiment capture wrote over the baseline"
    )


def test_recorded_quality_metrics_match_the_retained_reports() -> None:
    """Recall@K is deterministic, so a recorded value either matches or is wrong."""
    baseline, experiment = retained_reports()
    places = policy.rounding().recall_places
    for field, retained in (
        ("baseline_recall_at_k", baseline.recall_at_k),
        ("experiment_recall_at_k", experiment.recall_at_k),
    ):
        recorded = recorded_number(field)
        assert round(recorded, places) == round(retained, places), (
            f"answers.{field} records {recorded:.{places}f}; the retained report holds "
            f"{retained:.{places}f}. Recall@K is computed from published binary labels and "
            "does not vary between runs."
        )


def test_recorded_latency_metrics_match_the_retained_reports() -> None:
    """The recorded latency must be the report's p95, not its median.

    Graded against the retained report rather than a fresh measurement, so this
    is an exact match at the published precision. That is what makes recording
    the median instead of the 95th percentile a detectable mistake: both are in
    the report under their own names, and only one of them matches.
    """
    baseline, experiment = retained_reports()
    places = policy.rounding().latency_places
    for field, report in (
        ("baseline_latency_ms", baseline),
        ("experiment_latency_ms", experiment),
    ):
        recorded = round(recorded_number(field), places)
        expected = round(report.latency_p95_ms, places)
        assert recorded == expected, (
            f"answers.{field} records {recorded:.{places}f} ms, and the retained "
            f"{report.arm} report holds a p95 of {expected:.{places}f} ms "
            f"(p50 {report.latency_p50_ms:.{places}f}, p99 {report.latency_p99_ms:.{places}f}). "
            "Record the p95 column of the arm you captured, in milliseconds."
        )


def test_recorded_classification_matches_the_retained_evidence() -> None:
    """The classification must be the one the two retained signals actually show."""
    baseline, experiment = retained_reports()
    recorded = recorded_text("agreement_classification", CLASSIFICATIONS)
    observed = classification(baseline, experiment)
    assert recorded == observed, (
        f"answers.agreement_classification records {recorded!r}; the deterministic metric "
        f"moved {experiment.recall_at_k - baseline.recall_at_k:+.3f} and the cached judge "
        f"relevance moved {experiment.judge_relevance - baseline.judge_relevance:+.3f}, which "
        f"is {observed!r}. Run `poe compare` and read the observed comparison outcome."
    )


@pytest.fixture(scope="module")
def student_regression_calls() -> Iterator[tuple[int, list[dict[str, object]]]]:
    """Run the student regression suite and return its exit status and assertions."""
    with tempfile.TemporaryDirectory(prefix="coldline-regression-") as temporary:
        log = Path(temporary) / "regression-calls.json"
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/student", "-q"],
            cwd=TASK_ROOT,
            env={**os.environ, CALL_LOG: str(log)},
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        yield result.returncode, recorded_calls(log)


def test_a_regression_test_asserts_the_ranking_of_an_impacted_query(
    student_regression_calls: tuple[int, list[dict[str, object]]],
) -> None:
    """One passing regression test must pin the ranking of a query the change affected."""
    returncode, calls = student_regression_calls
    assert returncode == 0, (
        "`pytest tests/student` does not pass. A regression test that fails is not a "
        "regression test yet."
    )
    assert calls, (
        "no regression assertion was recorded. Add a test under tests/student/ that calls "
        "tests.regression.assert_expected_ranking for a query your experiment affected."
    )

    published = set(query_ids())
    asserted = {str(call["query_id"]) for call in calls}
    unknown = sorted(asserted - published)
    assert not unknown, f"these are not published golden queries: {unknown}"

    impacted = set(impacted_query_ids(*retained_reports()))
    assert impacted, (
        "the tuned parameter changed nothing for any published query, so there is no "
        "regression for a test to pin. Choose a value that actually moves the retrieval "
        "result."
    )
    assert asserted & impacted, (
        f"the regression test asserts on {sorted(asserted)}, none of which your change "
        f"affected. The queries it affected are {sorted(impacted)}."
    )


def test_the_adoption_decision_follows_the_published_rule() -> None:
    """The recorded decision must be the one the published rule gives for this evidence.

    The rule is fixed and its constants are published; there is exactly one
    correct decision for a valid comparison. While the benchmark owner has not
    calibrated the latency budget and tolerance, this check fails and names
    that gate. It does not fall back to `revert`, which would award an answer
    the evidence was never tested against.
    """
    baseline, experiment = retained_reports()
    recorded = recorded_text("adoption_decision", policy.DECISIONS)
    try:
        verdict = decision(baseline, experiment)
    except policy.PolicyUnpublished as exc:
        pytest.fail(
            f"the adoption decision cannot be graded yet: {exc} Until then this check fails "
            "for every submission, correct or not, and Task 2.7 is not release-ready."
        )
    except policy.PolicyError as exc:
        pytest.fail(f"the published adoption policy is unusable: {exc}")

    assert recorded == verdict.decision, (
        f"answers.adoption_decision records {recorded!r}, and the published rule gives "
        f"{verdict.decision!r}: {verdict.reason}. Run `poe compare` for the rule applied to "
        "your retained reports."
    )
