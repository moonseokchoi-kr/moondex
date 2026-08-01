import importlib.util
import json
from pathlib import Path
from subprocess import run

import pytest


SCRIPT = Path("scripts/run-benchmarks.py")


def load_runner():
    spec = importlib.util.spec_from_file_location("run_benchmarks", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def baseline_for_current_universe(runner, **overrides):
    train_case_ids = sorted(case["id"] for case in runner.load_json(runner.TRAIN_SET))
    held_out_case_ids = sorted(case["id"] for case in runner.load_json(runner.HELD_OUT_SET))
    baseline = {
        "schema_version": 2,
        "train_case_ids": train_case_ids,
        "held_out_case_ids": held_out_case_ids,
        "train_score": 2,
        "held_out_score": 3,
        "train_passed_case_ids": ["mapper-fallback-is-approximate", "pr-actionable-converged"],
        "held_out_passed_case_ids": [
            "learning-harness-is-proposal",
            "mapper-uninitialized-is-not-healthy",
            "pr-design-question-escalates",
        ],
        "source_revision": "7b017989ff7fd531b8606da6fef3ad6e1576bd1b",
        "source_case_outcomes": {
            case_id: case_id in {
                "mapper-fallback-is-approximate",
                "pr-actionable-converged",
                "learning-harness-is-proposal",
                "mapper-uninitialized-is-not-healthy",
                "pr-design-question-escalates",
            }
            for case_id in train_case_ids + held_out_case_ids
        },
        "source": "test baseline recorded on the current fixture universe",
    }
    baseline.update(overrides)
    return baseline


def test_runner_dispatches_real_harness_core_behavior_and_passes_harness_gate() -> None:
    runner = load_runner()
    report = runner.evaluate(Path("benchmarks/baseline.json"))

    assert report["baseline"] == {
        "train_score": 2,
        "held_out_score": 3,
        "source_revision": "7b017989ff7fd531b8606da6fef3ad6e1576bd1b",
    }
    assert report["candidate"] == {"train_score": 4, "held_out_score": 3}
    assert report["train_improvement_case_ids"] == [
        "learning-rootless-is-proposal",
        "pr-local-audit-raw-report-redacted",
    ]
    assert report["train_regression_case_ids"] == []
    assert report["held_out_regression_count"] == 0
    assert report["held_out_improvement_case_ids"] == []
    assert report["adoption_gate"]["status"] == "PASS"


def test_missing_baseline_rejects_harness_adoption(tmp_path: Path) -> None:
    runner = load_runner()

    try:
        runner.evaluate(tmp_path / "missing.json")
    except ValueError as exc:
        assert "baseline is required" in str(exc)
    else:
        raise AssertionError("missing baseline must be rejected")


def test_no_train_improvement_rejects_harness_adoption(tmp_path: Path, monkeypatch) -> None:
    runner = load_runner()
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(baseline_for_current_universe(runner)), encoding="utf-8")
    real_run_case = runner.run_case

    def unimproved_run_case(case):
        if case["id"] in {
            "learning-rootless-is-proposal",
            "pr-local-audit-raw-report-redacted",
        }:
            return {}
        return real_run_case(case)

    monkeypatch.setattr(runner, "run_case", unimproved_run_case)

    report = runner.evaluate(baseline)

    assert report["candidate"]["train_score"] == 2
    assert report["held_out_regression_count"] == 0
    assert report["adoption_gate"]["status"] == "REJECT"


def test_held_out_regression_is_per_case_not_an_aggregate_score_delta(tmp_path: Path, monkeypatch) -> None:
    runner = load_runner()
    baseline = tmp_path / "baseline.json"
    baseline.write_text(json.dumps(baseline_for_current_universe(runner)), encoding="utf-8")
    real_run_case = runner.run_case

    def regressed_run_case(case):
        if case["id"] == "learning-harness-is-proposal":
            return {"action": "APPLY"}
        return real_run_case(case)

    monkeypatch.setattr(runner, "run_case", regressed_run_case)

    report = runner.evaluate(baseline)

    # Candidate still scores 4, despite the baseline-passing held-out learning
    # case regressing. Aggregate score is never a substitute for case identity.
    assert report["candidate"]["train_score"] == 4
    assert report["held_out_regression_count"] == 1
    assert report["held_out_regression_case_ids"] == ["learning-harness-is-proposal"]
    assert report["adoption_gate"]["status"] == "REJECT"


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("train_case_ids", ["new-case-that-inflates-the-score"]),
        ("held_out_case_ids", ["different-held-out-case"]),
    ],
)
def test_changed_fixture_universe_rejects_baseline_before_score_comparison(
    tmp_path: Path, field: str, replacement: list[str],
) -> None:
    runner = load_runner()
    baseline = tmp_path / "baseline.json"
    record = baseline_for_current_universe(runner)
    record[field] = replacement
    baseline.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="fixture universe mismatch"):
        runner.evaluate(baseline)


def test_baseline_scores_and_passed_ids_must_describe_same_universe(tmp_path: Path) -> None:
    runner = load_runner()
    baseline = tmp_path / "baseline.json"
    record = baseline_for_current_universe(runner)
    record["train_passed_case_ids"] = ["case-not-in-current-universe"]
    baseline.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="passed-case ids must be members"):
        runner.evaluate(baseline)


def test_baseline_source_evidence_covers_and_agrees_with_every_fixture(tmp_path: Path) -> None:
    runner = load_runner()
    baseline = tmp_path / "baseline.json"
    record = baseline_for_current_universe(runner)
    record["source_case_outcomes"]["mapper-uninitialized-is-not-healthy"] = False
    baseline.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="source evidence must agree"):
        runner.evaluate(baseline)


def test_baseline_source_evidence_cannot_omit_a_fixture(tmp_path: Path) -> None:
    runner = load_runner()
    baseline = tmp_path / "baseline.json"
    record = baseline_for_current_universe(runner)
    del record["source_case_outcomes"]["mapper-uninitialized-is-not-healthy"]
    baseline.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="one boolean for every fixture id"):
        runner.evaluate(baseline)


def test_forged_aggregate_score_cannot_override_per_case_outcomes(tmp_path: Path) -> None:
    runner = load_runner()
    baseline = tmp_path / "baseline.json"
    record = baseline_for_current_universe(runner)
    record["train_score"] = 0
    baseline.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="scores must equal"):
        runner.evaluate(baseline)


def test_nonexistent_source_revision_rejects_self_consistent_baseline(tmp_path: Path) -> None:
    runner = load_runner()
    baseline = tmp_path / "baseline.json"
    record = baseline_for_current_universe(runner, source_revision="f" * 40)
    baseline.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="does not resolve"):
        runner.evaluate(baseline)


def test_coordinated_source_outcome_forgery_is_rejected_by_revision_replay(
    tmp_path: Path,
) -> None:
    runner = load_runner()
    baseline = tmp_path / "baseline.json"
    all_train_ids = sorted(case["id"] for case in runner.load_json(runner.TRAIN_SET))
    all_held_out_ids = sorted(case["id"] for case in runner.load_json(runner.HELD_OUT_SET))
    record = baseline_for_current_universe(
        runner,
        train_score=len(all_train_ids),
        held_out_score=len(all_held_out_ids),
        train_passed_case_ids=all_train_ids,
        held_out_passed_case_ids=all_held_out_ids,
        source_case_outcomes={case_id: True for case_id in all_train_ids + all_held_out_ids},
    )
    baseline.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="does not match source_revision replay"):
        runner.evaluate(baseline)


def test_presentation_boundary_allows_raw_local_audit_but_rejects_report_literal() -> None:
    runner = load_runner()
    literal = "trusted-local-token-7C2"

    accepted = runner.run_case({
        "operation": "pr.presentation_boundary",
        "input": {
            "credential_literal": literal,
            "raw_audit": {"credential": literal},
            "rendered_report": {"credential": "[REDACTED]"},
        },
    })
    leaked = runner.run_case({
        "operation": "pr.presentation_boundary",
        "input": {
            "credential_literal": literal,
            "raw_audit": {"credential": literal},
            "rendered_report": {"credential": literal},
        },
    })

    assert accepted == {"raw_audit_retains_literal": True, "rendered_report_redacted": True}
    assert leaked == {"raw_audit_retains_literal": True, "rendered_report_redacted": False}


def test_live_eval_requires_explicit_opt_in_and_is_outside_offline_collection() -> None:
    without_confirmation = run(["python3", "evals/run-live-eval.py"], capture_output=True, text=True)
    collection = run(["python3", "-m", "pytest", "--collect-only", "-q"], capture_output=True, text=True)

    assert without_confirmation.returncode == 2
    assert "confirm-live" in without_confirmation.stderr
    assert "run-live-eval" not in collection.stdout
