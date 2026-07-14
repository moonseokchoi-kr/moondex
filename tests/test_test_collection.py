from pathlib import Path


def test_live_evaluations_are_not_a_default_test_target() -> None:
    config = Path("pyproject.toml").read_text(encoding="utf-8")

    assert 'testpaths = ["tests"]' in config
    assert 'norecursedirs = ["evals"]' in config
