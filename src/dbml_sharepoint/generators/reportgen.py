# src/dbml_sharepoint/generators/reportgen.py
"""Report-query generator: Power Query (M) and T-SQL views from the schema.

The same DBML + mapping that provisions the lists also describes how to
report on them. This module emits:

- one Power Query (M) query per list, ``OData.Feed`` against the list's
  REST endpoint, with lookup and person columns expanded to a join key plus
  display column, and column types applied from the deployer's own typemap.
  ``build`` knows the site (``--site-url``) and bakes it into every query,
  so a shipped bundle has nothing to configure; the standalone ``report``
  command knows no site and falls back to a ``SiteUrl`` text parameter;
- a single T-SQL script of ``CREATE OR ALTER VIEW`` statements (SQLCMD
  variables for the landing/report schemas): a typed view per list plus an
  ``_Enriched`` view joining each lookup to its display column, for lists
  landed in a warehouse by any extract process;
- guide.md with usage instructions and the Power BI relationship table
  derived from the DBML refs.

Cross-site reference columns are extension-expanded at deploy time into
shapes the core cannot know; they are skipped here and listed in
guide.md. Person columns land differently per extract tool, so the SQL
views carry them as display-name text while the M queries expand both the
site-user id and display name.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dbml_sharepoint import __version__
from dbml_sharepoint.analysis.condition_description import describe
from dbml_sharepoint.analysis.exports import MULTI_VALUE_JOIN, ambiguous_members
from dbml_sharepoint.analysis.lookups import (
    display_column_for,
    lookup_display_columns,
)
from dbml_sharepoint.analysis.ordering import is_deployed_here
from dbml_sharepoint.analysis.report_columns import (
    REPORT_FIXED_COLUMNS,
    REPORT_KEY_SUFFIX,
)
from dbml_sharepoint.analysis.typemap import CALCULATED_TYPES, SPField, map_column
from dbml_sharepoint.bundle import (
    REPORT_DICTIONARY,
    REPORT_DIR,
    REPORT_GUIDE,
    REPORT_VIEWS_SQL,
    write_artifact,
)
from dbml_sharepoint.generators._indexes import deployable_index_columns
from dbml_sharepoint.model.mapping_types import MappingBundle
from dbml_sharepoint.model.parser import Schema, Table
from dbml_sharepoint.model.release import Release


@dataclass
class _ListPlan:
    """Everything the renderers need for one list, in DBML column order."""

    entity: str
    list_title: str
    selects: list[str] = field(default_factory=list)
    expands: list[str] = field(default_factory=list)
    # (record column, inner field, expanded output column, M type token)
    #
    # The type is carried here rather than looked up in `m_types` because the
    # expand is emitted GUARDED (see `_render_m`): when the source record
    # column is absent (which is what an EMPTY list gives you), the output
    # column is added as nulls instead, and that fallback has to ascribe a
    # type at the point it is written.
    record_expands: list[tuple[str, str, str, str]] = field(default_factory=list)
    # (output column, M type token)
    m_types: list[tuple[str, str]] = field(default_factory=list)
    # Multi-value columns joined to one text cell. Deliberately NOT in
    # `m_types`: the join step ascribes their type, because the raw list must
    # never reach `Table.TransformColumnTypes` at all.
    multi_value_joins: list[str] = field(default_factory=list)
    # (landed column, SQL type)
    sql_columns: list[tuple[str, str]] = field(default_factory=list)
    # (fk column, target list title, target display column)
    joins: list[tuple[str, str, str]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    # Site-relative path of the item display form, ending in "?ID=". The
    # ItemURL helper column is SiteUrl + this + the item id.
    item_url_path: str = ""
    # (internal/out column, model-facing display name), populated only when
    # the mapping declares display_names; the rename is the LAST query step
    # so internal names remain the wire/OData contract.
    renames: list[tuple[str, str]] = field(default_factory=list)
    # Declared internal field names (no cross-site, no Id), the expected
    # set for the user-added-column audit; cross-site names ride
    # ``skipped``.
    field_internal_names: list[str] = field(default_factory=list)


def _tables_for_role(schema: Schema, bundle: MappingBundle, site_role: str) -> list[Table]:
    """Schema-order tables mapped to the requested site role.

    The MEMBERSHIP question is `ordering.is_deployed_here`, shared with the
    generators that deploy: an entity absent from the mapping or belonging to
    another role is not provisioned at this site, so it must not be reported
    there either. Only the ORDER differs (declaration order here, dependency
    order there), and a report has no creation sequence to respect.

    This used to re-implement the predicate and say "same filter as jsgen" in
    its docstring, which is a claim nothing checked.
    """
    return [
        table
        for table in schema.tables
        if is_deployed_here(bundle.mapping.entities, table.name, site_role)
    ]


def _refuse_ambiguous_members(column: str, members: list[str]) -> None:
    """Refuse a choice set the joined cell could not be split back into.

    A BACKSTOP, not the primary control. `MULTI_VALUE_MEMBER_CONTAINS_THE_
    EXPORT_SEPARATOR` is the rule an author should meet, and `build` reaches
    it before this can fire.

    This exists because `report` does not validate. It is a supported
    command with no site URL, it renders straight from the schema, and
    without this guard it emits a Power Query cell joined on `"; "` from
    members that themselves contain `"; "` -- while the data dictionary
    beside it tells the reader to split on that string. The artifact is
    well-formed, the command exits 0, and any count taken from the export
    is wrong with nothing able to notice.

    So do NOT delete this on the reasoning that the validator now covers it.
    It was deleted once for exactly that reason and `report` silently
    started shipping the lossy bundle; the deletion was reverted with a test
    (`test_report_refuses_a_member_the_export_cannot_split_back`) that fails
    when it goes again. The knowledge is not duplicated -- both this and the
    validator ask `analysis/exports.ambiguous_members`, which is the one
    place the rule is written.
    """
    offending = ambiguous_members(members)
    if not offending:
        return
    raise ValueError(
        f"{column}: multi-value choice member(s) "
        f"{', '.join(repr(member) for member in offending)} contain "
        f'"{MULTI_VALUE_JOIN}", which is the separator the exported cell '
        f"joins members with. A set holding such a member joins to the same "
        f"text as a set holding its parts, so the export cannot be split back "
        f"into what the row actually held and any count of selections taken "
        f"from it is wrong with nothing able to notice. Rename the member, or "
        f"model the column as a child entity with one row per value.",
    )


def _display_column(bundle: MappingBundle, target_entity: str) -> str:
    """What a lookup into `target_entity` shows, the same column jsgen sets
    as the field's `LookupField`. One home: `analysis.lookups`."""
    return display_column_for(bundle.mapping.entities.get(target_entity))


def _item_url_path(bundle: MappingBundle, entity_name: str, list_title: str) -> str:
    """Site-relative display-form path for one item, ending in ``?ID=``.

    Lists live under /Lists/<Title>/; document libraries put their forms
    under /<Title>/Forms/.
    """
    entity = bundle.mapping.entities.get(entity_name)
    if entity is not None and entity.kind == "DocumentLibrary":
        return f"/{list_title}/Forms/DispForm.aspx?ID="
    return f"/Lists/{list_title}/DispForm.aspx?ID="


def _build_plans(
    schema: Schema, bundle: MappingBundle, site_role: str,
) -> list[_ListPlan]:
    tables = _tables_for_role(schema, bundle, site_role)
    emitted = {t.name for t in tables}
    enum_names = {e.name for e in schema.enums}
    enum_members = {e.name: e.members for e in schema.enums}
    cross_site_keys = bundle.mapping.cross_site_keys()
    prefix = bundle.mapping.prefix

    plans: list[_ListPlan] = []
    for table in tables:
        plan = _ListPlan(
            entity=table.name,
            list_title=prefix + table.name,
            item_url_path=_item_url_path(bundle, table.name, prefix + table.name),
        )
        for col in table.columns:
            if (table.name, col.name) in cross_site_keys:
                plan.skipped.append(col.name)
                continue
            sp = map_column(col, enum_names)
            if sp.kind != "Skip":
                plan.field_internal_names.append(sp.name)
            match sp.kind:
                case "Skip":
                    plan.selects.append("Id")
                    plan.m_types.append(("Id", "Int64.Type"))
                    plan.sql_columns.append(("Id", "INT"))
                case "Text" | "Choice":
                    plan.selects.append(sp.name)
                    plan.m_types.append((sp.name, "type text"))
                    plan.sql_columns.append((sp.name, "NVARCHAR(255)"))
                case "Note":
                    plan.selects.append(sp.name)
                    plan.m_types.append((sp.name, "type text"))
                    plan.sql_columns.append((sp.name, "NVARCHAR(MAX)"))
                case "Number":
                    plan.selects.append(sp.name)
                    plan.m_types.append((sp.name, "type number"))
                    plan.sql_columns.append((sp.name, "DECIMAL(18,4)"))
                case "DateTime":
                    plan.selects.append(sp.name)
                    if sp.date_only:
                        plan.m_types.append((sp.name, "type date"))
                        plan.sql_columns.append((sp.name, "DATE"))
                    else:
                        plan.m_types.append((sp.name, "type datetimezone"))
                        plan.sql_columns.append((sp.name, "DATETIMEOFFSET"))
                case "Boolean":
                    plan.selects.append(sp.name)
                    plan.m_types.append((sp.name, "type logical"))
                    plan.sql_columns.append((sp.name, "BIT"))
                case "URL":
                    # SP.FieldUrlValue arrives as a record; keep the Url part.
                    plan.selects.append(sp.name)
                    plan.record_expands.append(
                        (sp.name, "Url", f"{sp.name}Url", "type text"),
                    )
                    plan.m_types.append((f"{sp.name}Url", "type text"))
                    plan.sql_columns.append((sp.name, "NVARCHAR(2000)"))
                case "User":
                    plan.selects.append(f"{sp.name}Id")
                    plan.selects.append(f"{sp.name}/Title")
                    plan.expands.append(sp.name)
                    plan.record_expands.append(
                        (sp.name, "Title", f"{sp.name}Title", "type text"),
                    )
                    plan.m_types.append((f"{sp.name}Id", "Int64.Type"))
                    plan.m_types.append((f"{sp.name}Title", "type text"))
                    plan.sql_columns.append((sp.name, "NVARCHAR(255)"))
                case "Lookup":
                    target = sp.target_list or ""
                    display = _display_column(bundle, target)
                    plan.selects.append(f"{sp.name}Id")
                    plan.selects.append(f"{sp.name}/{display}")
                    plan.expands.append(sp.name)
                    plan.record_expands.append(
                        (sp.name, display, f"{sp.name}{display}", "type text"),
                    )
                    plan.m_types.append((f"{sp.name}Id", "Int64.Type"))
                    plan.m_types.append((f"{sp.name}{display}", "type text"))
                    plan.sql_columns.append((f"{sp.name}Id", "INT"))
                    if target in emitted:
                        plan.joins.append(
                            (f"{sp.name}Id", prefix + target, display),
                        )
                case "MultiChoice":
                    # MEASURED 2026-08-10 on a live tenant: the item value
                    # reads back as a bare JSON array under `odata=nometadata`
                    # (the dialect the Power Query layer speaks) and as
                    # {"__metadata":...,"results":[...]} under `odata=verbose`,
                    # the deploy layer's. The two need not agree, and only the
                    # first one matters here: THE CELL HOLDS A LIST.
                    #
                    # Which is why this cannot ride the scalar Choice arm.
                    # `type text` over a list does not mistype the column, it
                    # puts an Error value in every populated cell while the
                    # query still loads (a report that renders and is wrong).
                    # The join therefore happens in its own step, before
                    # anything types anything, and that step ascribes the type.
                    #
                    # SQL takes the same joined string, and it is NVARCHAR(MAX)
                    # because a joined set has no bound worth guessing and a
                    # CAST that overflows truncates in silence. A joined string
                    # rather than a junction table because there is no
                    # junction-table machinery anywhere in this generator (no
                    # CROSS APPLY, no STRING_SPLIT, no OPENJSON) and none is
                    # being added here. One text cell is the only shape both
                    # targets can carry today.
                    #
                    # Which only works while the cell can be split back apart,
                    # so the members are checked before anything is planned.
                    # `report` does not validate, so this is its only guard.
                    _refuse_ambiguous_members(
                        sp.name, enum_members.get(sp.choices_enum or "", []),
                    )
                    plan.selects.append(sp.name)
                    plan.multi_value_joins.append(sp.name)
                    plan.sql_columns.append((sp.name, "NVARCHAR(MAX)"))
                case "Calculated":
                    plan.selects.append(sp.name)
                    if sp.output_type == 9:
                        plan.m_types.append((sp.name, "type number"))
                        plan.sql_columns.append((sp.name, "DECIMAL(18,4)"))
                    elif sp.output_type == 4:
                        plan.m_types.append((sp.name, "type date"))
                        plan.sql_columns.append((sp.name, "DATE"))
                    else:
                        plan.m_types.append((sp.name, "type text"))
                        plan.sql_columns.append((sp.name, "NVARCHAR(255)"))
                case _:
                    # WITHOUT THIS THE TWO DRIFT AUDITS CONTRADICT EACH OTHER,
                    # and neither of them can say so.
                    #
                    # `field_internal_names` is appended above, BEFORE this
                    # match, so an unhandled kind is recorded as a column the
                    # list is expected to have, while contributing no
                    # `$select`, no Power Query type and no SQL column.
                    # `_UserAddedColumns.pq` is built from that expected list,
                    # so the M audit sees a clean list; the SQL audit is built
                    # from `sql_columns`, so it reports the very same column as
                    # an unexpected user-added one. One deployment, two audits,
                    # opposite verdicts, and the column silently missing from
                    # every query that was supposed to carry it.
                    #
                    # A silently dropped column in an export is this project's
                    # failure class, so a new FieldKind has to fail the build
                    # here until somebody decides what it means in M and in
                    # SQL. There is no defensible default: guessing `type text`
                    # is what turns a multi-value column into a per-row error
                    # value, and guessing NVARCHAR(255) is what truncates one.
                    raise ValueError(
                        f"{table.name}.{col.name}: reporting has no plan for "
                        f"SharePoint field kind {sp.kind!r}. Add a case to "
                        f"reportgen._build_plans giving it a $select, a Power "
                        f"Query type and a SQL column type -- and a matching "
                        f"arm in _sp_type_cell -- rather than letting it fall "
                        f"out of every generated query.",
                    )
        if bundle.mapping.display_name_mode is not None:
            # Derived out-columns (FooId/FooTitle/FooUrl) resolve through the
            # same map: overrides hit exact column names, everything else
            # auto-splits ("RiskOwnerTitle" -> "Risk Owner Title").
            # `multi_value_joins` is listed alongside `m_types` because it is
            # the only output column NOT in `m_types`, and a renameable name
            # that this loop cannot see is a column that silently keeps its
            # internal name in a model where every other column got its
            # display title.
            for out_name in (
                [name for name, _ in plan.m_types]
                + plan.multi_value_joins
                + ["ItemURL"]
            ):
                display = bundle.mapping.display_name_for(table.name, out_name)
                if display != out_name:
                    plan.renames.append((out_name, display))
        plans.append(plan)
    return plans


# ---------------------------------------------------------------- Power Query


def _fk_key_column(fk_col: str) -> str:
    """The site-qualified name for a foreign key column.

    `IncidentId` becomes `Incident Key`, matching the `<Entity> Key` the
    target table exposes, so the relationship reads as one name on both
    sides. Spaced to sit alongside the other model-facing names, which are
    display titles rather than internal ones.
    """
    return f"{fk_col.removesuffix('Id')} Key"


def _m_string(text: str) -> str:
    """An M string literal: double quotes are escaped by doubling."""
    return '"' + text.replace('"', '""') + '"'


def _row_key_m(list_title: str, id_expression: str) -> str:
    """The M expression for one row key: site, LIST, and item id.

    THE ONE definition of the key format, used for both a table's own
    ``<Entity> Key`` and the ``<Target> Key`` every lookup carries. Those two
    are what a Power BI relationship joins, so a format written twice is a
    relationship that matches nothing, and matching nothing renders as
    empty visuals rather than as an error.

    MEASURED implicitly on a live tenant, 2026-08-11: the key was site + id
    with nothing naming the list. Every SharePoint list numbers its items
    from 1, so two lists on ONE site produce colliding keys the moment their
    queries are appended (the multi-site, multi-list model this pack's own
    guide tells the operator to build). Wrong row counts and wrong
    relationships, and nothing anywhere raises.

    The list TITLE, not its GUID, and deliberately: a GUID would survive a
    rename, but the query addresses the list by title in
    ``getbytitle('<title>')`` two steps above, so a rename breaks the query
    outright regardless. The title therefore adds no failure mode the query
    does not already have, and it costs no second round trip to the site.

    ``SiteRoot`` rather than the raw ``SiteUrl``: two operators pasting the
    same site in different shapes must produce the SAME key, or appending
    their copies breaks the relationship rather than the URL.
    """
    return (
        f'SiteRoot & "|" & {_m_string(list_title)} & "|" '
        f"& Number.ToText({id_expression})"
    )


def _site_url_binding_m(site_url: str | None) -> list[str]:
    """The literal ``SiteUrl`` binding for a top-level ``let``, or nothing.

    ``build`` is given the site (``--site-url``), so a bundle it produces
    can bind the URL here and the operator has nothing to set up. The
    standalone ``report`` command knows no site; it emits no binding, and
    the query reads the ``SiteUrl`` text parameter instead (the same name),
    so everything below is identical either way.

    The URL goes through :func:`_m_string` rather than being interpolated:
    it is operator input, and a ``"`` in it would otherwise close the
    literal and rewrite the rest of the query as M code.

    Indented for a top-level ``let`` binding (four spaces), matching
    :data:`_SITE_ROOT_M`, which is emitted immediately after it.
    """
    if site_url is None:
        return []
    return [
        "    // Baked in at build time from `--site-url`; there is nothing to",
        "    // set up. To report across several sites, duplicate this query",
        "    // and change this ONE line per copy (or point it at a text",
        "    // parameter). Everything below, including the site name,",
        "    // derives from it.",
        f"    SiteUrl = {_m_string(site_url)},",
    ]


# The site root, derived from the SiteUrl binding above rather than trusted
# as given, and the first computed step of every query that consumes it.
# Applied whether the URL was baked in or typed into a parameter: a baked-in
# URL is already correct, but that one line is now the documented place to
# hand-edit for a second site, so it is MORE likely to be retyped, not less.
#
# Emitted verbatim into both the per-list queries and the user-added-column
# audit, so there is one definition of what "the site" means across the pack.
#
# Indented for a top-level `let` binding (four spaces); both consumers bind it
# at that level.
_SITE_ROOT_M: list[str] = [
    "    // The site root, derived from SiteUrl rather than trusted as typed.",
    "    //",
    "    // Measured against a live tenant on 2026-08-11: an operator set",
    "    // SiteUrl to what the browser address bar shows while VIEWING a list",
    "    // (.../sites/<site>/Lists/<ListTitle>), so every endpoint below was",
    "    // built as .../Lists/<ListTitle>/_api/... (_api hung off a list,",
    "    // which is not a web) and SharePoint answered 404",
    "    // DataSource.NotFound, naming neither the parameter at fault nor the",
    "    // correction. The header above already said \"site URL\" and that did",
    "    // not help, which is why this is done in code.",
    "    //",
    "    // Cutting at the first /_api/, /_layouts/, /lists/ or /sitepages/",
    "    // segment turns a list, form, page or API URL back into the site",
    "    // root, and leaves a correct site URL untouched. Deliberately no",
    "    // error is raised: a root site collection is legitimately",
    "    // https://tenant.sharepoint.com, with no /sites/ segment to check",
    "    // for, so anything shaped like a validation would refuse valid input.",
    "    SiteRoot = Text.TrimEnd(",
    "        List.Accumulate(",
    '            {"/_api/", "/_layouts/", "/lists/", "/sitepages/"},',
    '            Text.TrimEnd(SiteUrl, "/"),',
    "            (url, marker) =>",
    "                let",
    "                    at = Text.PositionOf(Text.Lower(url), marker)",
    "                in",
    "                    // Text.PositionOf answers -1 when the marker is",
    "                    // absent, and a marker can never sit at position 0",
    "                    // of an https:// URL, so > 0 covers both.",
    "                    if at > 0 then Text.Start(url, at) else url",
    "        ),",
    '        "/"',
    "    ),",
]


def _render_m(plan: _ListPlan, *, site_url: str | None = None) -> str:
    query_string = "?$select=" + ",".join(plan.selects)
    header = [] if site_url is not None else [
        "// Requires a text parameter named SiteUrl holding the site URL,",
        "// e.g. https://tenant.sharepoint.com/sites/YourSite, the SITE, not",
        "// a list or a page. A list URL is trimmed back to the site for you;",
        "// see the SiteRoot step below.",
        "//",
        "// To report on several sites at once, duplicate this query per site",
        "// and point each copy at its own SiteUrl parameter. Everything",
        "// below, including the site name, derives from whichever URL that",
        "// copy uses. Then append the copies.",
    ]
    lines = [
        (f"// {plan.list_title}: generated by dbml-sharepoint; regenerate "
         "rather than hand-edit."),
        *header,
        "let",
        *_site_url_binding_m(site_url),
        *_SITE_ROOT_M,
        # Deliberately inline rather than a shared _SiteName query. A shared
        # query binds to ONE SiteUrl parameter, so every duplicate of this
        # list -- one per site, which is exactly how a multi-site report is
        # built -- would stamp the FIRST site's name onto its rows. Wrong,
        # and silently so. Inline, the name always matches the URL that
        # fetched the rows beside it.
        #
        # The cost is one extra request per query per refresh instead of one
        # per site. `_api/web?$select=Title` is a single tiny read.
        "    // The site's own display title, read from the site rather than",
        "    // configured, so a renamed site shows its new name next refresh.",
        "    // Falls back to the URL: the name is a slicer label and the rows",
        "    // are the data, so this must not be able to fail the refresh.",
        "    SiteName =",
        "        try",
        "            OData.Feed(",
        '                SiteRoot & "/_api/web?$select=Title",',
        "                null,",
        '                [Implementation = "2.0"]',
        "            )[Title]",
        "        otherwise SiteRoot,",
        "    Source = OData.Feed(",
        f"        SiteRoot & \"/_api/web/lists/getbytitle('{plan.list_title}')/items\"",
        f'            & "{query_string}"',
    ]
    if plan.expands:
        lines.append(f'            & "&$expand={",".join(plan.expands)}"')
    lines[-1] += ","
    lines += [
        "        null,",
        '        [Implementation = "2.0"]',
        "    ),",
    ]
    prev = "Source"
    if plan.record_expands:
        lines += [
            "    // MEASURED on a live tenant, 2026-08-11: a freshly deployed",
            "    // list with ZERO rows answers without the expanded record",
            "    // columns at all, and a bare Table.ExpandRecordColumn then",
            "    // fails the whole query with \"The column '<name>' of the table",
            "    // wasn't found\", which reads as a broken query rather than an",
            "    // empty list. A fresh deploy produces empty lists, so that is",
            "    // the FIRST refresh every adopter runs; adding one row makes it",
            "    // work again, so it is invisible anywhere data already exists.",
            "    //",
            "    // Skipping the step instead is not an option: the typing step",
            "    // and the model-facing rename below both name these output",
            "    // columns. So the column is always produced, expanded when the",
            "    // record is there and nulls of the same type when it is not.",
        ]
    for i, (record_col, inner, out, m_type) in enumerate(
        plan.record_expands, start=1,
    ):
        step = f"Expand{i}"
        lines += [
            f"    {step} =",
            f'        if List.Contains(Table.ColumnNames({prev}), "{record_col}")',
            (f'        then Table.ExpandRecordColumn({prev}, "{record_col}", '
             f'{{"{inner}"}}, {{"{out}"}})'),
            f'        else Table.AddColumn({prev}, "{out}", each null, {m_type}),',
        ]
        prev = step
    # The separator, and why it is that string, live in `analysis/exports.py` --
    # the check that refuses a member containing it needs the same fact, and a
    # generator is the wrong place for `analysis/` to import from.
    if plan.multi_value_joins:
        lines += [
            "    // A multi-value column arrives as a LIST, so it is joined to",
            "    // one text cell here, before the typing step below, which",
            "    // over a list would put an Error value in every populated",
            "    // cell rather than mistyping the column, and the query would",
            "    // still load. An empty set reads back as null, not [], and",
            "    // Text.Combine(null) raises: that would fail the whole",
            "    // refresh over one row that has never had a value.",
            (f'    // Members are separated by "{MULTI_VALUE_JOIN}".'
             " Text.Split to get the list back."),
            "    JoinedMultiValue = Table.TransformColumns(",
            f"        {prev},",
            "        {",
        ]
        for name in plan.multi_value_joins:
            lines += [
                (f'            {{"{name}", each if _ = null '
                 "or List.IsEmpty(_) then null"),
                (f'                else Text.Combine(_, "{MULTI_VALUE_JOIN}"), '
                 "type text},"),
            ]
        # M list literals do not allow a trailing comma.
        lines[-1] = lines[-1].rstrip(",")
        lines += [
            "        }",
            "    ),",
        ]
        prev = "JoinedMultiValue"
    lines.append("    Typed = Table.TransformColumnTypes(")
    lines.append(f"        {prev},")
    lines.append("        {")
    for name, m_type in plan.m_types:
        lines.append(f'            {{"{name}", {m_type}}},')
    # M list literals do not allow a trailing comma.
    lines[-1] = lines[-1].rstrip(",")
    # Whatever SharePoint adds unasked rides through every step above, so the
    # declared set is selected here. `multi_value_joins` is the one output
    # column not in `m_types` (the join step types it), and a selection built
    # from `m_types` alone would drop it silently.
    declared = [name for name, _ in plan.m_types] + plan.multi_value_joins
    lines += [
        "        }",
        "    ),",
        "    // MEASURED on a live tenant, 2026-09-02: /items answers with an",
        "    // uppercase `ID` beside the `Id` the $select asked for, the same",
        "    // value on every row, and nothing above removes it. Power Query",
        "    // keeps both, since its column names are case-sensitive; the Power",
        "    // BI model's are not, and it loads the second as \"ID 2\". Only the",
        "    // declared columns go on from here, whatever else SharePoint adds.",
        "    Declared = Table.SelectColumns(",
        "        Typed,",
        "        {" + ", ".join(f'"{name}"' for name in declared) + "}",
        "    ),",
        '    WithItemURL = Table.AddColumn(',
        '        Declared, "ItemURL",',
        f'        each SiteRoot & "{plan.item_url_path}" & Number.ToText([Id]),',
        "        type text",
        "    ),",
        # Where the row came from. One build covers one site, but a report
        # routinely appends several deployments of the same template, and
        # without these two columns there is nothing to slice by.
        "    WithSiteUrl = Table.AddColumn(",
        f'        WithItemURL, "{REPORT_FIXED_COLUMNS[0]}", each SiteRoot, type text',
        "    ),",
        "    WithSiteName = Table.AddColumn(",
        f'        WithSiteUrl, "{REPORT_FIXED_COLUMNS[1]}", each SiteName, type text',
        "    ),",
        # Which LIST the row came from, the other half of the same problem
        # the two columns above solve. A model that appends several lists
        # needs to slice by list as well as by site, and the key below is
        # opaque.
        "    WithListTitle = Table.AddColumn(",
        f'        WithSiteName, "{REPORT_FIXED_COLUMNS[2]}",',
        f"        each {_m_string(plan.list_title)},",
        "        type text",
        "    ),",
        # THE reason an appended report can be trusted. `Id` is unique only
        # within one list on one site: appending three sites puts three rows
        # with Id = 1 in this table, and appending two LISTS on one site does
        # the same. A relationship on such a key cannot be many-to-one; Power
        # BI degrades it to many-to-many and joins a child row to the
        # same-numbered parent everywhere. The report renders and the numbers
        # are wrong. Format and rationale: `_row_key_m`.
        "    WithRowKey = Table.AddColumn(",
        f'        WithListTitle, "{plan.entity}{REPORT_KEY_SUFFIX}",',
        f"        each {_row_key_m(plan.list_title, '[Id]')},",
        "        type text",
        "    )",
    ]
    prev = "WithRowKey"
    for i, (fk_col, target_title, _display) in enumerate(plan.joins, start=1):
        step = f"WithFkKey{i}"
        lines[-1] += ","
        lines += [
            f"    {step} = Table.AddColumn(",
            f'        {prev}, "{_fk_key_column(fk_col)}",',
            # Null-guarded: an optional lookup leaves the FK null, and
            # Number.ToText(null) RAISES rather than returning null, which
            # would fail the whole refresh on one blank field.
            f"        each if [{fk_col}] = null then null",
            # The TARGET list's title, never this one's: this key is joined
            # against the row key the target table publishes, so it has to be
            # spelled the way the TARGET spells it. Both come from
            # `_row_key_m`, which is the point of that function.
            f"              else {_row_key_m(target_title, f'[{fk_col}]')},",
            "        type text",
            "    )",
        ]
        prev = step
    if plan.renames:
        lines[-1] += ","
        lines += [
            "    // Model-facing names match the SharePoint display titles.",
            "    RenamedForModel = Table.RenameColumns(",
            f"        {prev},",
            "        {",
        ]
        lines += [
            f'            {{"{internal}", "{display}"}},'
            for internal, display in plan.renames
        ]
        lines[-1] = lines[-1].rstrip(",")
        lines += [
            "        },",
            "        MissingField.Ignore",
            "    )",
            "in",
            "    RenamedForModel",
            "",
        ]
    else:
        lines += [
            "in",
            f"    {prev}",
            "",
        ]
    return "\n".join(lines)


def generate_powerquery(
    schema: Schema, bundle: MappingBundle, site_role: str,
    *,
    site_url: str | None = None,
) -> dict[str, str]:
    """One M query per list for the site role: {filename: query text}.

    Each query is self-contained, including its site-name lookup. That is
    what makes a multi-site report possible: duplicate a query, point the
    copy at another site's URL, and the name follows the rows. A shared
    lookup query would bind to one URL and stamp that site's name onto
    every copy.

    ``site_url``, when given, is bound as the first step of each query so
    the pack works with nothing to configure. Omitted (the standalone
    ``report`` command has no site to name), the queries read a ``SiteUrl``
    text parameter instead, and are otherwise identical.
    """
    return {
        f"{plan.list_title}.pq": _render_m(plan, site_url=site_url)
        for plan in _build_plans(schema, bundle, site_role)
    }


# ------------------------------------------------------------------ SQL views


_SQL_SITE_URL_PLACEHOLDER = "https://yourtenant.sharepoint.com/sites/YourSite"


def _sql_header(site_url: str | None) -> str:
    """The SQLCMD preamble, with SiteUrl set to the real site when known.

    Same rule as the M queries: ``build`` was given ``--site-url`` and bakes
    it in, ``report`` was not and leaves the placeholder to be edited. The
    trailing slash is dropped because ItemURL concatenates a path that
    already starts with one. ``$(SiteUrl)`` is a raw prefix here, with no
    normalisation step of the kind the M queries have to absorb it later.
    """
    setvar = (
        _SQL_SITE_URL_PLACEHOLDER if site_url is None else site_url.rstrip("/")
    )
    aim = (
        """\
-- Run in SQLCMD mode; point the variables at your landing/reporting schemas
-- and SiteUrl at the site the lists were deployed to (no trailing slash).
-- It feeds the ItemURL helper column linking each row back to SharePoint."""
        if site_url is None else
        """\
-- Run in SQLCMD mode; point the variables at your landing/reporting schemas.
-- SiteUrl is already set to the site this bundle was built for. It feeds
-- the ItemURL helper column linking each row back to SharePoint."""
    )
    return f"""\
-- Generated by dbml-sharepoint; regenerate rather than hand-edit.
-- T-SQL views over SharePoint list data landed in a warehouse.
{aim}
-- Assumes each list lands as a table named after the list, with columns
-- named after the SharePoint internal column names (see {REPORT_GUIDE}).
:setvar LandingSchema landing
:setvar ReportSchema rpt
:setvar SiteUrl {setvar}
GO
"""


def _render_sql_view(plan: _ListPlan) -> str:
    col_lines = [
        f"    CAST(t.[{name}] AS {sql_type}) AS [{name}]"
        for name, sql_type in plan.sql_columns
    ]
    col_lines.append(
        f"    CONCAT('$(SiteUrl){plan.item_url_path}', CAST(t.[Id] AS INT)) "
        "AS [ItemURL]",
    )
    cols = ",\n".join(col_lines)
    return (
        f"CREATE OR ALTER VIEW [$(ReportSchema)].[vw_{plan.list_title}] AS\n"
        f"SELECT\n{cols}\n"
        f"FROM [$(LandingSchema)].[{plan.list_title}] AS t;\n"
        "GO\n"
    )


def _render_sql_enriched(plan: _ListPlan) -> str:
    select_lines = ["    t.*"]
    join_lines = []
    for i, (fk_col, target_title, display) in enumerate(plan.joins, start=1):
        alias = f"j{i}"
        out_col = fk_col.removesuffix("Id") + display
        select_lines.append(f"    {alias}.[{display}] AS [{out_col}]")
        join_lines.append(
            f"LEFT JOIN [$(ReportSchema)].[vw_{target_title}] AS {alias}\n"
            f"    ON t.[{fk_col}] = {alias}.[Id]",
        )
    return (
        f"CREATE OR ALTER VIEW [$(ReportSchema)].[vw_{plan.list_title}_Enriched] AS\n"
        "SELECT\n" + ",\n".join(select_lines) + "\n"
        f"FROM [$(ReportSchema)].[vw_{plan.list_title}] AS t\n"
        + "\n".join(join_lines) + ";\n"
        "GO\n"
    )


def generate_sql_views(
    schema: Schema, bundle: MappingBundle, site_role: str,
    *,
    site_url: str | None = None,
) -> str:
    """A single SQLCMD script: typed view per list + _Enriched join views.

    ``site_url``, when known, is written into the ``:setvar SiteUrl`` line
    so the script needs no editing; otherwise a placeholder is left there.
    """
    plans = _build_plans(schema, bundle, site_role)
    parts = [_sql_header(site_url)]
    parts += [_render_sql_view(plan) for plan in plans]
    parts += [_render_sql_enriched(plan) for plan in plans if plan.joins]
    return "\n".join(parts)


# ------------------------------------------------------------ reporting guide


def generate_reporting_md(
    schema: Schema, bundle: MappingBundle, site_role: str,
    *,
    site_url: str | None = None,
) -> str:
    """Usage instructions + the Power BI relationship table.

    ``site_url`` must be passed whenever the queries beside this guide were
    built with it: the setup step it documents is the difference between
    "create a parameter" and "there is nothing to create", and a guide that
    is wrong about that costs the operator the whole first hour.
    """
    plans = _build_plans(schema, bundle, site_role)
    setup_step = (
        ("1. **Manage Parameters -> New parameter**: a *Text* parameter named "
         "`SiteUrl` holding the **site** URL, e.g. "
         "`https://tenant.sharepoint.com/sites/YourSite` (no trailing slash). "
         "That is the site, not a list or a page. Note the address bar shows the "
         "*list* URL (`.../Lists/YourList`) while you are looking at a list; "
         "each query trims that back to the site for you, so a pasted list, "
         "form, page or API URL still works.")
        if site_url is None else
        ("1. **Nothing to configure.** Each query already carries the site it "
         f"was built for (`{site_url}`) as its first line. See *Reporting on "
         "several sites at once* below to point a copy somewhere else.")
    )
    combine_steps = (
        [("1. Add one text parameter per site: `SiteUrl_North`, "
          "`SiteUrl_South`, and so on."),
         ("2. Duplicate each list query once per site (*right-click -> "
          "Duplicate*) and change `SiteUrl` in the duplicate to that site's "
          "parameter. Nothing else needs editing: the rows, the item links, "
          "the site name and the keys all follow that one reference.")]
        if site_url is None else
        [("1. Duplicate each list query once per site (*right-click -> "
          "Duplicate*)."),
         ("2. In each duplicate, change the one `SiteUrl = \"...\"` line to "
          "that site's URL, or replace it with a text parameter per site "
          "if you would rather manage them in one place. Nothing else needs "
          "editing: the rows, the item links, the site name and the keys "
          "all follow that one line.")]
    )
    lines = [
        "# Reporting queries",
        "",
        (f"Generated by dbml-sharepoint for site role `{site_role}` "
         f"(list prefix `{bundle.mapping.prefix}`). Regenerate with "
         "`dbml-sharepoint report` after any schema change. These queries "
         "stay in lockstep with the deployed lists only if they are "
         "regenerated together."),
        "",
        "## Power Query (M): Power BI Desktop / Excel",
        "",
        setup_step,
        ("2. For each `.pq` file: **Get Data -> Blank Query -> Advanced "
         "Editor**, paste the file contents, and rename the query to the "
         "list name (the first line of the file)."),
        ("3. When prompted to authenticate, choose **Organizational account** "
         "and sign in with an account that can read the lists."),
        "",
        ("Each query returns a typed table with lookup and person columns "
         "already expanded to a join key (`...Id`) plus a display column."),
        "",
        "## Reporting on several sites at once",
        "",
        ("This template is deployed one site at a time, but a report often "
         "needs all of them together: every region, service or committee "
         "running the same lists, in one model, sliced by site."),
        "",
        ("Every table already carries **`Site Url`**, **`Site Name`** and "
         "**`List Title`** for that, so a model that appends several "
         "deployments can slice by site and by list. The site name is read "
         "from the site's own title at refresh time, so nothing has to be "
         "typed in and a site renamed in SharePoint shows its new name at "
         "the next refresh."),
        "",
        ("Each query works that out for itself, from whichever URL it was "
         "given. That is deliberate: a single shared site-name query would "
         "bind to one `SiteUrl`, and every copy of a list pointed at a "
         "different site would still be stamped with the FIRST site's name."),
        "",
        "To combine deployments:",
        "",
        *combine_steps,
        ("3. **Append** the copies of a list into one table (*Home -> Append "
         "Queries as New*)."),
        ("4. Build the relationships below on the **Key** columns, not on "
         "`Id`."),
        "",
        (">  **`Id` is unique within one list on one site, and nowhere "
         "wider.** Append three sites and three different rows all have "
         "`Id = 1`, and so do the first rows of any two lists on a single "
         "site, because every list numbers its items from 1. A relationship "
         "on `Id` cannot then be many-to-one; Power BI degrades it to "
         "many-to-many and joins each child to the same-numbered parent "
         "everywhere. The report still renders. The numbers are just "
         "wrong. The `... Key` columns are `Site Url`, the **list title** and "
         "the id together, which is unique across any number of sites and "
         "lists, and they are why the relationships below are safe to "
         "append."),
        "",
        "## Relationships (Power BI model)",
        "",
        ("After loading the queries, create these many-to-one, "
         "single-direction relationships:"),
        "",
        "| From table | From column | To table | To column |",
        "|---|---|---|---|",
    ]
    for plan in plans:
        for fk_col, target_title, _display in plan.joins:
            target_entity = next(
                (p.entity for p in plans if p.list_title == target_title),
                target_title,
            )
            lines.append(
                f"| {plan.list_title} | {_fk_key_column(fk_col)} "
                f"| {target_title} | {target_entity} Key |",
            )
    lines += [
        "",
        ("Person columns carry the site-user id (`...Id`) and display name "
         "(`...Title`) but no relationship target. The site user list is not "
         "part of this schema."),
        "",
        "## SQL views: warehouse landing zone",
        "",
        ("`sql/views.sql` assumes each list has been landed (by any extract "
         "process: Azure Data Factory, Power Automate, Dataflows) as a "
         "table named after the list, columns named after the SharePoint "
         "internal names, in the `$(LandingSchema)` schema. Lookup columns "
         "land as `...Id` integers; person columns land as display-name text. "
         "Run the script in SQLCMD mode after adjusting `:setvar "
         "LandingSchema` / `:setvar ReportSchema`."),
        "",
        ("**Multi-value choice columns are a landing contract, not a "
         "transform.** The Power Query queries join a set into one text cell "
         f'separated by `\"{MULTI_VALUE_JOIN}\"`, in a step written into the '
         "`.pq` file. The SQL views do not: they `CAST` whatever the extract "
         "landed, as `NVARCHAR(MAX)` so nothing is truncated in silence. "
         "Your extract must therefore land such a column as text, and the "
         "text it lands is the text your reports will read: SharePoint's "
         "own `;#`-delimited string, a JSON array, or the same "
         f'`\"{MULTI_VALUE_JOIN}\"` join, depending on the extractor. Match '
         "it to the Power Query separator if the two layers are to agree, or "
         "record which one your warehouse uses; this generator cannot see "
         "the extract and does not guess."),
        "",
        ("Per list you get `vw_<List>` (typed casts) and, where the list has "
         "lookups, `vw_<List>_Enriched` (lookups joined to their display "
         "columns), the horizontal, cross-list reporting layer."),
    ]
    lines += [
        "",
        ("Both layers add an **ItemURL** helper column (the SharePoint "
         "display-form link for the row, built from the site URL, the list "
         "path and the item id), so any report visual can link straight "
         "back to the source item. `data-dictionary.md` documents every "
         "list and column plus the deployment metadata behind this "
         "generation."),
        "",
        "## Data dictionary page (in-report)",
        "",
        ("The dictionary also ships as loadable data so every report can "
         "carry its own documentation page: load `_DataDictionary.pq` and "
         "`_ModelInfo.pq` alongside the list queries (they are static "
         "`#table` literals with no connection and no refresh cost), add a report "
         "page with a table visual over `_DataDictionary` sorted by "
         "`SortOrder`, and a card or table over `_ModelInfo` for the "
         "release/schema provenance. SQL consumers get the same rows as "
         f"`vw_{bundle.mapping.prefix}DataDictionary` and "
         f"`vw_{bundle.mapping.prefix}ModelInfo` (built from embedded "
         "VALUES, with no landing table needed)."),
    ]
    lines += [
        "",
        "## User-added column audit",
        "",
        ("Load `_UserAddedColumns.pq` alongside the dictionary queries. It "
         "reads each list's fields collection live on every refresh and "
         "returns the visible, deletable columns the schema does not "
         "declare. Expected EMPTY. Any row is a column added outside this "
         "generation: investigate it before trusting the model. "
         "Extension-expanded cross-site columns (if any) can appear; "
         "recognise them once. SQL consumers get "
         f"`vw_{bundle.mapping.prefix}UserAddedColumns` over "
         "INFORMATION_SCHEMA, which sees only columns the extract process "
         "lands, and extractor-added audit columns (e.g. `LoadDate`) "
         "appear there as recognisable rows."),
    ]
    skipped = [
        (plan.list_title, name) for plan in plans for name in plan.skipped
    ]
    if skipped:
        lines += [
            "",
            "## Columns not included",
            "",
            ("Cross-site reference columns are expanded at deploy time by the "
             "active extension into shapes this generator cannot know; add "
             "them to the queries by hand if needed:"),
            "",
        ]
        lines += [f"- {title}: `{name}`" for title, name in skipped]
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------- Data dictionary


def _md_cell(text: str) -> str:
    """Make free text safe inside a markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ")


def _sp_type_cell(
    sp: SPField,
    enum_members: dict[str, list[str]],
    formula: str | None,
    prefix: str,
) -> str:
    """Human-readable SharePoint type description for one column.

    Plain text. Each renderer (markdown / M / SQL) applies its own
    escaping so the same rows can feed the document and the report-loadable
    dictionary tables.
    """
    match sp.kind:
        case "Skip":
            return "Counter (item ID)"
        case "Text":
            return f"Text ({sp.max_length})"
        case "Note":
            if sp.rich_text:
                return (
                    "Multi-line text (rich; HTML over OData, so strip markup "
                    "for reporting)"
                )
            return "Multi-line text (plain)"
        case "Choice":
            # Declaration-order ordinals: Power BI sorts choice text
            # alphabetically; these feed sort-by-column mappings.
            members = enum_members.get(sp.choices_enum or "", [])
            return "Choice: " + ", ".join(
                f"{i}. {member}" for i, member in enumerate(members, 1)
            )
        case "MultiChoice":
            # `MultiChoice` is this codebase's token for FieldTypeKind 15, and
            # the raw token is what a fall-through printed here, into the one
            # column a report author reads to find out what a column IS.
            #
            # Same declaration-order ordinals as Choice, and then how the
            # export spells a set, because this page is where somebody looking
            # at one text cell holding several members finds out that it is
            # several members and what to split on.
            members = enum_members.get(sp.choices_enum or "", [])
            # The dictionary is the one entry point that never builds a plan,
            # so the plan builder's guard does not cover it. It is also the
            # page that tells a reader to split on the separator.
            _refuse_ambiguous_members(sp.name, members)
            joined = ", ".join(
                f"{i}. {member}" for i, member in enumerate(members, 1)
            )
            # Says WHICH export joins them. The Power Query one does, in a
            # step this generator writes. The SQL views do not: they cast
            # whatever the extract process landed, and this module never sees
            # that process. Telling a warehouse reader the members "are"
            # joined by "; " would state as fact something no part of the SQL
            # path performs -- guide.md carries the landing contract.
            return (
                f"Choice (multiple): {joined} (a set of members; the Power "
                f"Query export joins them into one text cell separated by "
                f'"{MULTI_VALUE_JOIN}")'
            )
        case "Number":
            return "Number"
        case "DateTime":
            return "Date" if sp.date_only else "Date and time"
        case "Boolean":
            return "Yes/No"
        case "URL":
            return "Hyperlink"
        case "User":
            return "Person"
        case "Lookup":
            return f"Lookup -> {prefix}{sp.target_list}"
        case "Calculated":
            output = {9: "Number", 4: "Date"}.get(sp.output_type or 0, "Text")
            if formula:
                return f"Calculated {output}: {formula}"
            return f"Calculated {output}"
    # `generate_data_dictionary` is the ONE entry point in this module that
    # never goes through `_build_plans`, so the `case _` that guards the
    # queries does not cover this page. Ending `return sp.kind` published the
    # internal token instead: a reader of data-dictionary.md would be told a
    # column's SharePoint type is "MultiChoice", which is this codebase's word
    # and not one that appears anywhere in a SharePoint UI, in the one place
    # they went to look it up -- and nothing in the build could see it.
    #
    # The loadable tables are covered incidentally, because both their entry
    # points also build `_UserAddedColumns` and so hit `_build_plans` first.
    # That is not a guard, it is a coincidence of ordering, and this is.
    raise ValueError(
        f"{sp.name}: the data dictionary has no description for SharePoint "
        f"field kind {sp.kind!r}. Add an arm to _sp_type_cell saying what a "
        f"report author should understand the column to be, rather than "
        f"printing an internal token into data-dictionary.md and the "
        f"dictionary tables loaded beside it.",
    )


def _form_behaviour_cells(
    table_name: str, column: str, bundle: MappingBundle,
) -> tuple[str, str]:
    """(populated when, save rule) for one column, in prose.

    Described through `describe()`, never in a target's syntax. This is the
    artefact a report author reads, and `[$ID] != ''` tells them nothing.
    It is a SharePoint list-formatting expression they would first have to
    identify as one. The declaration is theirs to understand; the mechanism
    carrying it is not.
    """
    populated = "-"
    section = bundle.mapping.form_visibility.get(table_name)
    declared = section.columns.get(column) if section else None
    if declared is not None:
        when = describe(declared.when) if declared.when is not None else ""
        if not declared.new and not declared.existing:
            populated = "Never on a form"
        elif not declared.new:
            populated = "Only after creation" + (f", and when {when}" if when else "")
        elif not declared.existing:
            populated = "Only at creation" + (f", and when {when}" if when else "")
        elif when:
            populated = f"When {when}"
        else:
            populated = "Always"

    rule = "-"
    cv_section = bundle.mapping.column_validation.get(table_name)
    cv = cv_section.columns.get(column) if cv_section else None
    if cv is not None:
        rule = f"{describe(cv.when)}: {cv.message}"
    return populated, rule


def _column_rows_for_table(
    table: Table,
    bundle: MappingBundle,
    enum_names: set[str],
    enum_members: dict[str, list[str]],
    cross_site_keys: set[tuple[str, str]],
) -> list[tuple[str, str, str, str, str, str, str, str, str, str]]:
    """Plain-text dictionary rows for one table: (column, type, required,
    unique, default, retired, superseded by, populated when, save rule,
    description).

    Retired columns are still listed, and the generated list queries still
    select them: history is the entire point of retiring rather than
    deleting.
    """
    formulas = bundle.mapping.calculated_formulas.get(table.name, {})
    retired = bundle.mapping.retired_columns.get(table.name, {})
    rows: list[tuple[str, str, str, str, str, str, str, str, str, str]] = []
    for col in table.columns:
        populated, rule = _form_behaviour_cells(table.name, col.name, bundle)
        spec = retired.get(col.name)
        # The bare-list declaration form carries no date; "yes" still says
        # the column is retired.
        retired_cell = (spec.retired or "yes") if spec is not None else "-"
        superseded_cell = (spec.superseded_by or "-") if spec is not None else "-"
        if (table.name, col.name) in cross_site_keys:
            rows.append((
                col.name,
                "Cross-site reference (extension-expanded at deploy time)",
                "-", "-", "-",
                retired_cell, superseded_cell, populated, rule,
                col.note or "-",
            ))
            continue
        sp = map_column(col, enum_names)
        name = "Id" if sp.kind == "Skip" else sp.name
        rows.append((
            name,
            _sp_type_cell(sp, enum_members, formulas.get(col.name), bundle.mapping.prefix),
            "yes" if sp.required else "-",
            "yes" if sp.unique else "-",
            str(sp.default) if sp.default is not None else "-",
            retired_cell,
            superseded_cell,
            populated,
            rule,
            sp.description or (
                "SharePoint item identifier." if sp.kind == "Skip" else "-"
            ),
        ))
    for column, targets in bundle.mapping.lookup_projections.get(table.name, {}).items():
        for target in targets:
            rows.append((
                f"{column}{target}",
                "Lookup (read-only dependent)",
                "-", "-", "-", "-", "-", "Always", "-",
                f"Read-only dependent of {column}, showing the target's {target}.",
            ))
    return rows


def _metadata_rows(
    bundle: MappingBundle,
    site_role: str,
    list_count: int,
    release: Release | None,
    generated_at: str,
    source_schema: str,
    source_mapping: str,
) -> list[tuple[str, str]]:
    """Deployment/schema model metadata as plain (field, value) rows,
    shared by the data-dictionary.md header and the _ModelInfo report table."""
    mapping = bundle.mapping
    rows = [
        ("Generated at", generated_at or "-"),
        ("Generator", f"dbml-sharepoint {__version__}"),
        ("Source schema", source_schema or "-"),
        ("Source mapping", source_mapping or "-"),
        (
            "List prefix",
            mapping.prefix
            + (f" (owner: {mapping.prefix_owner})" if mapping.prefix_owner else ""),
        ),
        ("Site role", site_role),
        ("Lists", str(list_count)),
    ]
    if release is not None:
        rows += [
            ("Release", f"{release.release_tag} ({release.date})"),
            ("Schema version", release.schema_version),
            ("Deployer version pin", release.deployer_version),
        ]
    else:
        rows.append((
            "Release",
            "- (regenerate with `--release` to stamp release metadata)",
        ))
    return rows


def generate_data_dictionary(
    schema: Schema,
    bundle: MappingBundle,
    site_role: str,
    *,
    release: Release | None = None,
    generated_at: str = "",
    source_schema: str = "",
    source_mapping: str = "",
) -> str:
    """Companion data dictionary: deployment/schema metadata + every list and
    column as deployed, including choices, lookup targets, calculated
    formulas, indexing, versioning and the query-layer helper columns."""
    tables = _tables_for_role(schema, bundle, site_role)
    enum_names = {e.name for e in schema.enums}
    enum_members = {e.name: e.members for e in schema.enums}
    cross_site_keys = bundle.mapping.cross_site_keys()
    mapping = bundle.mapping
    prefix = mapping.prefix
    # cross_site_keys above is exactly the pair set lookup_display_columns
    # needs, so the report excludes a cross-site ref's target for the same
    # reason the validator and the deployer do: it renders as a Choice + URL
    # pair, and no picker exists on the far side to protect.
    calculated_by_entity = {
        table.name: {c.name for c in table.columns if c.type in CALCULATED_TYPES}
        for table in schema.tables
    }
    display_columns = lookup_display_columns(
        schema, mapping.entities, calculated_by_entity, cross_site_keys,
    )

    lines = [
        f"# Data dictionary: `{prefix}` (site role `{site_role}`)",
        "",
        "## Deployment / schema model metadata",
        "",
        "| Field | Value |",
        "|---|---|",
    ]
    lines += [
        f"| {field_name} | {_md_cell(value)} |"
        for field_name, value in _metadata_rows(
            bundle, site_role, len(tables),
            release, generated_at, source_schema, source_mapping,
        )
    ]

    for table in tables:
        entity = mapping.entities[table.name]
        list_title = prefix + table.name
        heading = (
            f"## {list_title}: entity `{table.name}` "
            f"({entity.kind}, template {entity.base_template}"
            + (", singleton" if entity.singleton else "")
            + ")"
        )
        lines += ["", heading, ""]
        if table.note:
            lines += [_md_cell(table.note), ""]
        lines += [
            ("| Column | SharePoint type | Required | Unique | Default | "
             "Retired | Superseded by | Populated when | Save rule | Description |"),
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for (
            name, type_cell, required, unique, default,
            retired, superseded_by, populated, rule, description,
        ) in _column_rows_for_table(
            table, bundle, enum_names, enum_members, cross_site_keys,
        ):
            lines.append(
                f"| {name} | {_md_cell(type_cell)} | {required} | {unique} | "
                f"{_md_cell(default)} | {retired} | {superseded_by} | "
                f"{_md_cell(populated)} | {_md_cell(rule)} | "
                f"{_md_cell(description)} |",
            )
        details: list[str] = []
        # The declared indexes PLUS the one a lookup target gets for free. A
        # list that anything looks up is indexed on its display column so the
        # picker keeps working past 5,000 items, and that index spends one of
        # the twenty, so a dictionary listing only the declared ones
        # understates a budget an author is reading this page to manage.
        # Derived from the same lookup_display_columns the deployer emits from,
        # so the report cannot disagree with what is deployed.
        indexed = list(deployable_index_columns(table))
        display = display_columns.get(table.name)
        if display is not None and display not in indexed:
            indexed.append(f"{display} (lookup display column)")
        if indexed:
            details.append(f"Indexed columns: {', '.join(indexed)}.")
        # `versioning_for` rather than the merge again: this page tells a
        # reader what the list was provisioned with, so it has to be the same
        # answer jsgen sent.
        versioning = mapping.versioning_for(table.name)
        if versioning.enable_versioning:
            details.append(
                "Versioning: major versions on, limit "
                f"{versioning.major_version_limit}"
                + (", minor versions on" if versioning.enable_minor_versions else "")
                + ".",
            )
        else:
            details.append("Versioning: off.")
        lines += ["", " ".join(details)]

    lines += [
        "",
        "## Helper columns (query layer only)",
        "",
        ("Added by every generated Power Query and SQL view; they are "
         "constructed at query time and do not exist on the lists:"),
        "",
        "| Column | Construction | Purpose |",
        "|---|---|---|",
        ("| ItemURL | SiteUrl + list form path + item id | Direct link from "
         "any report row back to the SharePoint item (display form) |"),
        ("| ...Id / ...Title (lookups, person) | `$select`/`$expand` of the "
         "lookup | Join key plus display column without a second query |"),
        "",
    ]
    return "\n".join(lines)


# ----------------------------------------- Dictionary as report-loadable data


def _dictionary_rows(
    schema: Schema, bundle: MappingBundle, site_role: str,
) -> list[tuple[str, str, str, str, str, str, str, str, str, str, str]]:
    """(list, column, type, required, unique, default, retired, superseded
    by, populated when, save rule, description) for every column in the site
    role, in schema order."""
    enum_names = {e.name for e in schema.enums}
    enum_members = {e.name: e.members for e in schema.enums}
    cross_site_keys = bundle.mapping.cross_site_keys()
    prefix = bundle.mapping.prefix
    rows: list[tuple[str, str, str, str, str, str, str, str, str, str, str]] = []
    for table in _tables_for_role(schema, bundle, site_role):
        for row in _column_rows_for_table(
            table, bundle, enum_names, enum_members, cross_site_keys,
        ):
            rows.append((prefix + table.name, *row))
    return rows


def _render_m_table(
    query_name: str, purpose: str, type_spec: str, row_literals: list[str],
) -> str:
    lines = [
        (f"// {query_name}: generated by dbml-sharepoint; regenerate rather "
         "than hand-edit."),
        f"// {purpose}",
        "let",
        "    Source = #table(",
        f"        type table [{type_spec}],",
        "        {",
    ]
    lines += [f"            {row}," for row in row_literals]
    lines[-1] = lines[-1].rstrip(",")
    lines += [
        "        }",
        "    )",
        "in",
        "    Source",
        "",
    ]
    return "\n".join(lines)


def _render_user_added_columns_m(
    plans: list[_ListPlan], *, site_url: str | None = None,
) -> str:
    """The live drift-audit query: every visible, deletable field on the
    deployed lists that the schema does not declare. Expected EMPTY.

    Filtering happens IN M (Table.SelectRows), never OData $filter, so
    REST property filterability quirks cannot break the query. Per the
    documented CanBeDeleted contract, sealed fields and base-type
    built-ins return CanBeDeleted=false, so system columns drop out even
    before the declared-name anti-join.
    """
    if not plans:
        return "\n".join([
            ("// _UserAddedColumns: generated by dbml-sharepoint; "
             "regenerate rather than hand-edit."),
            "// No lists in this site role.",
            "let",
            "    Source = #table(",
            ("        type table [List = text, InternalName = text, "
             "DisplayName = text, Type = text, PopulatedWhenFormula = text, "
             "SaveRuleFormula = text],"),
            "        {}",
            "    )",
            "in",
            "    Source",
            "",
        ])
    audit_calls = []
    for plan in plans:
        expected = ", ".join(
            _m_string(name)
            for name in dict.fromkeys(plan.field_internal_names + plan.skipped)
        )
        audit_calls.append(
            f"        Audit({_m_string(plan.list_title)}, {{{expected}}}),",
        )
    audit_calls[-1] = audit_calls[-1].rstrip(",")
    lines = [
        ("// _UserAddedColumns: generated by dbml-sharepoint; regenerate "
         "rather than hand-edit."),
        "// Live drift audit: every visible, deletable column on the deployed",
        "// lists that the schema does not declare. Expected EMPTY, so any row",
        "// is a column added outside this generation; investigate it.",
        *([
            "// Requires the same SiteUrl text parameter as the list queries,",
            "// normalised here the same way; see the SiteRoot step.",
        ] if site_url is None else [
            "// Carries the same baked-in site URL as the list queries,",
            "// normalised here the same way; see the SiteRoot step.",
        ]),
        "let",
        *_site_url_binding_m(site_url),
        *_SITE_ROOT_M,
        "    // Added by a tenant compliance feature outside operator",
        "    // control; a standing row here would erode the",
        "    // \"any row = investigate\" meaning of this table.",
        '    KnownTenantFields = {"ComplianceAssetId"},',
        "    Audit = (listTitle as text, expected as list) as table =>",
        "        let",
        "            Fields = OData.Feed(",
        "                SiteRoot & \"/_api/web/lists/getbytitle('\" & listTitle & \"')/fields\"",
        # The two formula properties ride along on a call this query already
        # makes on every refresh, turning the drift audit into a refresh-time
        # check that the DEPLOYED form contract still matches the dictionary
        # beside it. The declarations are otherwise visible only at build time.
        ("                    & \"?$select=InternalName,Title,TypeAsString,"
         "Hidden,ReadOnlyField,CanBeDeleted,ClientValidationFormula,"
         "ValidationFormula\","),
        "                null,",
        '                [Implementation = "2.0"]',
        "            ),",
        "            UserAdded = Table.SelectRows(",
        "                Fields,",
        "                each not [Hidden] and not [ReadOnlyField] and [CanBeDeleted]",
        "                    and not List.Contains(expected, [InternalName])",
        "                    and not List.Contains(KnownTenantFields, [InternalName])",
        "            ),",
        "            Named = Table.RenameColumns(",
        ("                Table.SelectColumns(UserAdded, "
         '{"InternalName", "Title", "TypeAsString", '
         '"ClientValidationFormula", "ValidationFormula"}),'),
        ('                {{"Title", "DisplayName"}, {"TypeAsString", "Type"}, '
         '{"ClientValidationFormula", "PopulatedWhenFormula"}, '
         '{"ValidationFormula", "SaveRuleFormula"}}'),
        "            ),",
        '            Tagged = Table.AddColumn(Named, "List", each listTitle, type text)',
        "        in",
        "            Tagged,",
        "    Combined = Table.Combine({",
        *audit_calls,
        "    }),",
        ('    Sorted = Table.Sort(Combined, {{"List", Order.Ascending}, '
         '{"InternalName", Order.Ascending}}),'),
        ('    Final = Table.ReorderColumns(Sorted, {"List", "InternalName", '
         '"DisplayName", "Type", "PopulatedWhenFormula", "SaveRuleFormula"})'),
        "in",
        "    Final",
        "",
    ]
    return "\n".join(lines)


def generate_dictionary_powerquery(
    schema: Schema,
    bundle: MappingBundle,
    site_role: str,
    *,
    release: Release | None = None,
    generated_at: str = "",
    source_schema: str = "",
    source_mapping: str = "",
    site_url: str | None = None,
) -> dict[str, str]:
    """The data dictionary as report-loadable M queries, so any report can
    surface it as a page: _DataDictionary (one row per column), _ModelInfo
    (deployment/schema metadata as field/value rows) and _UserAddedColumns
    (live drift audit, undeclared columns on the deployed lists).

    ``site_url`` reaches only _UserAddedColumns, the one query here that
    talks to the site; it takes the same binding as the list queries, so a
    bundle needs the ``SiteUrl`` parameter everywhere or nowhere.
    """
    dd_rows = [
        "{" + ", ".join([str(i)] + [_m_string(cell) for cell in row]) + "}"
        for i, row in enumerate(_dictionary_rows(schema, bundle, site_role), start=1)
    ]
    tables = _tables_for_role(schema, bundle, site_role)
    mi_rows = [
        "{" + _m_string(field_name) + ", " + _m_string(value) + "}"
        for field_name, value in _metadata_rows(
            bundle, site_role, len(tables),
            release, generated_at, source_schema, source_mapping,
        )
    ]
    return {
        "_DataDictionary.pq": _render_m_table(
            "_DataDictionary",
            "Load and add a report page with a table visual over this query "
            "(sorted by SortOrder) to surface the data dictionary in the report.",
            "SortOrder = Int64.Type, List = text, Column = text, Type = text, "
            "Required = text, Unique = text, Default = text, "
            "Retired = text, SupersededBy = text, "
            "PopulatedWhen = text, SaveRule = text, Description = text",
            dd_rows,
        ),
        "_ModelInfo.pq": _render_m_table(
            "_ModelInfo",
            "Deployment/schema model metadata for the report's data-dictionary "
            "page (release, schema version, sources, generation time).",
            "Field = text, Value = text",
            mi_rows,
        ),
        "_UserAddedColumns.pq": _render_user_added_columns_m(
            _build_plans(schema, bundle, site_role), site_url=site_url,
        ),
    }


def _sql_string(text: str) -> str:
    """An N'...' T-SQL literal: single quotes are escaped by doubling."""
    return "N'" + text.replace("'", "''") + "'"


def _render_sql_values_view(
    view_name: str, columns: list[str], row_literals: list[str],
) -> str:
    col_list = ", ".join(f"[{c}]" for c in columns)
    return (
        f"CREATE OR ALTER VIEW [$(ReportSchema)].[{view_name}] AS\n"
        f"SELECT {col_list}\n"
        "FROM (VALUES\n"
        + ",\n".join(f"    ({row})" for row in row_literals)
        + f"\n) AS v({col_list});\n"
        "GO\n"
    )


def _render_user_added_columns_sql(plans: list[_ListPlan], prefix: str) -> str:
    """Drift-audit view over the landing schema: columns present on the
    landed tables that the schema does not declare. Sees only what the
    extract process lands (the M audit query is the live control);
    extractor-added audit columns (e.g. LoadDate) surface as recognisable
    rows."""
    if not plans:
        return ""
    table_list = ", ".join(_sql_string(plan.list_title) for plan in plans)
    expected_rows = []
    for plan in plans:
        names = ["Id"] + [name for name, _ in plan.sql_columns]
        for name in dict.fromkeys(names):
            expected_rows.append(
                f"    ({_sql_string(plan.list_title)}, {_sql_string(name)})",
            )
    # Emitting SQL text is this generator's purpose; identifiers come
    # from the validated schema, never from runtime user input.
    return (
        f"CREATE OR ALTER VIEW [$(ReportSchema)].[vw_{prefix}UserAddedColumns] AS\n"  # noqa: S608
        "-- Drift audit: landed columns the schema does not declare. Expected\n"
        "-- EMPTY. Only sees columns the extract process lands.\n"
        "SELECT c.TABLE_NAME AS [List], c.COLUMN_NAME AS [Column],\n"
        "       c.DATA_TYPE AS [LandedType]\n"
        "FROM INFORMATION_SCHEMA.COLUMNS AS c\n"
        "WHERE c.TABLE_SCHEMA = '$(LandingSchema)'\n"
        f"  AND c.TABLE_NAME IN ({table_list})\n"
        "  AND NOT EXISTS (SELECT 1 FROM (VALUES\n"
        + ",\n".join(expected_rows)
        + "\n  ) AS d([List], [Column])\n"
        "  WHERE d.[List] = c.TABLE_NAME AND d.[Column] = c.COLUMN_NAME);\n"
        "GO\n"
    )


def generate_dictionary_sql(
    schema: Schema,
    bundle: MappingBundle,
    site_role: str,
    *,
    release: Release | None = None,
    generated_at: str = "",
    source_schema: str = "",
    source_mapping: str = "",
) -> str:
    """The data dictionary as SQL views built from embedded VALUES rows (no
    landing table needed), so warehouse-driven reports can surface the same
    dictionary page."""
    prefix = bundle.mapping.prefix
    dd_rows = [
        ", ".join([str(i)] + [_sql_string(cell) for cell in row])
        for i, row in enumerate(_dictionary_rows(schema, bundle, site_role), start=1)
    ]
    tables = _tables_for_role(schema, bundle, site_role)
    mi_rows = [
        _sql_string(field_name) + ", " + _sql_string(value)
        for field_name, value in _metadata_rows(
            bundle, site_role, len(tables),
            release, generated_at, source_schema, source_mapping,
        )
    ]
    audit_view = _render_user_added_columns_sql(
        _build_plans(schema, bundle, site_role), prefix,
    )
    return (
        _render_sql_values_view(
            f"vw_{prefix}DataDictionary",
            ["SortOrder", "List", "Column", "Type",
             "Required", "Unique", "Default", "Retired", "SupersededBy",
             "PopulatedWhen", "SaveRule", "Description"],
            dd_rows,
        )
        + "\n"
        + _render_sql_values_view(
            f"vw_{prefix}ModelInfo", ["Field", "Value"], mi_rows,
        )
        + ("\n" + audit_view if audit_view else "")
    )


def emit_reporting(
    out: Path,
    schema: Schema,
    bundle: MappingBundle,
    site_role: str,
    *,
    release: Release | None,
    generated_at: str,
    source_schema: str,
    source_mapping: str,
    site_url: str | None = None,
) -> list[str]:
    """Write the reporting bundle under ``out/reporting/`` and return the
    POSIX relpaths written (for checksums.txt).

    Shared by the core and extension CLIs so the shipped reporting
    artifact set cannot drift between them: per-list Power Query (M)
    plus the dictionary/model/audit queries, the SQL views script,
    the reporting guide and the data dictionary.

    ``site_url`` is the deployment target, which ``build`` always has.
    Passing it bakes the site into every query, the SQL script and the
    guide, so the pack loads with nothing configured. It is optional only
    because ``report`` runs without a site at all.
    """
    reporting_dir = out / REPORT_DIR
    pq_dir = reporting_dir / "powerquery"
    sql_dir = reporting_dir / "sql"
    pq_dir.mkdir(parents=True, exist_ok=True)
    sql_dir.mkdir(parents=True, exist_ok=True)
    dictionary_kwargs: dict[str, Any] = dict(
        release=release,
        generated_at=generated_at,
        source_schema=source_schema,
        source_mapping=source_mapping,
    )
    relpaths: list[str] = []
    queries = generate_powerquery(schema, bundle, site_role, site_url=site_url)
    queries.update(
        generate_dictionary_powerquery(
            schema, bundle, site_role, site_url=site_url, **dictionary_kwargs,
        ),
    )
    for filename, content in queries.items():
        write_artifact(pq_dir / filename, content)
        relpaths.append(f"reporting/powerquery/{filename}")
    write_artifact(
        sql_dir / REPORT_VIEWS_SQL,
        generate_sql_views(schema, bundle, site_role, site_url=site_url)
        + "\n"
        + generate_dictionary_sql(schema, bundle, site_role, **dictionary_kwargs),
    )
    write_artifact(
        reporting_dir / REPORT_GUIDE,
        generate_reporting_md(schema, bundle, site_role, site_url=site_url),
    )
    write_artifact(
        reporting_dir / REPORT_DICTIONARY,
        generate_data_dictionary(schema, bundle, site_role, **dictionary_kwargs),
    )
    relpaths += [
        f"{REPORT_DIR}/sql/{REPORT_VIEWS_SQL}",
        f"{REPORT_DIR}/{REPORT_GUIDE}",
        f"{REPORT_DIR}/{REPORT_DICTIONARY}",
    ]
    return relpaths
