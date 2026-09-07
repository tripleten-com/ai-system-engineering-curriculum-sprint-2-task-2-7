"""Coldline.

===================

File:              tests/contract/test_submission.py
Component:         Contract tests — Test Submission
Purpose:           Tests for the public answer and path checks for this Task's submission.
Interacts With:    Published interfaces and repository boundaries
Sprint/Task:       Sprint 2 — Project 2
Concepts:          Compatibility, ownership, export safety
Tools:             Python 3.12, pytest
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.contract.submission_validation import (
    SubmissionError,
    _load_one_document,
    main,
    validate_changed_paths,
    validate_submission,
)

ROOT = Path(__file__).parents[2]
SCHEMA = ROOT / "docs/contracts/submission.schema.json"


def valid_answers(**overrides: Any) -> dict[str, object]:
    """Return a complete answer sheet describing one plausible experiment."""
    answers: dict[str, Any] = {
        "selected_parameter": "top_k",
        "parameter_value": 5,
        "baseline_recall_at_k": 0.444,
        "experiment_recall_at_k": 0.611,
        "baseline_latency_ms": 21.4,
        "experiment_latency_ms": 22.0,
        "agreement_classification": "disagreement",
        "adoption_decision": "keep",
    }
    answers.update(overrides)
    return {"answers": answers}


def _task_root(tmp_path: Path, submission_text: str) -> Path:
    """Stage a minimal Task root the public verifier can validate."""
    (tmp_path / "docs/contracts").mkdir(parents=True)
    (tmp_path / "submission.yaml").write_text(submission_text, encoding="utf-8")
    (tmp_path / "submission-sample.yaml").write_text(
        (ROOT / "submission-sample.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "docs/contracts/submission.schema.json").write_text(
        SCHEMA.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return tmp_path


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"selected_parameter": "fusion_weight", "parameter_value": 0.2},
        {"selected_parameter": "fusion_weight", "parameter_value": 0.0},
        {"selected_parameter": "top_k", "parameter_value": 12},
        {"agreement_classification": "agreement"},
        {"agreement_classification": "mixed_or_no_change"},
        {"adoption_decision": "revert"},
        {"baseline_recall_at_k": 0.0, "experiment_recall_at_k": 1.0},
        {"baseline_latency_ms": 0, "experiment_latency_ms": 0},
    ],
    ids=[
        "top-k",
        "fusion-weight",
        "fusion-weight-sparse-only",
        "top-k-at-the-candidate-pool",
        "agreement",
        "mixed-or-no-change",
        "revert",
        "recall-bounds",
        "zero-latency",
    ],
)
def test_every_permitted_combination_passes_public_validation(
    tmp_path: Path, overrides: dict[str, Any]
) -> None:
    """No parameter, classification, or decision is privileged by the public schema.

    Which value is *correct* depends on the student's own measurement, and the
    runtime checks decide that. The public schema only decides what is
    well-formed.
    """
    root = _task_root(tmp_path, yaml.safe_dump(valid_answers(**overrides)))

    validate_submission(root / "submission.yaml", SCHEMA)


def test_blank_template_fails_with_field_address(tmp_path: Path) -> None:
    """An untouched answer sheet must identify the first incomplete field."""
    root = _task_root(tmp_path, (ROOT / "submission.yaml").read_text(encoding="utf-8"))

    with pytest.raises(SubmissionError, match="answers.selected_parameter"):
        validate_submission(root / "submission.yaml", SCHEMA)


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"selected_parameter": "embedding_model"}, "selected_parameter"),
        ({"selected_parameter": "top_k", "parameter_value": 0}, "parameter_value"),
        ({"selected_parameter": "top_k", "parameter_value": 13}, "parameter_value"),
        ({"selected_parameter": "top_k", "parameter_value": 4.5}, "parameter_value"),
        ({"selected_parameter": "fusion_weight", "parameter_value": 1.5}, "parameter_value"),
        ({"baseline_recall_at_k": 1.2}, "baseline_recall_at_k"),
        ({"experiment_recall_at_k": -0.1}, "experiment_recall_at_k"),
        ({"baseline_latency_ms": -1}, "baseline_latency_ms"),
        ({"agreement_classification": "partial"}, "agreement_classification"),
        ({"adoption_decision": "escalate"}, "adoption_decision"),
        ({"baseline_latency_ms": "21.4 ms"}, "baseline_latency_ms"),
    ],
    ids=[
        "unapproved-parameter",
        "top-k-below-one",
        "top-k-above-the-pool",
        "top-k-not-a-whole-number",
        "fusion-weight-above-one",
        "recall-above-one",
        "recall-below-zero",
        "negative-latency",
        "unlisted-classification",
        "unlisted-decision",
        "latency-with-a-unit-suffix",
    ],
)
def test_values_outside_the_published_contract_are_rejected(
    tmp_path: Path, overrides: dict[str, Any], message: str
) -> None:
    """The public schema must name the field it rejected, and reject the right ones."""
    root = _task_root(tmp_path, yaml.safe_dump(valid_answers(**overrides)))

    with pytest.raises(SubmissionError, match=message):
        validate_submission(root / "submission.yaml", SCHEMA)


def test_a_missing_answer_is_rejected(tmp_path: Path) -> None:
    """Eight answers describe one experiment; seven describe an incomplete one."""
    answers = valid_answers()
    mapping = answers["answers"]
    assert isinstance(mapping, dict)
    del mapping["experiment_latency_ms"]
    root = _task_root(tmp_path, yaml.safe_dump(answers))

    with pytest.raises(SubmissionError, match="experiment_latency_ms"):
        validate_submission(root / "submission.yaml", SCHEMA)


def test_unexpected_answer_field_is_rejected(tmp_path: Path) -> None:
    """Fields outside the published direct-answer schema must fail validation."""
    answers = valid_answers()
    mapping = answers["answers"]
    assert isinstance(mapping, dict)
    mapping["decision_rationale"] = "no free text is assessed in this Task"
    root = _task_root(tmp_path, yaml.safe_dump(answers))

    with pytest.raises(SubmissionError, match="Additional properties"):
        validate_submission(root / "submission.yaml", SCHEMA)


def test_exact_sample_copy_is_rejected(tmp_path: Path) -> None:
    """The published sample must not be accepted as a student submission."""
    root = _task_root(tmp_path, (ROOT / "submission-sample.yaml").read_text(encoding="utf-8"))

    with pytest.raises(SubmissionError, match="fictional sample"):
        validate_submission(
            root / "submission.yaml",
            SCHEMA,
            sample_path=root / "submission-sample.yaml",
        )


def test_student_editable_paths_and_prefixes_are_permitted() -> None:
    """The advisory path gate must accept this Task's implementation surface."""
    validate_changed_paths(["submission.yaml"])
    validate_changed_paths(["config/student/retrieval.yaml"])
    validate_changed_paths(["tests/student/test_my_regression.py"])

    with pytest.raises(SubmissionError, match="config/retrieval-baseline.yaml"):
        validate_changed_paths(["config/retrieval-baseline.yaml"])

    with pytest.raises(SubmissionError, match="infra/corpus/queries.jsonl"):
        validate_changed_paths(["infra/corpus/queries.jsonl"])

    with pytest.raises(SubmissionError, match="infra/judge"):
        validate_changed_paths(["infra/judge/cached-judgements.jsonl"])

    with pytest.raises(SubmissionError, match="tests/benchmark"):
        validate_changed_paths(["tests/benchmark/metrics.py"])

    with pytest.raises(SubmissionError, match="tests/regression.py"):
        validate_changed_paths(["tests/regression.py"])

    with pytest.raises(SubmissionError, match="tests/contract"):
        validate_changed_paths(["tests/contract/test_retrieval_experiment.py"])

    with pytest.raises(SubmissionError, match="src/api"):
        validate_changed_paths(["src/api/experiment.py"])


def test_public_entrypoint_reports_an_incomplete_answer_sheet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Catch a verifier entrypoint that skips the real submission contract."""
    root = _task_root(tmp_path, (ROOT / "submission.yaml").read_text(encoding="utf-8"))

    assert main(root, changed_paths=[]) == 1
    assert "answers.selected_parameter is incomplete" in capsys.readouterr().err


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "answers: {value: first, value: second}\n",
        "answers: &answer {value: fictional}\n",
        "answers: *missing\n",
        "answers: {<<: {value: fictional}}\n",
        "answers: {value: 2026-09-04}\n",
        "answers: {value: !custom fictional}\n",
        "answers: {1: fictional}\n",
    ],
    ids=[
        "duplicate-key",
        "anchor",
        "alias",
        "merge-key",
        "date",
        "custom-tag",
        "non-string-key",
    ],
)
def test_non_json_yaml_constructs_are_rejected(tmp_path: Path, unsafe_text: str) -> None:
    """Reject restricted syntax before schema validation can mask a parser defect."""
    submission = tmp_path / "submission.yaml"
    submission.write_text(unsafe_text, encoding="utf-8")

    with pytest.raises(SubmissionError, match="restricted YAML"):
        _load_one_document(submission)


def test_multiple_yaml_documents_are_rejected(tmp_path: Path) -> None:
    """A second document cannot supply or replace the answer mapping."""
    submission = tmp_path / "submission.yaml"
    submission.write_text("answers: {}\n---\nanswers: {}\n", encoding="utf-8")

    with pytest.raises(SubmissionError, match="exactly one YAML mapping"):
        _load_one_document(submission)
