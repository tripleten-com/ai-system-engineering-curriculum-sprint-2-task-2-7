"""Coldline.

===================

File:              tests/unit/benchmark/test_adoption_rule.py
Component:         Unit tests — Published adoption rule
Purpose:           Qualify the published keep-or-revert rule against stated constants.
Interacts With:    tests/benchmark/policy.py and config/adoption-policy.yaml
Sprint/Task:       Sprint 2 — Project 2 / Task 2.7
Concepts:          Published decision rule, boundary behavior, fail-closed gating
Tools:             Python 3.12, pytest

These tests qualify the *implementation* of the rule. The constants they use
are stated here as fixtures, not read from the published policy, so the rule
can be exercised at and around its boundaries before anyone has calibrated a
budget.

They are not the calibration qualification. ADR009-R04 requires at least one
keep case and one revert case qualified end to end against retained reports on
the supported environment profiles, with the real published constants. That
remains a release gate and these tests do not discharge it: the file the rule
reads still records `published: false`, and the check that applies it to a
submission still fails while it does.
"""

from __future__ import annotations

import pytest

from tests.benchmark import policy

# Stated for these tests only. A budget of 40 ms and a tolerance of 2 ms are
# plausible for this harness and are deliberately not written into
# config/adoption-policy.yaml: choosing them there would be inventing the
# calibration this Task is blocked on.
BUDGET_MS = 40.0
TOLERANCE_MS = 2.0

POLICY = policy.AdoptionPolicy(
    latency_budget_ms=BUDGET_MS,
    latency_tolerance_ms=TOLERANCE_MS,
    recall_places=3,
    latency_places=1,
)


def outcome(
    baseline_recall: float,
    experiment_recall: float,
    baseline_latency_ms: float,
    experiment_latency_ms: float,
) -> policy.Decision:
    """Return the rule's decision for one comparison under the stated constants."""
    return policy.decide(
        baseline_recall=baseline_recall,
        experiment_recall=experiment_recall,
        baseline_latency_ms=baseline_latency_ms,
        experiment_latency_ms=experiment_latency_ms,
        policy=POLICY,
    )


def test_a_recall_gain_within_budget_is_kept() -> None:
    """The qualified keep case: quality improves and the latency budget is met."""
    assert outcome(0.700, 0.780, 30.0, 34.0).decision == policy.KEEP


def test_a_recall_loss_is_reverted_however_much_faster_it_is() -> None:
    """The qualified revert case: the rule never accepts a recall loss."""
    assert outcome(0.780, 0.700, 34.0, 5.0).decision == policy.REVERT


def test_a_recall_gain_outside_the_budget_is_reverted() -> None:
    """A quality gain does not excuse missing the latency budget."""
    assert outcome(0.700, 0.900, 30.0, BUDGET_MS + 0.1).decision == policy.REVERT


def test_equality_with_the_budget_is_allowed() -> None:
    """Landing exactly on the budget has met it."""
    assert outcome(0.700, 0.780, 30.0, BUDGET_MS).decision == policy.KEEP


def test_flat_recall_needs_a_latency_gain_beyond_the_tolerance() -> None:
    """With recall unchanged, only a latency improvement above T carries a keep."""
    assert outcome(0.700, 0.700, 30.0, 30.0 - TOLERANCE_MS - 0.1).decision == policy.KEEP


def test_equality_with_the_tolerance_is_not_enough() -> None:
    """The tolerance must be exceeded, not merely matched."""
    assert outcome(0.700, 0.700, 30.0, 30.0 - TOLERANCE_MS).decision == policy.REVERT


def test_a_flat_comparison_is_reverted() -> None:
    """Nothing moved, so there is nothing to adopt."""
    assert outcome(0.700, 0.700, 30.0, 30.0).decision == policy.REVERT


def test_flat_recall_with_worse_latency_is_reverted() -> None:
    """A latency regression inside the budget still carries no keep."""
    assert outcome(0.700, 0.700, 30.0, 35.0).decision == policy.REVERT


def test_differences_below_the_published_precision_do_not_decide() -> None:
    """A move in a place the report does not publish is not a move."""
    assert outcome(0.7000, 0.70004, 30.0, 30.0).decision == policy.REVERT


def test_every_decision_carries_a_readable_reason() -> None:
    """A decision a student cannot check against the rule is not much use."""
    verdict = outcome(0.700, 0.780, 30.0, 34.0)
    assert verdict.decision in policy.DECISIONS
    assert "budget" in verdict.reason


def test_the_supplied_policy_file_is_not_published_yet() -> None:
    """The release gate is real: the rule refuses to decide until it is calibrated.

    This is the state the template ships in, and it is asserted so that
    publishing constants can never happen silently. Calibrating B and T means
    changing this test along with the file, deliberately.
    """
    with pytest.raises(policy.PolicyUnpublished):
        policy.published_policy()


def test_the_rounding_convention_is_readable_without_the_constants() -> None:
    """Matching an answer to a report is a precision question, not a policy one."""
    convention = policy.rounding()
    assert convention.recall_places == 3
    assert convention.latency_places == 1
