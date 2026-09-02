# test/test_clock_usage.py
"""Which clock cells a pack uses, and where.

Read by the assess script (does the site's time zone matter to this pack)
and by the verify script (which cells to exercise on the scratch list), so
one scan feeds both and they cannot disagree about what the pack does.
"""
from _model import bundle as make_bundle
from _model import column
from _model import schema as make_schema
from _model import table as make_table

from dbml_sharepoint.analysis.clock_usage import TodayDefault, clock_usage
from dbml_sharepoint.model.conditions import Group, Leaf
from dbml_sharepoint.model.mapping_types import (
    ColumnValidation,
    EntitySection,
    ListValidation,
    ViewDef,
)
from dbml_sharepoint.model.parser import Schema


def _schema() -> Schema:
    return make_schema(make_table(
        "Task",
        column("Title", required=True),
        column("Due", "date"),
        column("OccurredAt", "datetime"),
        column("Raised", "date", default="[today]"),
        column("Note"),
    ))


def _rule(field: str, op: str, value: str) -> ColumnValidation:
    return ColumnValidation(when=Leaf(field=field, op=op, value=value), message="m")


def test_every_clock_leaf_lands_in_its_cell_with_the_offsets_used() -> None:
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
            Leaf(field="Due", op="geq", value="today-1"),
            # The literal word on a text column is not a clock.
            Leaf(field="Note", op="eq", value="today"),
        )))]},
    )
    usage = clock_usage(_schema(), bundle.mapping, ["Task"])
    assert dict(usage.cells) == {
        "validation/date/today": frozenset({0}),
        "validation/date/today_offset": frozenset({30}),
        "validation/datetime/now": frozenset({0}),
        "caml/date/today_offset": frozenset({7, -1}),
    }


def test_a_today_default_is_reported_with_its_column_kind() -> None:
    usage = clock_usage(_schema(), make_bundle(entities=["Task"]).mapping, ["Task"])
    assert usage.cells == {}
    assert usage.today_defaults == (
        TodayDefault(entity="Task", column="Raised", column_kind="date"),
    )


def test_a_view_window_on_a_system_column_is_a_cell_too() -> None:
    """Modified and Created are datetime columns every list has; a view may
    filter on them without the schema declaring them."""
    bundle = make_bundle(
        entities=["Task"],
        views={"Task": [ViewDef(title="Recent", fields=["Title"], where=Group("all_of", (
            Leaf(field="Modified", op="geq", value="today-1"),
        )))]},
    )
    usage = clock_usage(_schema(), bundle.mapping, ["Task"])
    assert dict(usage.cells) == {"caml/datetime/today_offset": frozenset({-1})}


def test_uses_today_means_today_or_a_default_and_not_now() -> None:
    """assess's time_zone finding is about `today`; `now` compares with the
    save instant and never reads a date."""
    now_only = make_bundle(
        entities=["Task"],
        column_validation={"Task": EntitySection(columns={
            "OccurredAt": _rule("OccurredAt", "leq", "now"),
        })},
    )
    plain = make_schema(make_table(
        "Task", column("Title", required=True), column("OccurredAt", "datetime"),
    ))
    assert clock_usage(plain, now_only.mapping, ["Task"]).uses_today is False
    assert clock_usage(_schema(), now_only.mapping, ["Task"]).uses_today is True  # the default
    dated = make_bundle(
        entities=["Task"],
        column_validation={"Task": EntitySection(columns={"Due": _rule("Due", "leq", "today")})},
    )
    assert clock_usage(plain, dated.mapping, ["Task"]).uses_today is False  # Due is not on `plain`
    assert clock_usage(_schema(), dated.mapping, ["Task"]).uses_today is True


def test_only_the_tables_named_are_scanned() -> None:
    bundle = make_bundle(
        entities=["Task"],
        column_validation={"Task": EntitySection(columns={"Due": _rule("Due", "leq", "today")})},
    )
    usage = clock_usage(_schema(), bundle.mapping, [])
    assert usage.cells == {} and usage.today_defaults == ()
