"""The Any-related kinds are errors globally; the test sub-config relaxes only unknown-*."""

import tomllib

from _paths import REPO_ROOT

_KINDS = ("explicit-any", "implicit-any-empty-container", "implicit-any-lambda")
_RELAXED = {"unknown-argument-type", "unknown-variable-type"}


def _pyrefly() -> dict[str, object]:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    config = pyproject["tool"]["pyrefly"]
    assert isinstance(config, dict)
    return config


def test_the_global_errors_turn_all_three_kinds_on() -> None:
    errors = _pyrefly()["errors"]
    assert isinstance(errors, dict)
    assert {kind: errors.get(kind) for kind in _KINDS} == dict.fromkeys(_KINDS, "error")


def test_no_sub_config_relaxes_the_three_kinds() -> None:
    configs = _pyrefly().get("sub-config", [])
    assert isinstance(configs, list)
    assert configs, "the test sub-config is what this guards"
    for config in configs:
        errors = config["errors"]
        assert set(errors) <= _RELAXED, config
        assert all(value is False for value in errors.values()), config
