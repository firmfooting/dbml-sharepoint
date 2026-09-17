# test/test_digital_innovation_log_seed.py
"""The go-live catalogue for `DI_Pattern` stays loadable.

`digital-innovation-log/20-configure/patterns-seed.yaml` holds the twenty-nine
patterns a service enters by hand after its first deploy. The build never
reads it, so nothing else would notice a row that names a choice member the
enum no longer has, a column that was renamed, or a workload list with a
repeat in it. The person typing it in would, one refused save at a time.

So the file is run through the demo-row validator here. The rows use the
`demo_items` value grammar on purpose; the only thing the seeder requires
that this file must not carry is the `[DEMO]` marker, which the test adds
to a throwaway copy before validating. A future real-row seeder can read
the file as it is.
"""

import shutil
from pathlib import Path
from typing import Any

import yaml
from _paths import SOLUTION_TEMPLATES

from dbml_sharepoint.analysis.demo_marker import DEMO_TITLE_PREFIX
from dbml_sharepoint.analysis.validator import validate, validate_against_mapping
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml

FAMILY = SOLUTION_TEMPLATES / "digital-innovation-log"
SEED = FAMILY / "20-configure" / "patterns-seed.yaml"

# The brief the catalogue was researched against: a title that reads as a
# pattern name in a pill-width column, and every row a proposal until its
# Build Owner has built it.
TITLE_LIMIT = 60
EXPECTED_ROWS = 29


def _rows() -> list[dict[str, Any]]:
    raw: dict[str, Any] = yaml.safe_load(SEED.read_text(encoding="utf-8"))
    assert set(raw) == {"seed_items"}, f"the seed file holds {sorted(raw)}, not only seed_items"
    assert set(raw["seed_items"]) == {"Pattern"}, "the catalogue seeds DI_Pattern and nothing else"
    rows: list[dict[str, Any]] = raw["seed_items"]["Pattern"]
    return rows


def test_the_catalogue_is_the_researched_size() -> None:
    assert len(_rows()) == EXPECTED_ROWS


def test_every_row_is_a_proposed_unmarked_pattern_with_a_guide() -> None:
    keys: set[str] = set()
    titles: set[str] = set()
    for row in _rows():
        assert set(row) == {"key", "values"}, row
        assert row["key"] not in keys, f"duplicate key {row['key']}"
        keys.add(row["key"])
        values = row["values"]
        title = values["Title"]
        assert not title.startswith(DEMO_TITLE_PREFIX.strip()), f"{title!r} carries the demo marker"
        assert title not in titles, f"duplicate title {title!r}"
        titles.add(title)
        assert len(title) <= TITLE_LIMIT, f"{title!r} is over {TITLE_LIMIT} characters"
        assert values["Status"] == "Proposed", f"{title!r} is not Proposed"
        assert values["GuideLink"].startswith("https://"), f"{title!r} has no guide link"
        assert values["Workloads"], f"{title!r} names no workload"
        assert "BuildOwner" not in values, f"{title!r} names an owner the service has not chosen"
        assert "AvailableDate" not in values, f"{title!r} claims to be available"


def test_every_row_validates_as_a_pattern_row(tmp_path: Path) -> None:
    """Marked and pointed at from a copy of the family, the rows must pass
    the same validator the demo seeder's rows pass: enum members, column
    names, multi-value shape, literal types."""
    family = tmp_path / "digital-innovation-log"
    shutil.copytree(FAMILY, family)
    mapping_path = family / "20-configure" / "mapping.yaml"
    mapping = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
    del mapping["demo_items"]
    mapping["demo_source"] = "seed-check.yaml"
    mapping_path.write_text(yaml.safe_dump(mapping, sort_keys=False), encoding="utf-8")

    marked = [
        {
            "key": row["key"],
            "values": {**row["values"], "Title": DEMO_TITLE_PREFIX + row["values"]["Title"]},
        }
        for row in _rows()
    ]
    (family / "20-configure" / "seed-check.yaml").write_text(
        yaml.safe_dump({"demo_items": {"Pattern": marked}}, sort_keys=False), encoding="utf-8"
    )

    schema = parse_dbml(family / "10-design" / "schema.dbml")
    bundle = load_mapping(mapping_path)
    findings = validate(schema) + validate_against_mapping(schema, bundle)
    errors = [f for f in findings if f.severity == "error"]
    assert not errors, "\n".join(f"{f.code}: {f.message}" for f in errors)
    assert len(bundle.mapping.demo_items["Pattern"]) == EXPECTED_ROWS
