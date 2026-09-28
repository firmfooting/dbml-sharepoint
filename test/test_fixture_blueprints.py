"""The suite's own blueprints are the listed ones, and the engine sweeps read every root."""

import re
from pathlib import Path

from _paths import SOLUTION_TEMPLATES, TEST_BLUEPRINTS, engine_blueprints

#: Grows only with a row in the README beside the directories; never a copy of a shipped one.
TEST_ROSTER = frozenset({"reporting-sample", "risk-register"})


def _ids(root: Path) -> set[str]:
    return {schema.parent.parent.name for schema in root.glob("*/10-design/schema.dbml")}


def test_the_suite_s_blueprints_are_exactly_the_listed_ones() -> None:
    readme = (TEST_BLUEPRINTS / "README.md").read_text(encoding="utf-8")
    rows = set(re.findall(r"^\| `([a-z0-9-]+)/` \|", readme, flags=re.MULTILINE))
    directories = {path.name for path in TEST_BLUEPRINTS.iterdir() if path.is_dir()}
    assert directories == rows == TEST_ROSTER


def test_the_engine_sweeps_read_core_first_then_the_suite_s_blueprints() -> None:
    found = engine_blueprints()
    for blueprint_id in _ids(SOLUTION_TEMPLATES):
        assert found[blueprint_id] == SOLUTION_TEMPLATES / blueprint_id
    assert _ids(TEST_BLUEPRINTS) == TEST_ROSTER
    for blueprint_id in TEST_ROSTER - _ids(SOLUTION_TEMPLATES):
        assert found[blueprint_id] == TEST_BLUEPRINTS / blueprint_id
