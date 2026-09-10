# src/dbml_sharepoint/analysis/reporting/plan.py
"""The reporting plan: what each list's queries carry, as data.

Everything here is a pure derivation of ``(schema, bundle, site_role)``
that returns data. Text written to a file, or a fragment of one such as a
line of M, a SQL statement or a markdown row, belongs to a renderer under
``generators/``, and those are split by the escaping function the text
needs. That rule decides where a function lives. A type token such as
``"type text"`` or ``"NVARCHAR(255)"`` is data and sits on a plan; a line of
a query is not.

The plan lives under ``analysis/`` so a validator check can read the same
derivation the renderers do rather than keep its own copy in step with
them. ``AGENTS.md`` names ``analysis/joins.py`` as the worked example of a
fact both sides need, and a generator must never import from
``analysis/checks/``.
"""

from dataclasses import dataclass, field

from dbml_sharepoint.analysis.column_projection import SYSTEM_COLUMN_TYPES
from dbml_sharepoint.analysis.derived import (
    DERIVED_REFERENCE,
    DERIVED_TYPES,
    derived_output_names,
    is_users_source,
    lookup_key_columns,
)
from dbml_sharepoint.analysis.exports import MULTI_VALUE_JOIN, ambiguous_members
from dbml_sharepoint.analysis.lookups import display_column_for
from dbml_sharepoint.analysis.ordering import is_deployed_here
from dbml_sharepoint.analysis.report_columns import (
    DATE_ZONE_RESOLVED_COLUMN,
    ITEM_URL_COLUMN,
    ITEM_URL_RESOLVED_COLUMN,
    REPORT_SYSTEM_COLUMNS,
    SYSTEM_DISPLAY_TITLES,
    USERS_DISPLAY_TITLES,
    USERS_KEY_LIST,
    projection_output_name,
    report_output_names,
)
from dbml_sharepoint.analysis.timezones import ZoneTable, zone_table
from dbml_sharepoint.analysis.typemap import is_person, map_column
from dbml_sharepoint.model.mapping_types import DerivedColumn, MappingBundle
from dbml_sharepoint.model.parser import Schema, Table


@dataclass
class DerivedStep:
    """One derived column, with every name already resolved.

    Built in a POST-PASS over the plans, because a join has to translate the
    columns it reads through the TARGET query's own rename map, and that map
    only exists once the target's plan does. Reading the map rather than
    re-deriving the display title is the point: it is the rename the target
    query actually performs, so the two cannot disagree.
    """

    kind: str
    name: str = ""
    m_type: str = ""
    m: str = ""
    replace: bool = False
    hidden: bool = False
    description: str = ""
    # The other query this step reads, by the name its file carries.
    source_query: str = ""
    source_entity: str = ""
    own_key: str = ""
    other_key: str = ""
    # (column on the target, column produced here, M type token)
    picks: tuple[tuple[str, str, str], ...] = ()
    aggregate: str = ""
    # Already translated to the names the source query ends with.
    column: str = ""
    where: str = ""


@dataclass
class ListPlan:
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
    # Multi-value columns joined to one text cell, each with whether its
    # members arrive as text. Deliberately NOT in `m_types`: the join step
    # ascribes their type, because the raw list must never reach
    # `Table.TransformColumnTypes` at all. A multi-value LOOKUP arrives as a
    # list of ids rather than of strings, and `Text.Combine` over numbers
    # raises, so the flag decides whether the members are converted first.
    multi_value_joins: list[tuple[str, bool]] = field(default_factory=list)
    # The report columns the DECLARED fields contribute, in column order,
    # from `report_columns.report_output_names`. `m_types` and
    # `multi_value_joins` above hold the same names split by how the query
    # types them; this is the one list the rename step reads, and it is the
    # one `checks/_naming` reads too, so a rule about the report's names
    # cannot compare a different set from the one the query produces.
    output_columns: list[str] = field(default_factory=list)
    # (landed column, SQL type)
    sql_columns: list[tuple[str, str]] = field(default_factory=list)
    # (fk column, target list title, target display column, projected target
    # columns). The projections ride the JOIN rather than the base view
    # because the SQL side reads a landed table and cannot know whether the
    # extract carried a dependent lookup across; the target's own view always
    # has the column, and the join is already there for the display column.
    joins: list[tuple[str, str, str, tuple[str, ...]]] = field(
        default_factory=list,
    )
    skipped: list[str] = field(default_factory=list)
    # Site-relative path of the item display form, ending in "?ID=", built
    # from the DECLARED title. The fallback when the list's own folder cannot
    # be read, and what the SQL views use, having no site to read.
    item_url_path: str = ""
    # What follows the list's own RootFolder to reach the same form. The
    # refresh-time branch: see `_item_url_suffix`.
    item_url_suffix: str = ""
    # (internal/out column, model-facing display name), populated only when
    # the mapping declares display_names; the rename is the LAST query step
    # so internal names remain the wire/OData contract.
    renames: list[tuple[str, str]] = field(default_factory=list)
    # Declared internal field names (no cross-site, no Id), the expected
    # set for the user-added-column audit; cross-site names ride
    # ``skipped``.
    field_internal_names: list[str] = field(default_factory=list)
    # Person columns in select order, system ones included when they are
    # on. Each carries a `... Key` into the users dimension when
    # `users_table` is on; the flag is carried here so the renderer needs
    # no mapping.
    person_columns: list[str] = field(default_factory=list)
    users_table: bool = False
    # The declared site zone's transitions (`reporting.time_zone`), or None.
    # Carried on the plan so the renderer and the column list cannot answer
    # "does this query carry the zone table" differently.
    zone: ZoneTable | None = None
    # Reporting-only columns, in declaration order. Resolved after every
    # plan exists; see `DerivedStep`.
    derived: list[DerivedStep] = field(default_factory=list)


def tables_for_role(schema: Schema, bundle: MappingBundle, site_role: str) -> list[Table]:
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


def refuse_ambiguous_members(column: str, members: list[str]) -> None:
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


def _item_url_suffix(bundle: MappingBundle, entity_name: str) -> str:
    """What follows the list's OWN folder to reach one item's display form.

    The other half of :func:`_item_url_path`, for the branch that reads the
    folder from the site instead of building it from the declared title. A
    list's RootFolder is /Lists/<slug> and its form sits directly under it; a
    library's RootFolder is the library, and its forms sit in Forms/.
    """
    entity = bundle.mapping.entities.get(entity_name)
    if entity is not None and entity.kind == "DocumentLibrary":
        return "/Forms/DispForm.aspx?ID="
    return "/DispForm.aspx?ID="


def _projection_types(
    tables_by_name: dict[str, Table],
    target_entity: str,
    target_column: str,
    enum_names: set[str],
    *,
    source: str,
) -> tuple[str, str]:
    """The (Power Query, SQL) types one projected column reports as.

    The TARGET's column decides, not the lookup's: a projection is read
    through the same ``$expand`` the display column uses, so what arrives is
    whatever the target list holds. Reusing the lookup's own `type text`
    would put a number in a text column and truncate a Note at 255, which is
    the silently-wrong export this generator exists to avoid.

    Only the scalar kinds are answered. A projection of a person, a URL, a
    multi-value or another lookup arrives through the expand as a record or a
    collection whose shape has NOT been measured here, and guessing `type
    text` over a record is what puts an Error value in every populated cell
    while the query still loads. Those fail the build instead, naming the
    column, the way an unhandled field kind does in `build_plans`.
    """
    table = tables_by_name.get(target_entity)
    col = (
        next((c for c in table.columns if c.name == target_column), None)
        if table is not None else None
    )
    if col is None:
        # SharePoint gives every list its own `Title`, so a projection may
        # name it without the DBML declaring it. The validator allows the
        # same one exception (`_structure._lookup_projections`).
        if target_column == "Title":
            return ("type text", "NVARCHAR(255)")
        raise ValueError(
            f"{source}: projected column "
            f"{target_entity}.{target_column} is not in the schema.",
        )
    sp = map_column(col, enum_names)
    match sp.kind:
        case "Text" | "Choice":
            return ("type text", "NVARCHAR(255)")
        case "Note":
            return ("type text", "NVARCHAR(MAX)")
        case "Number":
            return ("type number", "DECIMAL(18,4)")
        case "Boolean":
            return ("type logical", "BIT")
        case "DateTime":
            if sp.date_only:
                return ("type date", "DATE")
            return ("type datetimezone", "DATETIMEOFFSET")
        case "Calculated":
            # Same three output types the direct Calculated arm resolves,
            # and for the same reason: a calculated column is number, date
            # or text and nothing else.
            if sp.output_type == 9:
                return ("type number", "DECIMAL(18,4)")
            if sp.output_type == 4:
                return ("type date", "DATE")
            return ("type text", "NVARCHAR(255)")
        case _:
            raise ValueError(
                f"{source}: reporting has no plan for a projection of "
                f"{target_entity}.{target_column}, which is SharePoint field "
                f"kind {sp.kind!r}. A projection is read through the lookup's "
                f"$expand, and the shape a {sp.kind!r} takes on that path has "
                f"not been measured, so it is refused rather than guessed. "
                f"Project a scalar column, or carry this one by joining the "
                f"target table in the model.",
            )


def _translate_refs(text: str, renames: dict[str, str]) -> str:
    """Rewrite every `[Column]` through one query's own rename map.

    An author writes internal names everywhere. A `where` and an aggregate's
    `column` read the CHILD query's rows, and that query renamed its columns
    in its last step, so the names have to be the ones it ends with. Taken
    from the plan's own rename list rather than re-derived, because that list
    IS the rename the query performs.
    """
    if not renames:
        return text
    return DERIVED_REFERENCE.sub(
        lambda match: f"[{renames.get(match.group(1), match.group(1))}]",
        text,
    )


def _resolve_derived(
    plans: list[ListPlan], bundle: MappingBundle, prefix: str,
) -> None:
    """Turn each entity's `derived_columns` into fully resolved steps.

    A post-pass, so a join can read the target plan's rename map. Entries
    naming an entity that is not reported at this site are DROPPED rather
    than emitted against a query that will not exist: the validator has
    already refused the declaration, and `report` does not validate.
    """
    by_entity = {plan.entity: plan for plan in plans}
    for plan in plans:
        for entry in bundle.mapping.derived_for(plan.entity):
            step = _derived_step(entry, plan, by_entity, prefix)
            if step is not None:
                plan.derived.append(step)


def _derived_step(
    entry: DerivedColumn,
    plan: ListPlan,
    by_entity: dict[str, ListPlan],
    prefix: str,
) -> DerivedStep | None:
    hidden = entry.hidden
    description = entry.description
    if entry.kind == "expr":
        # No translation: an `expr` reads THIS query, and at the point it
        # runs this query still carries its internal names.
        return DerivedStep(
            kind="expr",
            name=entry.name,
            m_type=DERIVED_TYPES[entry.type],
            m=entry.m,
            replace=entry.replace,
            hidden=hidden,
            description=description,
        )
    if is_users_source(entry):
        # `_Users` renames unconditionally and has no plan, so its map is
        # the shared one rather than a plan's.
        own_key, other_key = lookup_key_columns(entry, plan.entity)
        return DerivedStep(
            kind="lookup",
            source_query=USERS_KEY_LIST,
            source_entity=USERS_KEY_LIST,
            own_key=own_key,
            other_key=other_key,
            picks=tuple(
                (
                    USERS_DISPLAY_TITLES.get(source, source),
                    new_name,
                    DERIVED_TYPES[entry.types[new_name]],
                )
                for new_name, source in entry.pick.items()
            ),
            hidden=hidden,
            description=description,
        )
    target = by_entity.get(entry.from_entity)
    if target is None:
        return None
    renames = dict(target.renames)
    own_key, other_key = lookup_key_columns(entry, plan.entity)
    if entry.kind == "lookup":
        return DerivedStep(
            kind="lookup",
            source_query=prefix + entry.from_entity,
            source_entity=entry.from_entity,
            own_key=own_key,
            other_key=other_key,
            picks=tuple(
                (
                    renames.get(source, source),
                    new_name,
                    DERIVED_TYPES[entry.types[new_name]],
                )
                for new_name, source in entry.pick.items()
            ),
            hidden=hidden,
            description=description,
        )
    return DerivedStep(
        kind="count",
        name=entry.name,
        m_type=DERIVED_TYPES[entry.type],
        source_query=prefix + entry.from_entity,
        source_entity=entry.from_entity,
        own_key=own_key,
        other_key=other_key,
        aggregate=entry.aggregate,
        column=renames.get(entry.column, entry.column),
        where=_translate_refs(entry.where, renames),
        hidden=hidden,
        description=description,
    )


def build_plans(
    schema: Schema, bundle: MappingBundle, site_role: str,
) -> list[ListPlan]:
    tables = tables_for_role(schema, bundle, site_role)
    emitted = {t.name for t in tables}
    # EVERY table, not the role-filtered set: a projection reads its type off
    # the lookup target, which the mapping may well deploy to another site.
    tables_by_name = {t.name: t for t in schema.tables}
    enum_names = {e.name for e in schema.enums}
    enum_members = {e.name: e.members for e in schema.enums}
    cross_site_keys = bundle.mapping.cross_site_keys()
    prefix = bundle.mapping.prefix
    # Derived once per build, and fail-closed on a name the database does
    # not declare: `report` does not validate, so this raise is what it has.
    time_zone = bundle.mapping.reporting.time_zone
    zone = zone_table(time_zone) if time_zone is not None else None

    plans: list[ListPlan] = []
    for table in tables:
        plan = ListPlan(
            entity=table.name,
            list_title=prefix + table.name,
            item_url_path=_item_url_path(bundle, table.name, prefix + table.name),
            item_url_suffix=_item_url_suffix(bundle, table.name),
            users_table=bundle.mapping.reporting.users_table,
            zone=zone,
        )
        for col in table.columns:
            if (table.name, col.name) in cross_site_keys:
                plan.skipped.append(col.name)
                continue
            sp = map_column(col, enum_names)
            if sp.kind != "Skip":
                plan.field_internal_names.append(sp.name)
            # What a lookup into the target DISPLAYS names one of the columns
            # this field contributes, so it is resolved before the arms below
            # rather than inside the one that needs it. `display_column_for`
            # answers Title for a target with no mapping entry, which is why
            # this needs no None branch.
            lookup_display = _display_column(bundle, sp.target_list or "")
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
                    _plan_datetime(plan, sp.name, date_only=sp.date_only)
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
                    _plan_person(plan, sp.name)
                case "Lookup":
                    target = sp.target_list or ""
                    display = lookup_display
                    plan.selects.append(f"{sp.name}Id")
                    plan.selects.append(f"{sp.name}/{display}")
                    plan.expands.append(sp.name)
                    plan.record_expands.append(
                        (sp.name, display, f"{sp.name}{display}", "type text"),
                    )
                    plan.m_types.append((f"{sp.name}Id", "Int64.Type"))
                    plan.m_types.append((f"{sp.name}{display}", "type text"))
                    plan.sql_columns.append((f"{sp.name}Id", "INT"))
                    # A dependent lookup is a column of THIS list as far as
                    # SharePoint, the deploy and the data dictionary are
                    # concerned, and it reached neither generated query: the
                    # projection was planned from the lookup's DISPLAY column
                    # alone, so a projection of anything else was absent
                    # rather than blank, and a consumer had the dictionary
                    # and the release notes both promising a column their
                    # refresh would not produce.
                    #
                    # Read through the SAME $expand the display column uses,
                    # rather than as a scalar field of this list: that path
                    # is already measured to work, it answers with the
                    # target's own value (which is what the dependent field
                    # shows), and it needs no second request.
                    #
                    # The display column is dropped where a projection names
                    # it, because both would land as one column name and
                    # `Table.ExpandRecordColumn` refuses the duplicate.
                    projected = tuple(
                        target_column
                        for target_column in bundle.mapping.projections_for(
                            table.name, col.name,
                        )
                        if target_column != display
                    )
                    for target_column in projected:
                        out = projection_output_name(sp.name, target_column)
                        m_type, _sql_type = _projection_types(
                            tables_by_name, target, target_column, enum_names,
                            source=f"{table.name}.{col.name}",
                        )
                        plan.selects.append(f"{sp.name}/{target_column}")
                        plan.record_expands.append(
                            (sp.name, target_column, out, m_type),
                        )
                        plan.m_types.append((out, m_type))
                    if target in emitted:
                        plan.joins.append(
                            (f"{sp.name}Id", prefix + target, display, projected),
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
                    refuse_ambiguous_members(
                        sp.name, enum_members.get(sp.choices_enum or "", []),
                    )
                    plan.selects.append(sp.name)
                    plan.multi_value_joins.append((sp.name, True))
                    plan.sql_columns.append((sp.name, "NVARCHAR(MAX)"))
                case "LookupMulti":
                    # Everything the MultiChoice arm above argues applies here
                    # too: the cell holds a list, so it is joined to one text
                    # cell before anything types anything, and the joined
                    # string is NVARCHAR(MAX) because a set has no bound worth
                    # guessing.
                    #
                    # THREE THINGS DIVERGE FROM THE SINGLE-VALUE Lookup ARM.
                    # No `$expand`: expanding a collection yields a nested
                    # TABLE per row rather than a record, and there is no
                    # machinery here that flattens one. No star-schema join
                    # either, because `joins` maps one foreign key to one
                    # dimension row and a set of ids is not one key. And the
                    # members are ids, measured 2026-09-02 as
                    # Collection(Edm.Int32) in verbose and a bare array of
                    # numbers under nometadata (the dialect this layer
                    # speaks), so they are converted to text before the join.
                    #
                    # The cell therefore holds ids, not titles. Joining the
                    # target's display column would need the expand this arm
                    # does not do; the ids resolve against the target list's
                    # own query, which the same bundle emits.
                    plan.selects.append(f"{sp.name}Id")
                    plan.multi_value_joins.append((f"{sp.name}Id", False))
                    plan.sql_columns.append((f"{sp.name}Id", "NVARCHAR(MAX)"))
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
                        f"reporting.plan.build_plans giving it a $select, a Power "
                        f"Query type and a SQL column type -- and a matching "
                        f"arm in _sp_type_cell -- rather than letting it fall "
                        f"out of every generated query.",
                    )
            # After the arms, so an unhandled kind is refused by the `case _`
            # above with the entity and the column in the message rather than
            # by the shared derivation's `assert_never`, which knows neither.
            plan.output_columns += report_output_names(
                sp, lookup_display=lookup_display,
                projections=tuple(bundle.mapping.projections_for(
                    table.name, col.name,
                )),
            )
        # After the schema's own columns, so they sit at the end of every
        # query and view. MEASURED 2026-09-02 on a live tenant: /items answers
        # $select=Created,Modified,AuthorId,Author/Title,EditorId,Editor/Title
        # with $expand=Author,Editor in the same shape as a declared person
        # or date-time column, which is why they ride the same two helpers.
        system_outputs: set[str] = set()
        if bundle.mapping.reporting.system_columns:
            for name in REPORT_SYSTEM_COLUMNS:
                kind = SYSTEM_COLUMN_TYPES[name]
                if is_person(kind):
                    _plan_person(plan, name)
                    system_outputs.update((f"{name}Id", f"{name}Title"))
                elif kind == "datetime":
                    _plan_datetime(plan, name, date_only=False)
                    system_outputs.add(name)
                else:
                    raise ValueError(
                        f"reporting has no plan for system column {name!r} "
                        f"of kind {kind!r}",
                    )
        if bundle.mapping.display_name_mode is not None:
            # Derived out-columns (FooId/FooTitle/FooUrl) resolve through the
            # same map: overrides hit exact column names, everything else
            # auto-splits ("RiskOwnerTitle" -> "Risk Owner Title").
            #
            # Read off `output_columns` rather than off `m_types` plus
            # `multi_value_joins`, so the set renamed here is the set
            # `checks/_naming` refuses a collision against. The system
            # columns are absent from it by construction: they are not
            # declared fields, and the loop below gives them SharePoint's own
            # titles.
            pack_columns = [ITEM_URL_COLUMN, ITEM_URL_RESOLVED_COLUMN]
            if reads_zone(plan):
                pack_columns.append(DATE_ZONE_RESOLVED_COLUMN)
            # A derived column is renamed with the rest: it is a column of
            # the model like any other, and leaving it out would be the one
            # place a report author meets an internal name.
            derived_names = [
                name
                for entry in bundle.mapping.derived_for(table.name)
                for name in derived_output_names(entry)
            ]
            for out_name in [
                *plan.output_columns, *pack_columns, *derived_names,
            ]:
                display = bundle.mapping.display_name_for(table.name, out_name)
                if display != out_name:
                    plan.renames.append((out_name, display))
            # System columns are not the mapping's to rename: they take
            # SharePoint's own display titles, through the same
            # "<Display> Id" / "<Display> Title" shape as a declared person
            # column, so they sit consistently beside one.
            for name, title in SYSTEM_DISPLAY_TITLES.items():
                if f"{name}Id" in system_outputs:
                    plan.renames.append((f"{name}Id", f"{title} Id"))
                    plan.renames.append((f"{name}Title", f"{title} Title"))
        plans.append(plan)
    # The SQL side selects a projection from the TARGET's view, so it can
    # only carry the ones that view actually has. The Power Query has no
    # such limit: it reads the target through the expand, so a projection of
    # a column the SQL views cannot reach is still in the M query.
    landed = {
        plan.list_title: {name for name, _ in plan.sql_columns}
        for plan in plans
    }
    for plan in plans:
        plan.joins = [
            (
                fk_column, target_title, display,
                tuple(
                    target_column for target_column in projections
                    if target_column in landed.get(target_title, set())
                ),
            )
            for fk_column, target_title, display, projections in plan.joins
        ]
    _resolve_derived(plans, bundle, prefix)
    return plans


def _plan_person(plan: ListPlan, name: str) -> None:
    """A person column: the site-user id as the join key, the display name
    through a guarded expand, and display text on the SQL side."""
    plan.selects.append(f"{name}Id")
    plan.selects.append(f"{name}/Title")
    plan.expands.append(name)
    plan.record_expands.append((name, "Title", f"{name}Title", "type text"))
    plan.m_types.append((f"{name}Id", "Int64.Type"))
    plan.m_types.append((f"{name}Title", "type text"))
    plan.sql_columns.append((name, "NVARCHAR(255)"))
    plan.person_columns.append(name)


def _plan_datetime(plan: ListPlan, name: str, *, date_only: bool) -> None:
    plan.selects.append(name)
    if date_only:
        plan.m_types.append((name, "type date"))
        plan.sql_columns.append((name, "DATE"))
    else:
        plan.m_types.append((name, "type datetimezone"))
        plan.sql_columns.append((name, "DATETIMEOFFSET"))


# The two M type tokens `AsDate` covers, and so the two that must be kept out
# of `Table.TransformColumnTypes`. Only `type date` today: a calculated column
# is number, date or text, so `type datetimezone` always arrives typed.
TOLERANT_DATE_TYPES = frozenset({"type date"})


def grouped_record_expands(
    plan: ListPlan,
) -> list[tuple[str, list[tuple[str, str, str]]]]:
    """`record_expands` gathered by source record column, first appearance
    first. See `_render_m` for why one step per record is not optional."""
    grouped: list[tuple[str, list[tuple[str, str, str]]]] = []
    at: dict[str, int] = {}
    for record_col, inner, out, m_type in plan.record_expands:
        if record_col not in at:
            at[record_col] = len(grouped)
            grouped.append((record_col, []))
        grouped[at[record_col]][1].append((inner, out, m_type))
    return grouped


def tolerant_date_columns(plan: ListPlan) -> list[str]:
    """The columns `AsDate` converts, and so whether the query reads the
    site's time zone at all. Asked by the planner (which decides whether
    `DateZoneResolved` is one of this list's columns) and by the renderer
    (which writes the steps), so it cannot be answered differently twice."""
    return [
        name for name, m_type in plan.m_types
        if m_type in TOLERANT_DATE_TYPES
    ]


def reads_zone(plan: ListPlan) -> bool:
    """Whether the query reads the site's zone, and so carries
    `DateZoneResolved`: for a date-only column, or for a declared zone,
    whose agreement check has nowhere else to surface. Asked by the planner
    and by the renderer; `analysis/derived.py` answers the same for the
    column list, and the family sweep in `test_derived_columns` holds the
    two together."""
    return plan.zone is not None or bool(tolerant_date_columns(plan))
