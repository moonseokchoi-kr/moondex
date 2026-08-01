#!/usr/bin/env python3
"""Run deterministic offline benchmark fixtures and report the adoption gate.

Held-out fixtures are deliberately input-only: this command has no update mode
for either fixture set, and especially no option that can rewrite held-out data.
Live/LLM evaluations belong under ``evals/`` and are never called here.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness_core.code_mapper import NOT_INITIALIZED, UNAVAILABLE, classify_probe
from harness_core.learning import route_change
from harness_core.pr import transition


DEFAULT_BASELINE = ROOT / "benchmarks" / "baseline.json"
TRAIN_SET = ROOT / "benchmarks" / "sets" / "train" / "core.json"
HELD_OUT_SET = ROOT / "benchmarks" / "sets" / "held-out" / "core.json"


SOURCE_REPLAY_PROGRAM = r"""
import json
import os
import sys

sys.path.insert(0, os.getcwd())

from harness_core.code_mapper import UNAVAILABLE, classify_probe
from harness_core.learning import route_change
from harness_core.pr import transition


def run_case(case):
    payload = case["input"]
    operation = case["operation"]
    if operation == "learning.route_change":
        return route_change(**payload)
    if operation == "pr.transition":
        return transition(**payload)
    if operation == "code_mapper.classify_probe":
        state = classify_probe(payload["graph_probe"])
        return {"state": state, "approximate": state == UNAVAILABLE}
    # An operation absent from the predecessor is a genuine failed fixture,
    # rather than an invitation to evaluate it with candidate code.
    return {"__source_operation_unsupported__": operation}


cases = json.load(sys.stdin)
json.dump({case["id"]: run_case(case) for case in cases}, sys.stdout, sort_keys=True)
"""


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    """Dispatch one fixture to its real, deterministic harness_core behavior."""
    payload = case["input"]
    operation = case["operation"]
    if operation == "learning.route_change":
        return route_change(**payload)
    if operation == "pr.transition":
        return transition(**payload)
    if operation == "pr.presentation_boundary":
        return _presentation_boundary(**payload)
    if operation == "code_mapper.classify_probe":
        state = classify_probe(payload["graph_probe"])
        return {"state": state, "approximate": state == UNAVAILABLE}
    raise ValueError(f"unsupported benchmark operation: {operation}")


def _contains_literal(value: Any, literal: str) -> bool:
    """Return whether a fixture surface exposes an exact raw evidence value."""
    if isinstance(value, dict):
        return any(_contains_literal(item, literal) for item in value.values())
    if isinstance(value, list):
        return any(_contains_literal(item, literal) for item in value)
    return isinstance(value, str) and literal in value


def _presentation_boundary(
    *, credential_literal: str, raw_audit: Any, rendered_report: Any,
) -> dict[str, bool]:
    """Check the trusted-local audit versus human-readable report contract.

    A raw local audit intentionally retains evidence for reproducibility.  The
    same literal must never appear in a rendered report/evaluation surface.
    This is a fixture-level assertion only; it neither mutates the audit nor
    treats trusted-local at-rest evidence as a benchmark failure.
    """
    return {
        "raw_audit_retains_literal": _contains_literal(raw_audit, credential_literal),
        "rendered_report_redacted": not _contains_literal(rendered_report, credential_literal),
    }


def run_set(cases: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {case["id"]: run_case(case) for case in cases}


def matches_expected(actual: dict[str, Any], expected: dict[str, Any]) -> bool:
    """Fixtures assert stable outcome fields without coupling to diagnostic text."""
    return all(actual.get(key) == value for key, value in expected.items())


def passed_case_ids(cases: list[dict[str, Any]], results: dict[str, dict[str, Any]]) -> set[str]:
    return {case["id"] for case in cases if matches_expected(results[case["id"]], case["expected"])}


def fixture_case_ids(cases: Any, *, set_name: str) -> list[str]:
    """Return the stable fixture identity, rejecting ambiguous case universes."""
    if not isinstance(cases, list):
        raise ValueError(f"{set_name} fixture set must be a list")
    case_ids: list[str] = []
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"]:
            raise ValueError(f"{set_name} fixtures must have non-empty string ids")
        case_ids.append(case["id"])
    if len(case_ids) != len(set(case_ids)):
        raise ValueError(f"{set_name} fixture ids must be unique")
    return sorted(case_ids)


def _source_tree(revision: str, destination: Path) -> None:
    """Materialize committed deterministic core files without touching checkout state."""
    resolved = subprocess.run(
        ["git", "rev-parse", "--verify", f"{revision}^{{commit}}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if resolved.returncode != 0 or resolved.stdout.strip() != revision:
        raise ValueError("baseline source_revision does not resolve to the recorded commit")

    archive = subprocess.run(
        ["git", "archive", "--format=tar", revision, "harness_core"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if archive.returncode != 0:
        raise ValueError("baseline source_revision has no replayable harness_core tree")

    root = destination.resolve()
    with tarfile.open(fileobj=io.BytesIO(archive.stdout), mode="r:") as bundle:
        for member in bundle.getmembers():
            target = (destination / member.name).resolve()
            if root not in target.parents or not member.isfile():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            source = bundle.extractfile(member)
            if source is None:
                raise ValueError("baseline source archive contains an unreadable file")
            target.write_bytes(source.read())


def replay_source_outcomes(
    revision: str, cases: list[dict[str, Any]],
) -> dict[str, bool]:
    """Evaluate current fixture inputs using only deterministic code at revision."""
    with tempfile.TemporaryDirectory(prefix="moondex-benchmark-source-") as temporary:
        source_root = Path(temporary)
        _source_tree(revision, source_root)
        replay = subprocess.run(
            [sys.executable, "-I", "-c", SOURCE_REPLAY_PROGRAM],
            cwd=source_root,
            input=json.dumps(cases),
            capture_output=True,
            text=True,
            check=False,
        )
    if replay.returncode != 0:
        raise ValueError("baseline source_revision could not replay deterministic fixtures")
    try:
        results = json.loads(replay.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("baseline source_revision returned invalid replay evidence") from exc
    if not isinstance(results, dict) or sorted(results) != sorted(case["id"] for case in cases):
        raise ValueError("baseline source_revision returned incomplete replay evidence")
    return {
        case["id"]: matches_expected(results[case["id"]], case["expected"])
        for case in cases
    }


def validate_baseline(
    baseline: Any,
    *,
    train_cases: list[dict[str, Any]],
    held_out_cases: list[dict[str, Any]],
) -> None:
    train_case_ids = fixture_case_ids(train_cases, set_name="train")
    held_out_case_ids = fixture_case_ids(held_out_cases, set_name="held-out")
    required = (
        "schema_version",
        "train_case_ids",
        "held_out_case_ids",
        "train_score",
        "held_out_score",
        "train_passed_case_ids",
        "held_out_passed_case_ids",
        "source_revision",
        "source_case_outcomes",
    )
    if not isinstance(baseline, dict) or any(key not in baseline for key in required):
        raise ValueError("baseline must contain fixture identities, scores, and per-case passed ids")
    if baseline["schema_version"] != 2:
        raise ValueError("baseline schema_version must be 2")

    if not isinstance(baseline["source_revision"], str) or not re.fullmatch(
        r"[0-9a-f]{40}", baseline["source_revision"]
    ):
        raise ValueError("baseline source_revision must be a full lowercase git commit id")

    for field in ("train_case_ids", "held_out_case_ids", "train_passed_case_ids", "held_out_passed_case_ids"):
        values = baseline[field]
        if not isinstance(values, list) or any(not isinstance(case_id, str) or not case_id for case_id in values):
            raise ValueError(f"baseline {field} must be a string list")
        if values != sorted(set(values)):
            raise ValueError(f"baseline {field} must contain unique sorted ids")

    if baseline["train_case_ids"] != train_case_ids or baseline["held_out_case_ids"] != held_out_case_ids:
        raise ValueError("baseline fixture universe mismatch; record a baseline for the current case ids")

    train_universe = set(train_case_ids)
    held_out_universe = set(held_out_case_ids)
    if not set(baseline["train_passed_case_ids"]).issubset(train_universe) or not set(
        baseline["held_out_passed_case_ids"]
    ).issubset(held_out_universe):
        raise ValueError("baseline passed-case ids must be members of their fixture universe")

    if type(baseline["train_score"]) is not int or type(baseline["held_out_score"]) is not int:
        raise ValueError("baseline scores must be integers")
    if baseline["train_score"] != len(baseline["train_passed_case_ids"]) or baseline[
        "held_out_score"
    ] != len(baseline["held_out_passed_case_ids"]):
        raise ValueError("baseline scores must equal their passed-case id counts")

    all_case_ids = train_case_ids + held_out_case_ids
    source_outcomes = baseline["source_case_outcomes"]
    if (
        not isinstance(source_outcomes, dict)
        or sorted(source_outcomes) != sorted(all_case_ids)
        or any(type(passed) is not bool for passed in source_outcomes.values())
    ):
        raise ValueError("baseline source_case_outcomes must record one boolean for every fixture id")
    recorded_passes = sorted(case_id for case_id, passed in source_outcomes.items() if passed)
    declared_passes = sorted(baseline["train_passed_case_ids"] + baseline["held_out_passed_case_ids"])
    if recorded_passes != declared_passes:
        raise ValueError("baseline source evidence must agree with passed-case ids")

    replayed_outcomes = replay_source_outcomes(
        baseline["source_revision"], train_cases + held_out_cases,
    )
    if source_outcomes != replayed_outcomes:
        raise ValueError("baseline source evidence does not match source_revision replay")


def evaluate(baseline_path: Path) -> dict[str, Any]:
    if not baseline_path.is_file():
        raise ValueError(f"baseline is required: {baseline_path}")
    baseline = load_json(baseline_path)
    train_cases = load_json(TRAIN_SET)
    held_out_cases = load_json(HELD_OUT_SET)
    train_case_ids = fixture_case_ids(train_cases, set_name="train")
    held_out_case_ids = fixture_case_ids(held_out_cases, set_name="held-out")
    validate_baseline(
        baseline,
        train_cases=train_cases,
        held_out_cases=held_out_cases,
    )
    train_results = run_set(train_cases)
    held_out_results = run_set(held_out_cases)
    train_passed = passed_case_ids(train_cases, train_results)
    held_out_passed = passed_case_ids(held_out_cases, held_out_results)
    train_score = len(train_passed)
    held_out_score = len(held_out_passed)
    baseline_train_passed = set(baseline["train_passed_case_ids"])
    baseline_held_out_passed = set(baseline["held_out_passed_case_ids"])
    train_improvements = sorted(train_passed - baseline_train_passed)
    train_regressions = sorted(baseline_train_passed - train_passed)
    held_out_regressions = sorted(baseline_held_out_passed - held_out_passed)
    held_out_improvements = sorted(held_out_passed - baseline_held_out_passed)
    train_improved = len(train_passed) > len(baseline_train_passed)
    accepted = train_improved and not held_out_regressions
    return {
        "baseline": {
            "train_score": baseline["train_score"],
            "held_out_score": baseline["held_out_score"],
            "source_revision": baseline["source_revision"],
        },
        "candidate": {"train_score": train_score, "held_out_score": held_out_score},
        "fixture_identity": {
            "train_case_ids": train_case_ids,
            "held_out_case_ids": held_out_case_ids,
        },
        "train_improvement_case_ids": train_improvements,
        "train_regression_case_ids": train_regressions,
        "held_out_improvement_case_ids": held_out_improvements,
        "held_out_regression_count": len(held_out_regressions),
        "held_out_regression_case_ids": held_out_regressions,
        "adoption_gate": {
            "tier": "harness",
            "status": "PASS" if accepted else "REJECT",
            "reason": "train score improved and no held-out regressions" if accepted else "requires train score improvement and zero held-out regressions",
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run offline train and guarded held-out benchmark fixtures.")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE, help="recorded score before the candidate change")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = evaluate(args.baseline)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"BENCHMARK_INVALID: {exc}")
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["adoption_gate"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
