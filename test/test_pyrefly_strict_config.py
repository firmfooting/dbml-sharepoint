# test/test_pyrefly_strict_config.py
"""Every source module outside an uncleaned unit sits under the strict pyrefly sub-config."""

import fnmatch
import tomllib

from _paths import REPO_ROOT
from test_any_pins import PINS

_KINDS = {"explicit-any", "implicit-any-empty-container", "implicit-any-lambda"}


def _sub_configs() -> list[dict[str, object]]:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    configs = pyproject["tool"]["pyrefly"]["sub-config"]
    assert isinstance(configs, list)
    # The test and script sub-configs belong to units still being cleaned.
    return [config for config in configs if str(config["matches"]).startswith("src/")]


def test_every_sub_config_turns_all_three_kinds_to_error() -> None:
    for config in _sub_configs():
        errors = config["errors"]
        assert isinstance(errors, dict)
        assert {kind: errors.get(kind) for kind in _KINDS} == dict.fromkeys(_KINDS, "error"), config


def test_every_module_of_a_cleaned_unit_is_matched() -> None:
    patterns = [str(config["matches"]) for config in _sub_configs()]
    uncleaned = tuple(unit + "/" for unit in PINS if unit.startswith("src/"))
    missed = []
    for path in sorted((REPO_ROOT / "src" / "dbml_sharepoint").rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        # pyrefly globs, like fnmatch, let `*` cross directory separators.
        if not rel.startswith(uncleaned) and not any(fnmatch.fnmatch(rel, p) for p in patterns):
            missed.append(rel)
    assert not missed, f"add these to a strict [[tool.pyrefly.sub-config]]: {missed}"
