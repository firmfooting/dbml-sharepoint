# test/test_jsgen_views.py
"""Views: the CAML the deploy writes, and the view rows the schema carries.

The declared views and the generated All Items, their filters, sorts, group
levels, widths and totals. The filter guard is here too: a view emitted in
the editable shape is one an operator can silently widen.
"""

from pathlib import Path
from typing import Any

import pytest
from _builders import ID_PK, TITLE, table
from _packs import blocks, entities, entity, pack, with_tail, write_dbml, write_mapping
from _paths import FIXTURES, SOLUTION_TEMPLATES
from test_jsgen import _generate_simple_js, _generate_views_js, _schema_json_for

from dbml_sharepoint.analysis.condition_rendering import CAML_VIEW_FILTER_GUARD
from dbml_sharepoint.analysis.phases import phase_number as pn
from dbml_sharepoint.analysis.typemap import TOTAL_FUNCTIONS
from dbml_sharepoint.generators.jsgen import (
    UNMANAGED,
    _view_aggregations,
    _view_caml_query,
    build_schema_json,
)
from dbml_sharepoint.model.conditions import parse_condition
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import ViewDef, ViewGroupBy, ViewSort
from dbml_sharepoint.model.parser import parse_dbml

# --- Declared views ---------------------------------------------------------


def _caml(view_kwargs: dict[str, Any], column_types: dict[str, str] | None = None) -> str:
    return _view_caml_query(
        ViewDef(title="V", fields=["Title"], **view_kwargs),
        column_types or {},
    )


def test_view_caml_condition_sort_and_group() -> None:
    caml = _caml(
        dict(
            where=parse_condition([{"field": "Status", "op": "neq", "value": "Closed"}], "w"),
            sort=[ViewSort(field="RiskScore", direction="desc")],
            group_by=ViewGroupBy(fields=["Impact"], collapsed=True),
        ),
        {"Status": "status_enum", "RiskScore": "calculated_number", "Impact": "impact_enum"},
    )
    assert caml == (
        '<GroupBy Collapse="TRUE"><FieldRef Name="Impact"/></GroupBy>'
        '<Where><And><Or><IsNull><FieldRef Name="Status"/></IsNull>'
        '<Neq><FieldRef Name="Status"/>'
        '<Value Type="Text">Closed</Value></Neq></Or>'
        f"{CAML_VIEW_FILTER_GUARD}</And></Where>"
        '<OrderBy><FieldRef Name="RiskScore" Ascending="FALSE"/></OrderBy>'
    )


def test_view_caml_renders_two_group_levels_in_one_groupby() -> None:
    """SharePoint takes both FieldRefs inside ONE GroupBy. Two GroupBy
    elements would be malformed CAML, not a deeper grouping."""
    caml = _caml(
        dict(group_by=ViewGroupBy(fields=["SourceType", "SourceInstrument"], collapsed=False)),
        {"SourceType": "source_enum", "SourceInstrument": "nvarchar"},
    )
    assert caml == (
        '<GroupBy Collapse="FALSE">'
        '<FieldRef Name="SourceType"/><FieldRef Name="SourceInstrument"/>'
        "</GroupBy>"
    )


def test_view_caml_ands_multiple_conditions() -> None:
    caml = _caml(
        dict(where=parse_condition(
            [
                {"field": "Status", "op": "eq", "value": "Open"},
                {"field": "SortOrder", "op": "geq", "value": 5},
                {"field": "Owner", "op": "is_not_null"},
            ],
            "w",
        )),
        {"Status": "status_enum", "SortOrder": "int", "Owner": "person"},
    )
    assert caml == (
        "<Where><And><And><And>"
        '<Eq><FieldRef Name="Status"/><Value Type="Text">Open</Value></Eq>'
        '<Geq><FieldRef Name="SortOrder"/><Value Type="Number">5</Value></Geq>'
        "</And>"
        '<IsNotNull><FieldRef Name="Owner"/></IsNotNull>'
        "</And>"
        f"{CAML_VIEW_FILTER_GUARD}</And></Where>"
    )


def test_view_caml_today_offsets_and_ascending_sort() -> None:
    caml = _caml(
        dict(
            where=parse_condition([{"field": "DueDate", "op": "leq", "value": "today+30"}], "w"),
            sort=[ViewSort(field="DueDate", direction="asc")],
        ),
        {"DueDate": "date"},
    )
    assert caml == (
        '<Where><And><Leq><FieldRef Name="DueDate"/>'
        '<Value Type="DateTime"><Today OffsetDays="30"/></Value></Leq>'
        f"{CAML_VIEW_FILTER_GUARD}</And></Where>"
        '<OrderBy><FieldRef Name="DueDate"/></OrderBy>'
    )
    bare = _caml(
        dict(where=parse_condition([{"field": "DueDate", "op": "eq", "value": "today"}], "w")),
        {"DueDate": "datetime"},
    )
    assert '<Value Type="DateTime"><Today/></Value>' in bare
    minus = _caml(
        dict(where=parse_condition([{"field": "DueDate", "op": "gt", "value": "today-7"}], "w")),
        {"DueDate": "date"},
    )
    assert '<Today OffsetDays="-7"/>' in minus


def test_view_caml_escapes_values_and_maps_boolean() -> None:
    caml = _caml(
        dict(where=parse_condition([{"field": "Name", "op": "eq", "value": 'A & B < "C"'}], "w")),
        {"Name": "nvarchar"},
    )
    assert '<Value Type="Text">A &amp; B &lt; &quot;C&quot;</Value>' in caml
    flag = _caml(
        dict(where=parse_condition([{"field": "Active", "op": "eq", "value": True}], "w")),
        {"Active": "boolean"},
    )
    assert '<Value Type="Integer">1</Value>' in flag


def test_schema_json_carries_declared_views(tmp_path: Path) -> None:
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            """
            Enum status {
              "Open"
              "Closed"
            }
            """,
            table("Risk", ID_PK, TITLE, "Status status", "DueDate date"),
        ),
        mapping=blocks(entities("Risk"), """
            views:
              Risk:
                - title: Open risks
                  renamed_from: [Active risks]
                  default: true
                  fields: [Title, Status, DueDate]
                  where:
                    - { field: Status, op: neq, value: Closed }
                  sort:
                    - { field: DueDate, direction: asc }
                  row_limit: 100
        """),
    )
    schema_json = build_schema_json(schema, bundle, "default")
    assert [view["title"] for view in schema_json["views"]] == [
        "Open risks", "All Items",
    ]
    declared, all_items = schema_json["views"]
    assert all_items["set_default"] is False
    assert all_items["hidden"] is True
    assert all_items["caml_query"] == ""
    assert declared == {
        "list": "APP_Risk",
        "title": "Open risks",
        "view_fields": ["Title", "Status", "DueDate"],
        "caml_query": (
            '<Where><And><Or><IsNull><FieldRef Name="Status"/></IsNull>'
            '<Neq><FieldRef Name="Status"/>'
            '<Value Type="Text">Closed</Value></Neq></Or>'
            f"{CAML_VIEW_FILTER_GUARD}</And></Where>"
            '<OrderBy><FieldRef Name="DueDate"/></OrderBy>'
        ),
        # No scope declared on a list view: null leaves the live property alone.
        "scope": None,
        # No totals declared: the empty string is what the deploy reads as
        # "never touch the live Aggregations property".
        "aggregations": "",
        "row_limit": 100,
        "set_default": True,
        "renamed_from": ["Active risks"],
        "hidden": False,
        "formatting": None,
        "widths": None,
        "url_slug": "OpenRisks",
        # A DECLARED view never adopts a page it did not create, on either
        # kind. The flag is the generated All Items on a library and nothing
        # else, which is what keeps the foreign-view guard standing here.
        "adopts_builtin_view": False,
    }


def test_view_widths_emitted_by_display_name(tmp_path: Path) -> None:
    """ColumnWidth FieldRefs bind by DISPLAY title (live finding: internal
    names are accepted but silently reset widths), so the generator rewrites
    widths keys with display_name_for (the same generation-time rewrite
    calculated formulas and form bodies use)."""
    schema, bundle = pack(
        tmp_path,
        dbml=table("Risk", ID_PK, TITLE, "DueDate date"),
        mapping=blocks(entities("Risk"), """
            display_names:
              mode: auto
            views:
              Risk:
                - title: Sized
                  fields: [Title, DueDate]
                  widths:
                    Title: 240
                    DueDate: 150
        """),
    )
    schema_json = build_schema_json(schema, bundle, "default")
    sized = next(view for view in schema_json["views"] if view["title"] == "Sized")
    assert sized["widths"] == {"Title": 240, "Due Date": 150}


def test_schema_json_adds_unfiltered_all_items_with_every_supported_column() -> None:
    schema = parse_dbml(FIXTURES / "calculated.dbml")
    bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    assert build_schema_json(schema, bundle, "default")["views"] == [{
        "list": "APP_Risk",
        "title": "All Items",
        "view_fields": [
            "ID", "Title", "Severity", "RiskScore", "RiskBand",
            "Created", "Modified", "Author", "Editor",
        ],
        "caml_query": "",
        "scope": None,
        "aggregations": "",
        "row_limit": None,
        "set_default": True,
        "renamed_from": [],
        "hidden": False,
        "formatting": None,
        "widths": None,
        "url_slug": "AllItems",
        # A LIST's built-in view is already titled All Items, so the title
        # matcher adopts it and nothing here may adopt by URL.
        "adopts_builtin_view": False,
    }]


def test_view_probe_treats_missing_view_400_as_absent(tmp_path: Path) -> None:
    """views/getbytitle signals a missing view the same way
    fields/getbyinternalnameortitle signals a missing field: HTTP 400
    System.ArgumentException ("The specified view is invalid."), code
    -2147024809, NOT 404. Treating only 404 as absent made Phase 3.1 fail
    its probe on every view it was about to create (seen live on a register
    deployment). Both probes must share one absent-detection helper so the
    next by-name getter cannot reintroduce this bug."""
    js = _generate_views_js(tmp_path)
    view_probe = js.split("async function readViewShape")[1].split("async function")[0]
    assert "isAbsent400(r.status, text)" in view_probe
    assert "return null" in view_probe
    assert "view shape probe failed" in view_probe


def test_view_query_comparison_tolerates_space_before_self_close(
    tmp_path: Path,
) -> None:
    """SharePoint's ViewQuery readback writes self-closing tags with a space
    (`<FieldRef Name="X" />` for a declared `<FieldRef Name="X"/>`), so the
    normalized comparison must collapse whitespace before `/>` as well as
    between tags. Otherwise every created view immediately fails its own
    verification (seen live on a register deployment)."""
    js = _generate_views_js(tmp_path)
    normalizer = js.split("const normalizeViewQuery")[1].split("\n")[0]
    assert "replace(/\\s+\\/>/g, '/>')" in normalizer
    assert "replace(/>\\s+</g, '><')" in normalizer


def test_deploy_js_phase_3c_provisions_and_reconciles_views(tmp_path: Path) -> None:
    """Fields created through the REST field collection join no view. The
    generated All Items recovery view and authored views are part of the
    physical shape: Phase 3.1 creates missing views, reconciles
    ViewQuery/RowLimit/field order/default flag on existing ones (public
    views only; a same-name personal view fails closed), verifies by
    readback, and never touches other views (user content, unlike exact
    ACLs)."""
    js = _generate_views_js(tmp_path)
    assert f"Starting Phase {pn('views')}: views" in js
    assert "const deployView = async (view)" in js
    assert "mapLanes(SCHEMA.views, (view) => view.list, deployView" in js
    # create path
    assert "'SP.View'" in js
    assert "PersonalView: false" in js
    # reconcile paths
    assert "is a personal view; declared views must be public" in js
    assert "normalizeViewQuery" in js
    assert "removeallviewfields" in js
    assert "addviewfield('${odataName(name)}')" in js
    assert "DefaultView: true" in js
    # Case-insensitively: SharePoint resolves a view by title that way and
    # refuses two views on one list differing only in case, so a previous
    # title recorded with different casing must still be adopted rather
    # than left behind while a duplicate is created beside it.
    assert "view.renamed_from.some((t) => nameKey(t) === nameKey(v.Title))" in js
    assert "multiple previous-title views exist" in js
    assert "Hidden: view.hidden" in js
    assert "actual.Hidden !== view.hidden" in js
    assert "$select=Id,Title,DefaultView,Hidden,RowLimit" in js
    # verification + fail-closed error routing
    assert "did not retain declared view setting(s)" in js
    assert "phase: '3.1'" in js
    # runs between field defaults and ACL work
    assert js.index(f"Starting Phase {pn('defaults')}") < js.index(
        f"Starting Phase {pn('views')}") < js.index(
        f"Starting Phase {pn('acls')}",
    )
    # rendered SCHEMA carries the view declaration
    assert '"Open risks"' in js
    assert '"set_default": true' in js


def test_views_created_with_slug_then_renamed(tmp_path: Path) -> None:
    """A view's .aspx name is fixed at creation from its Title, so creating
    with the display title bakes %20 into the URL forever. Create with the
    URL slug, then MERGE Title to the declared display title (renames never
    touch the URL). Existing escaped-URL declared views are migrated by
    recreate (deployer-owned), with the URL in the fail-closed drift gate."""
    js = _generate_views_js(tmp_path)
    assert "Title: view.url_slug" in js
    assert "ServerRelativeUrl" in js
    # Rename to the declared title after create (skipped when identical).
    assert "view.url_slug !== view.title" in js
    # Migration path for existing views under an escaped URL.
    assert "clean URL" in js
    assert "'X-HTTP-Method': 'DELETE'" in js
    # Fail closed: URL basename must verify like every declared setting.
    assert "Url (declared" in js


def test_widths_apply_via_guarded_setviewxml(tmp_path: Path) -> None:
    """Widths ride the whole-document SetViewXml() surface the modern Lists
    UI uses (live capture 2026-07-24). Property MERGEs on ListViewXml are
    DESTRUCTIVE (live finding: every view reset to the blank default), so
    the generated step must be read → splice ONLY ColumnWidth → write, with
    a diff-guard refusing any other change and a fail-closed readback."""
    js = _generate_views_js(tmp_path)
    # Read side: the server's own full serialization, fresh each time.
    assert "$select=ListViewXml" in js
    # Write side: the method call, never a MERGE of ListViewXml.
    assert "/setviewxml()" in js
    assert "ListViewXml:" not in js  # no MERGE body carrying the property
    # Splice + guard + fail-closed verify.
    assert "<ColumnWidth>" in js
    assert "stripColumnWidth" in js
    assert "widths splice guard" in js
    assert "did not retain declared column widths" in js


def test_retired_columns_leave_views_but_stay_deployed() -> None:
    """The end-to-end proof that retirement needs no jsgen change: the
    column is still created and still deployer-managed (so the drift audit
    stays clean) but it is hidden from the New form, carries the retired
    suffix, and has left every declared view."""
    schema = parse_dbml(FIXTURES / "retired.dbml")
    bundle = load_mapping(FIXTURES / "retired-mapping.yaml")

    schema_json = build_schema_json(schema, bundle, "default")

    board = next(lst for lst in schema_json["lists"] if lst["title"] == "APP_Board")
    ops = next(f for f in board["fields_phase1"] if f["title"] == "OperationsStatus")
    # Present on the Edit and Display forms, absent from New: [$ID] is empty
    # only while the item is being created.
    assert ops["client_validation_formula"] == "=if([$ID] != '', 'true', 'false')"
    assert ops["display_title"] == "Operations Status (retired)"
    live = next(
        f for f in board["fields_phase1"] if f["title"] == "SiteServicesStatus"
    )
    # `declared` reconcile: a live column of the same list is untouched.
    assert live["client_validation_formula"] == UNMANAGED
    assert live["display_title"] == "Site Services Status"

    view = next(v for v in schema_json["views"] if v["title"] == "Heat grid")
    assert view["view_fields"] == ["BoardDate", "SiteServicesStatus"]


def test_view_fields_reach_jsgen_flat_and_resolved(tmp_path: Path) -> None:
    """jsgen has no field-set awareness by design: ViewDef.fields is always
    already a flat, resolved, de-duplicated list of internal column names by
    the time build_schema_json reads it. A failure here means expansion has
    leaked past the loader."""
    schema, bundle = pack(
        tmp_path,
        dbml=table(
            "Board", ID_PK, TITLE,
            "BoardDate date",
            "OperationsStatus nvarchar",
            "WorkforceStatus nvarchar",
        ),
        mapping=blocks(entities("Board"), """
            field_sets:
              Board:
                header:   [Title, BoardDate]
                statuses: [OperationsStatus, WorkforceStatus]
            views:
              Board:
                - title: Heat grid
                  fields: ["@header", "@statuses", BoardDate]
        """),
    )
    schema_json = build_schema_json(schema, bundle, "default")
    view_fields = next(
        view for view in schema_json["views"] if view["title"] == "Heat grid"
    )["view_fields"]
    assert view_fields == [
        "Title", "BoardDate", "OperationsStatus", "WorkforceStatus",
    ]
    assert not any(name.startswith("@") for name in view_fields)


# --- Declared view totals ---------------------------------------------------


def _aggregations(totals: dict[str, str]) -> str:
    return _view_aggregations(ViewDef(title="V", fields=["Title"], totals=totals))


def test_view_aggregations_concatenate_in_declaration_order() -> None:
    """Order matters twice over: it is the order SharePoint renders the
    figures in, and the deployer compares the whole string exactly, so a
    reordering would drift on every redeploy."""
    assert _aggregations({"TripKm": "sum", "Days": "avg"}) == (
        '<FieldRef Name="TripKm" Type="SUM"/><FieldRef Name="Days" Type="AVG"/>'
    )


def test_every_function_renders_the_token_sharepoint_documents() -> None:
    """The tokens transcribed from Microsoft's FieldRef element (Query)
    reference, which enumerates exactly AVG, COUNT, MAX, MIN, SUM, STDEV
    and VAR:
    https://learn.microsoft.com/sharepoint/dev/schema/fieldref-element-query

    Written out LITERALLY and taken from that reference rather than from
    English. Deriving them from TOTAL_FUNCTIONS would be tautological, and
    typing the function's name instead of its token yields values like
    "Average" that SharePoint stores, round-trips, and then fails the whole
    view over. A literal test is only as good as the source the literal
    came from.
    """
    assert _aggregations({"A": "sum"}) == '<FieldRef Name="A" Type="SUM"/>'
    assert _aggregations({"A": "count"}) == '<FieldRef Name="A" Type="COUNT"/>'
    assert _aggregations({"A": "avg"}) == '<FieldRef Name="A" Type="AVG"/>'
    assert _aggregations({"A": "min"}) == '<FieldRef Name="A" Type="MIN"/>'
    assert _aggregations({"A": "max"}) == '<FieldRef Name="A" Type="MAX"/>'
    assert _aggregations({"A": "stdev"}) == '<FieldRef Name="A" Type="STDEV"/>'
    assert _aggregations({"A": "var"}) == '<FieldRef Name="A" Type="VAR"/>'


def test_no_aggregation_token_is_an_english_word_sharepoint_does_not_know() -> None:
    """`Average`, `Minimum`, `Maximum`, `Total` and `Mean` are what an
    author reaches for when transcribing from memory instead of from the
    enumeration. None is a member of it, and a non-member breaks the view
    rather than being rejected."""
    invented = {"Average", "Minimum", "Maximum", "Total", "Mean"}
    present = invented & set(TOTAL_FUNCTIONS.values())
    assert not present, (
        f"{sorted(present)} are not SharePoint aggregation tokens. The enumeration is "
        f"AVG, COUNT, MAX, MIN, SUM, STDEV, VAR, and a non-member is stored, round-tripped, "
        f"and then breaks the view's rendering entirely."
    )


def test_every_declared_function_is_pinned_above() -> None:
    """Guards the guard: a sixth function added to TOTAL_FUNCTIONS without a
    literal assertion beside it would slip through unrendered-and-untested,
    which is exactly how the tautological version hid three of five."""
    assert set(TOTAL_FUNCTIONS) == {
        "sum", "count", "avg", "min", "max", "stdev", "var",
    }


def test_a_view_without_totals_renders_no_aggregations() -> None:
    """Empty is what the deploy reads as "never touch the live property"."""
    assert _aggregations({}) == ""


def test_a_grouped_column_need_not_be_displayed() -> None:
    """SharePoint renders the grouped value in the group HEADER, from the
    GroupBy FieldRef, independently of ViewFields, which is why grouping
    by a column you do not also list is a normal way to avoid repeating the
    same value in every row. Nothing may refuse it."""
    caml = _caml(
        dict(group_by=ViewGroupBy(fields=["Area"], collapsed=True)),
        {"Area": "area_enum"},
    )
    assert caml == '<GroupBy Collapse="TRUE"><FieldRef Name="Area"/></GroupBy>'


def test_a_casing_only_view_rename_does_not_deadlock() -> None:
    """`title: Open` with `renamed_from: [open]` matches ONE live view under
    case-insensitive comparison. Counting it as both the current view and a
    competing previous-title view makes the conflict check refuse to choose
    between a view and itself, on every run, so the rename never lands."""
    js = _generate_simple_js()
    block = js[js.index("const previousMatches = listedViews.filter("):]
    block = block[: block.index("if (previousMatches.length > 1)")]
    assert "!existing || v.Id !== existing.Id" in block, (
        "previousMatches must exclude the view already matched as current"
    )


def _hide_fixture(tmp_path: Path, hide_line: str) -> Path:
    """A Task list with two Person columns, plus one declared view.

    `hide_line` is spliced INSIDE the Task entity block, so its four-space
    indent is what says where it goes: pass `"    hide_from_all_items: [...]\\n"`
    or `""`. `with_tail` appends it verbatim for exactly that reason.
    `blocks()` would dedent the lone indented line flat and reparent it to the
    top level of the mapping, silently (see `_packs.with_tail`).
    """
    write_dbml(tmp_path, table("Task", ID_PK, TITLE, "Owner person", "Reviewer person"))
    write_mapping(
        tmp_path,
        # The outer `blocks()` dedent is a no-op on the first part: it already
        # begins with `entities:` at column zero, so the common prefix is empty
        # and the tail's indentation survives.
        blocks(
            with_tail("""
                entities:
                  Task:
                    kind: List
                    base_template: 100
                    site_role: default
            """, hide_line),
            """
            views:
              Task:
                - title: Mine
                  fields: [Title, Owner, Reviewer]
            """,
        ),
    )
    return tmp_path


def _all_items_fields(tmp_path: Path) -> list[str]:
    schema_json = build_schema_json(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"), "default",
    )
    view = next(v for v in schema_json["views"] if v["title"] == "All Items")
    fields: list[str] = view["view_fields"]
    return fields


def test_all_items_renders_everything_without_the_key(tmp_path: Path) -> None:
    """The control. If this list ever changes for an unrelated reason, fix the
    expectation in BOTH tests. The pair is what proves the omission."""
    _hide_fixture(tmp_path, "")
    assert _all_items_fields(tmp_path) == [
        "ID", "Title", "Owner", "Reviewer", "Created", "Modified", "Author", "Editor",
    ]


def test_all_items_omits_hidden_columns_and_nothing_else(tmp_path: Path) -> None:
    _hide_fixture(tmp_path, "    hide_from_all_items: [Author, Editor, Owner]\n")
    assert _all_items_fields(tmp_path) == [
        "ID", "Title", "Reviewer", "Created", "Modified",
    ]


def test_a_declared_view_keeps_a_hidden_column(tmp_path: Path) -> None:
    """hide_from_all_items affects ONLY the generated view."""
    _hide_fixture(tmp_path, "    hide_from_all_items: [Author, Editor, Owner]\n")
    schema_json = build_schema_json(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"), "default",
    )
    mine = next(v for v in schema_json["views"] if v["title"] == "Mine")
    assert mine["view_fields"] == ["Title", "Owner", "Reviewer"]


def test_an_entity_declaring_no_views_still_gets_all_items(tmp_path: Path) -> None:
    """A mapping with no `views:` section at all is valid, and its lists work.

    `All Items` is generated, never declared -- authors are refused if they
    try (`_views.py`'s "'All Items' is generated with every" error). So a
    template that ships no views is not shipping a list you cannot read; it
    ships one with the generated view, and with nothing declared to outrank
    it that view is the default and visible.

    Pinned because it is the invariant on the other side of #141's guard.
    `views: []` now refuses, and the reason that is safe to do is precisely
    that declaring no views has its own well-formed spellings -- an omitted
    section, `views:`, `views: {}`. A guard that crept into refusing those
    would break every mapping that never wanted a view, and the deploy would
    still look fine right up until it was not.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=table("Risk", ID_PK, TITLE, "DueDate date"),
        mapping=entities("Risk"),  # no `views:` section whatsoever
    )
    schema_json = build_schema_json(schema, bundle, "default")

    assert [view["title"] for view in schema_json["views"]] == ["All Items"]
    all_items = schema_json["views"][0]
    # Default AND visible: with nothing declared there is no authored view to
    # hand the working UI to, which is the opposite of the declared-view case
    # asserted in test_schema_json_carries_declared_views.
    assert all_items["set_default"] is True
    assert all_items["hidden"] is False


def _shipped_solution_ids() -> list[str]:
    """Discovered, never listed. A hardcoded roster fails open."""
    return sorted(
        path.parent.parent.name
        for path in SOLUTION_TEMPLATES.glob("*/10-design/schema.dbml")
    )


@pytest.mark.parametrize("solution_id", _shipped_solution_ids())
def test_every_shipped_view_filter_is_emitted_protected(solution_id: str) -> None:
    """No shipped view may be emitted in a shape the filter editor will open.

    Asserted on the EMITTED query rather than by calling the renderer, which
    would compare the renderer to itself and stay green if `jsgen` reverted to
    30 of the 192 shipped filtered views were already protected before this
    change, by which clause happened to render last. Counted 2026-08-17 by
    rendering every shipped `where` and taking those whose top node has a
    group in the right child.
    """
    for view in _schema_json_for(solution_id)["views"]:
        if "<Where>" not in view["caml_query"]:
            continue
        assert CAML_VIEW_FILTER_GUARD in view["caml_query"], (
            f"{solution_id}/{view['list']}/{view['title']}"
        )


def test_the_shipped_corpus_still_declares_filtered_views() -> None:
    """The per-solution test above passes vacuously on a corpus with none.

    Measured 2026-08-17: 192 filtered views. The floor is well under that,
    because the real number moves whenever a family gains a view and pinning
    it exactly would fail for the wrong reason.
    """
    total = sum(
        1
        for solution_id in _shipped_solution_ids()
        for view in _schema_json_for(solution_id)["views"]
        if "<Where>" in view["caml_query"]
    )
    assert total > 100, total


def test_every_declared_view_filter_is_emitted_protected() -> None:
    """No emitted view may be left in a shape the filter editor will open.

    A view the editor opens is one an operator can truncate to ten conditions
    by pressing Save, with nothing in the build or the deploy able to see it
    happen. Measured 2026-08-17 on caml-chain-depth-probe.js:
    `view.filter-editor.ui-chain-40` watched a save rewrite forty conditions to
    ten, and `view.filter-editor.wrapper-group-left-editable` against
    `view.filter-editor.wrapper-group-right-editable` isolated a group in the
    right child as what the editor refuses.
    """
    filtered = 0
    for view in _schema_json_for("risk-register")["views"]:
        if "<Where>" not in view["caml_query"]:
            continue
        filtered += 1
        assert CAML_VIEW_FILTER_GUARD in view["caml_query"], view["title"]
    # Without this the loop passes vacuously on a family that stopped
    # declaring filters, which is the shape this suite has shipped before.
    assert filtered > 0


def test_a_view_with_no_filter_gains_no_where_clause() -> None:
    """An unfiltered view must stay editable.

    Measured 2026-08-17 (view-edit-page-probe.js
    `view.filter-editor.control-unfiltered-view`, F7): an unfiltered view's
    edit page carries the filter editor's controls, so it reads as
    unprotected and must remain so. Guarding it would also invent a <Where>
    for a view whose author declared none.
    """
    unfiltered = [
        view for view in _schema_json_for("risk-register")["views"]
        if "<Where>" not in view["caml_query"]
    ]
    # `assert unfiltered` is the whole test: the comprehension already
    # selected on the absence of a <Where>, and the guard is only ever emitted
    # inside one, so a per-view assertion below could not fail.
    assert unfiltered


def test_only_a_librarys_generated_all_items_may_adopt_the_view_on_its_url(
    tmp_path: Path,
) -> None:
    """The flag that narrows the view phase's foreign-view guard, and the test
    that keeps it narrow.

    MEASURED 2026-09-13 in library-builtin-view-probe.js: a bare library's
    view on AllItems.aspx reads 'All Documents'
    (`library.view.builtin-occupies-allitems`) and a second view created under
    the slug is minted AllItems1.aspx
    (`library.view.create-allitems-title-on-library`), so on a library that URL
    can only ever hold the built-in view. A generic LIST ships 'All Items'
    there (`library.view.control-list-builtin-occupies-allitems`) and is
    adopted by title, reaching no URL match at all.

    Every other view stays under the guard: a declared view whose .aspx is
    already taken by somebody else's page fails the run closed rather than
    renaming a view it did not create.
    """
    declared = """
        views:
          Doc:
            - title: "By division"
              fields: [Title, Division]
    """

    def views_of(kind: str, template: int, where: Path) -> list[dict[str, Any]]:
        where.mkdir(parents=True, exist_ok=True)
        schema, bundle = pack(
            where,
            dbml=table("Doc", ID_PK, TITLE, "Division nvarchar"),
            mapping=blocks(
                entities(entity("Doc", kind=kind, base_template=template)), declared,
            ),
        )
        views: list[dict[str, Any]] = build_schema_json(schema, bundle, "default")["views"]
        return views

    library = views_of("DocumentLibrary", 101, tmp_path / "library")
    assert {v["title"] for v in library} == {"All Items", "By division"}
    adopting = {v["title"] for v in library if v["adopts_builtin_view"]}
    assert adopting == {"All Items"}, adopting

    as_list = views_of("List", 100, tmp_path / "list")
    assert {v["title"] for v in as_list} == {"All Items", "By division"}
    assert not any(v["adopts_builtin_view"] for v in as_list)
