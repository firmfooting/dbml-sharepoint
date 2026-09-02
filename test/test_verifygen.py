# test/test_verifygen.py
"""verify.js.txt: each clock cell a pack uses, exercised on a scratch list.

The checks are derived from the pack's clock usage and rendered with the
same renderer and the same list-rule join the deployer uses, so what the
script writes to the scratch list is what the deploy writes to the real
lists, one column at a time.
"""
from _model import bundle as make_bundle
from _model import column
from _model import schema as make_schema
from _model import table as make_table

from dbml_sharepoint.analysis.clock_cells import cell_for
from dbml_sharepoint.analysis.condition_rendering import to_validation
from dbml_sharepoint.analysis.list_description import VERIFY_LIST_TITLE, verify_marker
from dbml_sharepoint.analysis.save_rules import joined_list_validation
from dbml_sharepoint.generators.verifygen import verify_targets
from dbml_sharepoint.model.conditions import Group, Leaf
from dbml_sharepoint.model.mapping_types import (
    ColumnValidation,
    EntitySection,
    ListValidation,
    MappingBundle,
    ViewDef,
)
from dbml_sharepoint.model.parser import Schema


def _rule(field: str, op: str, value: str) -> ColumnValidation:
    return ColumnValidation(when=Leaf(field=field, op=op, value=value), message="m")


def _clock_pack() -> tuple[Schema, MappingBundle]:
    schema = make_schema(make_table(
        "Task",
        column("Title", required=True),
        column("Due", "date"),
        column("OccurredAt", "datetime"),
        column("Raised", "date", default="[today]"),
        note="Tasks.",
    ))
    bundle = make_bundle(
        entities=["Task"],
        column_validation={"Task": EntitySection(columns={
            "Due": _rule("Due", "leq", "today"),
            "OccurredAt": _rule("OccurredAt", "leq", "now"),
        })},
        list_validation={"Task": ListValidation(
            when=Group("all_of", (Leaf(field="Due", op="leq", value="today+30"),)), message="m",
        )},
        views={"Task": [ViewDef(title="Soon", fields=["Title"], where=Group("all_of", (
            Leaf(field="Due", op="leq", value="today+7"),
        )))]},
    )
    return schema, bundle


def _checks(targets: dict) -> dict[str, dict]:  # type: ignore[type-arg]
    return {check["key"]: check for check in targets["checks"]}


def test_a_pack_without_a_clock_cell_has_nothing_to_verify() -> None:
    schema = make_schema(make_table("Task", column("Title", required=True), note="Tasks."))
    targets = verify_targets(schema, make_bundle(entities=["Task"]), "default")
    assert targets["checks"] == []
    assert targets["rule"] is None


def test_the_scratch_list_is_named_and_marked_from_the_shared_spellers() -> None:
    targets = verify_targets(*_clock_pack(), "default")
    assert targets["list_title"] == VERIFY_LIST_TITLE
    assert targets["marker"] == verify_marker()


def test_one_save_check_per_validation_cell_and_offset_with_the_cells_rendering() -> None:
    checks = _checks(verify_targets(*_clock_pack(), "default"))
    today = checks["validation_date_today"]
    assert today["cell"] == "validation/date/today"
    assert today["column"] == {"name": "VDT", "kind": "date", "display_format": 0}
    rendering = cell_for("today", "date", "validation").renderings[("leq", "today")]
    assert today["clause"] == rendering.replace("[D]", "[VDT]")
    assert [(c["id"], c["op"], c["expect"]) for c in today["cases"]] == [
        ("yesterday", "create", "save"),
        ("today", "create", "save"),
        ("tomorrow", "create", "refuse"),
        ("update-today", "update", "save"),
        ("update-tomorrow", "update", "refuse"),
    ]
    assert today["cases"][0]["value"] == {"kind": "midnight", "days": -1}
    assert today["cases"][3]["on"] == "today"

    offset = checks["validation_date_today_offset_30"]
    assert offset["column"]["name"] == "VDO30"
    assert offset["clause"] == to_validation(
        Group("all_of", (Leaf(field="VDO30", op="leq", value="today+30"),)), {"VDO30": "date"},
    )
    assert [(c["id"], c["expect"], c["value"]["days"]) for c in offset["cases"]] == [
        ("day-30", "save", 30), ("day-31", "refuse", 31), ("day-29", "save", 29),
    ]

    now = checks["validation_datetime_now"]
    assert now["column"] == {"name": "VWN", "kind": "datetime", "display_format": 1}
    assert now["clause"] == "[VWN]<=[Modified]"
    assert [(c["id"], c["op"], c["expect"], c["value"]) for c in now["cases"]] == [
        ("hour-ago", "create", "save", {"kind": "instant", "seconds": -3600}),
        ("hour-ahead", "create", "refuse", {"kind": "instant", "seconds": 3600}),
        ("update-now", "update", "save", {"kind": "instant", "seconds": -5}),
    ]


def test_the_list_rule_is_the_deployers_join_over_the_save_checks() -> None:
    """The joined shape is what the deploy writes for a real list, so the
    scratch list exercises it too. Produced by the same function, not
    re-spelled."""
    targets = verify_targets(*_clock_pack(), "default")
    save_checks = [c for c in targets["checks"] if c["kind"] == "save"]
    types = {c["column"]["name"]: c["column"]["kind"] for c in save_checks}
    joined = joined_list_validation(
        None,
        [(c["column"]["name"], ColumnValidation(when=Leaf(**c["leaf"]), message=c["message"]))
         for c in save_checks],
    )
    assert joined is not None
    assert targets["rule"]["formula"] == f"={to_validation(joined.when, types)}"
    assert targets["rule"]["message"] == joined.message
    assert targets["rule"]["formula"].startswith("=AND(OR(ISBLANK([VDT]),[VDT]<=[Modified]),")


def test_a_lagging_clock_cell_is_reported_not_judged() -> None:
    schema = make_schema(make_table(
        "Event", column("Title", required=True), column("At", "datetime"), note="Events.",
    ))
    bundle = make_bundle(
        entities=["Event"],
        column_validation={"Event": EntitySection(columns={"At": _rule("At", "leq", "today+1")})},
    )
    checks = _checks(verify_targets(schema, bundle, "default"))
    check = checks["validation_datetime_today_offset_1"]
    assert check["cell"] == "validation/datetime/today_offset"
    assert check["column"]["name"] == "VWO1"
    assert all(case["expect"] == "info" for case in check["cases"])


def test_view_windows_become_query_checks_over_rows_the_script_places() -> None:
    targets = verify_targets(*_clock_pack(), "default")
    checks = _checks(targets)
    query = checks["caml_date_today_offset_7"]
    assert query["kind"] == "query"
    assert query["field"] == "CD"
    assert query["op"] == "Eq"
    assert query["element"] == '<Value Type="DateTime"><Today OffsetDays="7"/></Value>'
    assert query["expect"] == ["cd-day-7"]
    rows = {row["id"]: row for row in targets["rows"]}
    assert rows["cd-day-7"] == {
        "id": "cd-day-7", "column": "CD", "value": {"kind": "midnight", "days": 7},
    }
    # The fixed rows around today are always placed, so a window's edges are visible.
    assert {"cd-day--1", "cd-day-0", "cd-day-1"} <= set(rows)


def test_a_today_default_and_the_formula_clock_are_checked_when_used() -> None:
    targets = verify_targets(*_clock_pack(), "default")
    checks = _checks(targets)
    assert checks["default_date"]["column"]["default_value"] == "[today]"
    assert checks["default_date"]["method"] == "today-query"
    assert checks["formula_clock_lag"]["column"] == {
        "name": "LT", "kind": "date", "display_format": 0, "default_formula": "=TODAY()",
    }
    names = [c["name"] for c in targets["columns"]]
    assert names == sorted(names) and len(names) == len(set(names))
    assert {"VDT", "VDO30", "VWN", "CD", "DD", "LT"} <= set(names)
