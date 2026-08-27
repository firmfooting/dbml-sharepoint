# src/dbml_sharepoint/analysis/checks/_structure.py
"""Entities, cross-site references, indexes, deferred lookups, calculated columns."""

import re
from collections.abc import Set as AbstractSet

from dbml_sharepoint.analysis.checks.context import ValidationContext
from dbml_sharepoint.analysis.column_refs import formula_column_refs
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.limits import (
    INDEX_WARN_AT,
    LIST_VIEW_THRESHOLD,
    MAX_CALCULATED_FORMULA,
    MAX_INTERNAL_NAME,
    MAX_LIST_INDEXES,
)
from dbml_sharepoint.analysis.list_description import (
    DESCRIPTION_LIMIT,
    MARKER_GROWTH_RESERVE,
    NAME_BUDGET,
    family_for,
    marker_for,
    note_budget,
)
from dbml_sharepoint.analysis.lookups import (
    display_column_for,
    lookup_target_entities,
)
from dbml_sharepoint.analysis.ordering import compute_phases
from dbml_sharepoint.analysis.rendered_columns import rendered_columns
from dbml_sharepoint.analysis.typemap import (
    CALCULATED_TYPE_LIST,
    CALCULATED_TYPES,
    MULTI_VALUE_SP_TYPE_NAME,
    element_type,
    is_multi_value,
    unsupported_index_reason,
)
from dbml_sharepoint.model.mapping_types import CrossSiteRef, EntityMapping
from dbml_sharepoint.model.parser import Column, Schema, Table

# Calculated fields accept only a subset of column types as operands.
# Microsoft lists Single line of text, Number, Currency, Date and Time,
# Choice, Yes/No and Calculated, and its formula examples state explicitly
# that Lookup fields are not supported:
# https://support.microsoft.com/en-us/sharepoint/lists/data-and-lists/examples-of-common-formulas-in-lists
#
# MEASURED, not inferred. test/manual/calculated-operand-probe.js was run
# against a live SharePoint Online site on 2026-07-30 and answered all twelve
# of its questions. Every type below was REFUSED at createfieldasxml with
# HTTP 500 and one identical body:
#
#   "One or more column references are not allowed, because the columns are
#    defined as a data type that is not supported in formulas."
#
# The same run ACCEPTED Yes/No, Choice, Date-only, Date-and-time, Number,
# single line of text, and a calculated column feeding another calculated
# column, which is where _SUPPORTED_CALCULATED_OPERANDS below comes from.
#
# longtext, richtext and hyperlink were deliberately left OUT of this denylist
# until that run existed, on the grounds that Microsoft's silence about a type
# is not evidence against it. The run closed the question: all three are
# refused, and the guess would have been right for the wrong reason.
_FORBIDDEN_CALCULATED_OPERANDS = {
    "lookup": "a Lookup column",
    "person": "a Person column",
    "longtext": "a plain multi-line-text column",
    "richtext": "a rich-text column",
    "hyperlink": "a Hyperlink column",
}

# The operand types the same live run accepted. Named in the error message
# because "not that one" leaves an author guessing which types remain.
_SUPPORTED_CALCULATED_OPERANDS = (
    "single line of text, number, date, date/time, Choice, Yes/No, or another "
    "calculated column"
)

# The generic list. It is the only BaseTemplate this tool builds for, and
# every declaration in the repository is this value.
#
# Checked as an ALLOWLIST rather than a denylist on 101. `base_template` is
# an unconstrained int read straight from the mapping and posted straight to
# SharePoint, so refusing only the library template would close one integer
# and leave 109, 119, 851 and the rest one keystroke from the same defect.
# Stating what this tool builds needs no claim about SharePoint's behaviour,
# which refusing a specific list of templates would.
_GENERIC_LIST_TEMPLATE = 100



def _no_room_for_any_note(family: str, entity_name: str) -> str:
    """The remedy to offer when the note budget is ZERO.

    At `len(family) + len(entity)` of 184 or more the marker plus the reserve
    fill the Description on their own, and `note_budget` clamps to zero. The
    two note rules are then JOINTLY UNSATISFIABLE: no note fires
    `ENTITY_HAS_NO_NOTE`, and any note at all fires
    `ENTITY_NOTE_TOO_LONG_FOR_MARKER`. Neither rule is wrong -- the list really
    is anonymous, and the note really does not fit -- but their ordinary advice
    is not: "add a note of up to 0 characters" and "shorten the note by N" are
    both instructions the author cannot carry out.

    So when the budget is zero, both messages say the actionable thing instead,
    which is that the NAMES are what has to change. It takes absurd names to
    reach -- no shipped family is within a hundred characters of it -- but a
    message that sends someone in a circle is worse the rarer it is, because
    nobody will have seen it before.
    """
    return (
        f"No note of any length can be accepted here: the family name "
        f"{family!r} ({len(family)} characters) and the entity name "
        f"{entity_name!r} ({len(entity_name)} characters) leave the "
        f"{DESCRIPTION_LIMIT}-character list Description with no room beside "
        f"the marker and the {MARKER_GROWTH_RESERVE} characters reserved for "
        f"it to grow into. Shorten the DBML `Project` name or the table name; "
        f"together they must come to under {NAME_BUDGET} characters for a note "
        f"to fit at all."
    )


def _note_is_present(table: Table | None, entity_name: str, family: str) -> list[Finding]:
    """Refuse an entity whose table carries no `Note:` at all.

    A list Description is the one list-level sentence this tool writes, and a
    table with no note deploys a list whose Description is the provenance
    marker and nothing else. The list works, the marker is intact and fleet
    reporting still finds it -- so nothing downstream ever complains. What is
    lost is the only place an adopter opening list settings is told what the
    list is for, and that loss is invisible from every direction except the
    settings page itself.

    Skipped when the table is missing: `ENTITY_NOT_IN_SCHEMA` already reports
    that, and "your table has no note" is unhelpful advice about a table that
    does not exist.

    A whitespace-only note counts as absent, because that is what
    `list_description` does with it -- it strips, and an all-space note
    composes exactly the same Description an empty one does.
    """
    if table is None or table.note.strip():
        return []
    budget = note_budget(family, entity_name)
    remedy = (
        f"Add a Note: to the {entity_name} table -- up to {budget} characters "
        f"fit beside the marker -- saying what the list is for and who uses it."
        if budget > 0
        else _no_room_for_any_note(family, entity_name)
    )
    return [Finding(
        FindingCode.ENTITY_HAS_NO_NOTE,
        f"{entity_name}: the table has no Note:, so this list deploys with "
        f"{marker_for(family, entity_name)!r} as its entire Description and "
        f"nothing telling an adopter what it holds. {remedy}",
        location=Location(Section.ENTITIES, entity=entity_name),
    )]


# A run of horizontal whitespace, the shape the retired round-trip rule
# refused. The probe measured ASCII spaces only, so runs containing a tab or a
# non-breaking space stay refused until something measures them.
_HORIZONTAL_WHITESPACE_RUN = re.compile(r"[^\S\r\n]{2,}")


def _note_whitespace_is_measured(
    table: Table | None, entity_name: str,
) -> list[Finding]:
    """Refuse a whitespace run this project has not measured a round trip for.

    `entity_note_may_not_round_trip` refused every run of two or more
    horizontal whitespace characters. `test/manual/list-description-probe.js`
    measured two ASCII spaces on 2026-08-14 and found them preserved, so that
    case is allowed now. A run containing a tab or a non-breaking space was
    never sent, and if SharePoint collapses one the deploy's byte compare
    aborts every paste after a partial deployment.

    A single tab is left alone, because the retired rule allowed it and this
    one must not be stronger than the rule it narrows.

    Runs of plain spaces are allowed at any length, from a measurement of two.
    Collapsing is one behaviour rather than a per-length one: a normaliser
    that shortens a run shortens the shortest run there is, and two came back
    uncollapsed. A different CHARACTER is a different question, which is why
    tabs and non-breaking spaces stay refused. L11 in the probe sends a longer
    run so the next run settles it by observation instead.
    """
    if table is None:
        return []
    note = table.note.strip()
    unmeasured = sorted({
        char
        for run in _HORIZONTAL_WHITESPACE_RUN.finditer(note)
        for char in run.group()
        if char != " "
    })
    if not unmeasured:
        return []
    named = ", ".join(f"U+{ord(c):04X}" for c in unmeasured)
    return [Finding(
        FindingCode.ENTITY_NOTE_WHITESPACE_UNMEASURED,
        f"{entity_name}: the table's Note: contains a whitespace run holding "
        f"{named}, and no probe has measured whether SharePoint returns it "
        f"unchanged. Plain spaces were measured on 2026-08-14 and are fine. "
        f"Use single spaces between words, or plain spaces if you meant "
        f"alignment.",
        location=Location(Section.ENTITIES, entity=entity_name),
    )]


def _note_fits_beside_marker(
    table: Table | None, entity_name: str, family: str,
) -> list[Finding]:
    """Refuse a table `Note:` too long to leave room for the provenance marker.

    The deployed list Description is the note followed by a marker, and fleet
    reporting discovers the list BY that marker. So the marker is never
    truncated and the note is refused here instead.

    Truncating the note would lose prose, which anyone who opens list settings
    can see. Truncating the marker loses the list from every fleet report --
    and NOTHING can see that: the list provisions, the Description the deploy
    reads back matches the truncated one it sent, and every deploy phase
    passes. Build time is the last point at which the mistake is still
    observable.

    A list Description round-trips byte for byte, MEASURED 2026-08-14 by
    `test/manual/list-description-probe.js`. This rule does not depend on
    that, because a truncated marker is invisible whether the read-back
    compares equal or aborts the run.

    The budget is computed rather than a constant, because it depends on the
    length of the family and entity names inside the marker. It comes from the
    same module `generators.jsgen` composes the description with, so the rule
    and the emitter cannot disagree about what fits.
    """
    note = table.note.strip() if table is not None else ""
    budget = note_budget(family, entity_name)
    if len(note) <= budget:
        return []
    remedy = (
        f"Shorten the note by {len(note) - budget} character(s). "
        f"{MARKER_GROWTH_RESERVE} further characters of the "
        f"{DESCRIPTION_LIMIT}-character list Description would fit but are "
        f"held in reserve, so that the marker can grow without invalidating "
        f"notes already written."
        if budget > 0
        # At a budget of zero "shorten it by 41 characters" means "delete all
        # of it", which the other note rule then refuses. See
        # `_no_room_for_any_note`.
        else _no_room_for_any_note(family, entity_name)
    )
    return [Finding(
        FindingCode.ENTITY_NOTE_TOO_LONG_FOR_MARKER,
        f"{entity_name}: the table's Note: is {len(note)} characters, but the "
        f"budget beside the provenance marker "
        f"{marker_for(family, entity_name)!r} is {budget}. The marker is how "
        f"fleet reporting finds this list, so it is never truncated. "
        f"{remedy}",
        location=Location(Section.ENTITIES, entity=entity_name),
    )]


def check(vc: ValidationContext) -> list[Finding]:
    # Shared with `lookup_display_columns`, which decides which lists get the
    # picker's index. A second copy of this comprehension is how the
    # display-column warning comes to fire for a list the deployer never
    # indexes, or stay silent for one it does, and it did: a list reached only
    # by a CROSS-SITE ref has no picker at all, so it was told its picker would
    # stop working.
    lookup_targets = lookup_target_entities(vc.schema, vc.cross_site_pairs)

    # The family the emitter will stamp into every list Description. Resolved
    # once, from the same helper `generators.jsgen` uses, so the budget this
    # rule enforces is the budget the emitter actually has.
    family = family_for(vc.schema)

    return [
        *_entities(vc, lookup_targets, family),
        *_mapping_and_schema_agree(vc),
        *_cross_site_references(vc),
        *_lookup_projections(vc),
        *_indexes(vc),
        *_entity_keyed_sections(vc),
        *_calculated_columns(vc),
    ]


def _entities(
    vc: ValidationContext, lookup_targets: set[str], family: str,
) -> list[Finding]:
    """Every rule that reads one entity's own declaration, in mapping order."""
    findings: list[Finding] = []
    for entity_name, entity in vc.bundle.mapping.entities.items():
        table = vc.tables_by_name.get(entity_name)
        findings += _entity_kind(entity_name, entity)
        findings += _note_is_present(table, entity_name, family)
        findings += _note_whitespace_is_measured(table, entity_name)
        findings += _note_fits_beside_marker(table, entity_name, family)
        findings += _display_column(vc, entity_name, entity, lookup_targets)
    return findings


def _entity_kind(entity_name: str, entity: EntityMapping) -> list[Finding]:
    """Refuse a document library, and every BaseTemplate but the generic list.

    `kind: DocumentLibrary` is REFUSED, and refused here so that it fails at
    build rather than part-way through a paste.

    A library's items are files, and this tool writes list rows. The gap is not
    cosmetic: SharePoint answers a POST to a library's /items with HTTP 500,
    "To add an item to a document library, use SPFileCollection.Add()", so
    seeded demo data cannot exist; a library's Title is null after an upload,
    with the name in FileLeafRef, so the standard form header renders blank on
    every document; and the deploy has no upload step to offer instead. Each of
    those was observed on a tenant on 2026-07-29
    (test/manual/document-library-probe.js).

    Half-support (a library that provisions but can carry no view naming its
    files, no usable header and no demo rows) reads as a bug in every
    direction. Refusing is the honest state until the work in issue #14 is
    done: a file-upload step in the deploy, a file-identity column vocabulary,
    and a header anatomy that does not rest on [$Title].
    """
    if entity.kind == "DocumentLibrary":
        return [Finding(
            FindingCode.DOCUMENT_LIBRARY_UNSUPPORTED,
            f"entities[{entity_name}]: kind 'DocumentLibrary' is not supported. "
            f"A library's items are files and this tool writes list rows, so a "
            f"library cannot carry seeded demo data (SharePoint refuses a POST to "
            f"/items outright), its Title is empty after an upload so the standard "
            f"form header renders blank, and nothing here uploads a file. Model the "
            f"metadata as a 'List' and keep the documents in a library you manage "
            f"separately, linking to it with a hyperlink column. See issue #14 for "
            f"the measurements behind this and what support would require.",
            location=Location(Section.ENTITIES, entity=entity_name),
        )]

    # Returned above rather than reported beside it, so a DocumentLibrary
    # reports the kind rather than a second complaint about the 101 it was
    # always going to carry.
    #
    # This is the door the message above holds open. An author told to
    # "model the metadata as a 'List'" who changes `kind` and leaves
    # `base_template: 101` behind got a GREEN build that provisioned a
    # real library: `_lists.js.j2` sends BaseTemplate and never sends
    # `kind`, while every library guard in the build keys on `kind` and
    # so does not fire. The refusal above would have been bypassed by
    # the very edit it recommends.
    if entity.base_template != _GENERIC_LIST_TEMPLATE:
        return [Finding(
            FindingCode.UNSUPPORTED_BASE_TEMPLATE,
            f"entities[{entity_name}]: base_template {entity.base_template} is not "
            f"supported; this tool builds generic lists (BaseTemplate "
            f"{_GENERIC_LIST_TEMPLATE}). The create call sends BaseTemplate and "
            f"never sends 'kind', so SharePoint would provision whatever this "
            f"number names while the rest of the build treats {entity_name} as a "
            f"'{entity.kind}'. If you meant a document library, that kind is "
            f"refused outright -- see issue #14.",
            location=Location(Section.ENTITIES, entity=entity_name),
        )]
    return []


def _display_column(
    vc: ValidationContext,
    entity_name: str,
    entity: EntityMapping,
    lookup_targets: set[str],
) -> list[Finding]:
    """Refuse or warn about a display column a lookup picker cannot enumerate.

    A lookup's picker enumerates its target list. A calculated display
    column cannot be indexed, so the enumeration is refused once the
    target passes the threshold and the column becomes unsettable.
    MEASURED 2026-07-31, test/manual/templates/threshold-index-probe.js.j2:
    at 6,500 items in the target, GetLookupFieldChoices served an indexed
    ShowField (2,000 choices) and refused both calculated ones with
    SPQueryThrottledException; and CALCIDX set Indexed=true on a
    calculated column, the MERGE was ACCEPTED, and the flag read back
    false.

    A warning rather than an error because a list that stays small has no
    problem, and that is a common, legitimate case.
    """
    findings: list[Finding] = []
    display = display_column_for(entity)
    is_calculated = display in vc.calculated_by_entity.get(entity_name, set())
    if entity_name in lookup_targets and is_calculated:
        if not entity.accept_unindexable_display_column:
            findings.append(Finding(
                FindingCode.CALCULATED_DISPLAY_COLUMN_UNINDEXABLE,
                f"{entity_name}.display_column: {display!r} is a calculated "
                f"column. Calculated columns cannot be indexed, so this "
                f"list's lookup picker stops working once it passes roughly "
                f"{LIST_VIEW_THRESHOLD:,} items: the new-item form fails with \"exceeds the "
                f"list view threshold\" while views carry on working "
                f"normally. If this list will stay small, set "
                f"accept_unindexable_display_column: true on the entity.",
                location=Location(
                    Section.ENTITIES, entity=entity_name, sub="display_column",
                ),
            ))
    elif entity.accept_unindexable_display_column:
        # Reaching here means NOT (target AND calculated), which is three
        # combinations, not one. The message used to assert "the display
        # column is not calculated" in all three, false for a calculated
        # display column on an entity nothing looks up, which is precisely
        # the case an author is most likely to have set the key for. State
        # only what is true of the branch actually taken.
        reasons = []
        if entity_name not in lookup_targets:
            reasons.append("nothing looks this entity up")
        if not is_calculated:
            reasons.append(f"the display column {display!r} is not calculated")
        findings.append(Finding(
            FindingCode.REDUNDANT_DISPLAY_COLUMN_ACCEPTANCE,
            f"{entity_name}: accept_unindexable_display_column is set, but "
            + " and ".join(reasons)
            + ". Remove it -- there is nothing to accept.",
            location=Location(
                Section.ENTITIES, entity=entity_name,
                sub="accept_unindexable_display_column",
            ),
        ))
    return findings + _display_column_index(
        vc, entity_name, display, is_calculated, lookup_targets,
    )


def _display_column_index(
    vc: ValidationContext,
    entity_name: str,
    display: str,
    is_calculated: bool,
    lookup_targets: set[str],
) -> list[Finding]:
    """Guard the index a lookup target's display column gets automatically.

    The display column's index is IMPLICIT: it is appended in
    generators/jsgen.py rather than declared in `indexes { }`, so neither of
    the two guards a declared entry passes applies to it. Both apply just as
    hard.

    An unindexable type here is a DEPLOY ABORT, not a cosmetic miss:
    templates/deploy/_field_reconcile.js.j2 sets desired.indexed = true,
    MERGEs it, reads the flag back and THROWS when it did not stick,
    part-way through a run, after earlier phases have written to the site.
    Errors, not warnings: no acceptance can make a Note column indexable,
    which is what separates these from the calculated case above.
    """
    table = vc.tables_by_name.get(entity_name)
    if entity_name not in lookup_targets or is_calculated or table is None:
        return []
    findings: list[Finding] = []
    display_xcols = vc.cross_site_columns(entity_name)
    declared_names = {col.name: col for col in table.columns}
    rendered_names = rendered_columns(table, display_xcols)
    if display in declared_names and display not in rendered_names:
        # A name that is not declared AT ALL is already reported by
        # analysis.checks._naming, which sees every lookup into this
        # entity. Only the declared-but-not-rendered case is invisible
        # there: a cross-site logical column, or the auto-increment Id.
        hint = (
            " -- a cross-site logical column is replaced by generated "
            "Abbreviation and SiteUrl fields, so it never exists on the "
            "list"
            if display in display_xcols
            else ""
        )
        findings.append(Finding(
            FindingCode.DISPLAY_COLUMN_NOT_RENDERED,
            f"{entity_name}.display_column: {display!r} is not a "
            f"rendered column of {entity_name}{hint}. It is indexed "
            f"automatically because this list is a lookup target, so "
            f"the deploy would create that index on a field that does "
            f"not exist.",
            location=Location(
                Section.ENTITIES, entity=entity_name, sub="display_column",
            ),
        ))
    display_column = declared_names.get(display)
    unindexable = (
        None if display_column is None
        else unsupported_index_reason(display_column.type)
    )
    if unindexable is not None:
        findings.append(Finding(
            FindingCode.DISPLAY_COLUMN_TYPE_UNINDEXABLE,
            f"{entity_name}.display_column: {display!r} is a "
            f"{unindexable} column, "
            f"which SharePoint cannot index. A lookup target's display "
            f"column is indexed automatically so its picker keeps "
            f"working past {LIST_VIEW_THRESHOLD:,} items, and the deploy sets "
            f"Indexed=true, reads it back and fails when it did not "
            f"stick. Name an indexable column as display_column.",
            location=Location(
                Section.ENTITIES, entity=entity_name, sub="display_column",
            ),
        ))
    return findings


def _mapping_and_schema_agree(vc: ValidationContext) -> list[Finding]:
    """Every mapping entity needs a table, and every table a mapping entry."""
    findings: list[Finding] = []
    # Every entity in the mapping must exist in the schema.
    for entity_name in vc.bundle.mapping.entities:
        if entity_name not in vc.table_names:
            findings.append(Finding(
                FindingCode.ENTITY_NOT_IN_SCHEMA,
                f"Mapping references unknown entity: {entity_name}",
                location=Location(Section.ENTITIES, entity=entity_name),
            ))

    # ...and every schema table must have a mapping entry (opposite direction).
    # build_schema_json silently skips unmapped tables, so an unmapped schema
    # entity would otherwise be dropped from the deploy plan without any error.
    for table in vc.schema.tables:
        if table.name not in vc.bundle.mapping.entities:
            findings.append(Finding(
                FindingCode.UNMAPPED_SCHEMA_TABLE,
                f"Schema table {table.name} has no mapping entry in "
                "sharepoint-mapping.yaml (would be omitted from the deploy plan).",
                location=Location(Section.SCHEMA, entity=table.name),
            ))
    return findings


def _cross_site_references(vc: ValidationContext) -> list[Finding]:
    """Every cross-site reference must point at an existing entity + column ref."""
    findings: list[Finding] = []
    for xref in vc.bundle.mapping.cross_site_reference_columns:
        if xref.entity not in vc.table_names:
            findings.append(Finding(
                FindingCode.UNKNOWN_ENTITY,
                f"cross_site_reference_columns: entity {xref.entity} not in schema",
                location=Location(Section.CROSS_SITE_REFERENCE_COLUMNS),
            ))
            continue
        table = next(t for t in vc.schema.tables if t.name == xref.entity)
        col = next((c for c in table.columns if c.name == xref.column), None)
        if col is None:
            findings.append(Finding(
                FindingCode.CROSS_SITE_UNKNOWN_COLUMN,
                f"cross_site_reference_columns: {xref.entity}.{xref.column} not in schema",
                location=Location(Section.CROSS_SITE_REFERENCE_COLUMNS),
            ))
        elif col.ref is None:
            findings.append(Finding(
                FindingCode.CROSS_SITE_COLUMN_HAS_NO_REF,
                f"cross_site_reference_columns: {xref.entity}.{xref.column} has no ref:",
                location=Location(Section.CROSS_SITE_REFERENCE_COLUMNS),
            ))
        else:
            if col.unique:
                findings.append(Finding(
                    FindingCode.CROSS_SITE_COLUMN_CANNOT_BE_UNIQUE,
                    f"{xref.entity}.{xref.column}: a cross-site reference cannot "
                    "be unique. Its logical DBML column is replaced by generated "
                    "Abbreviation and SiteUrl fields, so the column-level unique "
                    "constraint would not be deployed.",
                    location=Location(
                        Section.CROSS_SITE_REFERENCE_COLUMNS,
                        entity=xref.entity, column=xref.column,
                    ),
                ))
            findings += _cross_site_generated_names(xref, table)
    return findings


def _cross_site_generated_names(xref: CrossSiteRef, table: Table) -> list[Finding]:
    """The two companion fields a cross-site column expands into.

    Cross-site columns expand to <name>Abbreviation + <name>SiteUrl at deploy
    time. The longer of the two ("Abbreviation") plus the column name must fit
    within MAX_INTERNAL_NAME.
    """
    findings: list[Finding] = []
    for suffix in ("Abbreviation", "SiteUrl"):
        generated = xref.column + suffix
        if len(generated) > MAX_INTERNAL_NAME:
            findings.append(Finding(
                FindingCode.CROSS_SITE_GENERATED_NAME_TOO_LONG,
                f"cross_site {xref.entity}.{xref.column}: generated "
                f"name '{generated}' is {len(generated)} chars; "
                f"SP internal-name limit is {MAX_INTERNAL_NAME}.",
                location=Location(
                    Section.CROSS_SITE_REFERENCE_COLUMNS,
                    entity=xref.entity, column=xref.column, sub=generated,
                ),
            ))
        if any(col.name == generated and col.name != xref.column for col in table.columns):
            findings.append(Finding(
                FindingCode.CROSS_SITE_GENERATED_NAME_COLLIDES,
                f"cross_site {xref.entity}.{xref.column}: generated field "
                f"{generated!r} collides with the declared DBML column "
                f"{xref.entity}.{generated}.",
                location=Location(
                    Section.CROSS_SITE_REFERENCE_COLUMNS,
                    entity=xref.entity, column=xref.column, sub=generated,
                ),
            ))
    return findings


def _lookup_projections(vc: ValidationContext) -> list[Finding]:
    """Every lookup projection must name a real lookup column that is not a
    cross-site reference, project columns that render on the target, and
    generate field names that fit the internal-name limit and collide with
    neither a declared column nor another projection."""
    findings: list[Finding] = []
    for entity_name, columns in vc.bundle.mapping.lookup_projections.items():
        if entity_name not in vc.table_names:
            findings.append(Finding(
                FindingCode.UNKNOWN_ENTITY,
                f"lookup_projections: entity {entity_name} not in schema",
                location=Location(Section.LOOKUP_PROJECTIONS),
            ))
            continue
        table = vc.tables_by_name[entity_name]
        generated_here: set[str] = set()
        for column, targets in columns.items():
            col = next((c for c in table.columns if c.name == column), None)
            if col is None:
                findings.append(Finding(
                    FindingCode.PROJECTION_UNKNOWN_COLUMN,
                    f"lookup_projections: {entity_name}.{column} not in schema",
                    location=Location(
                        Section.LOOKUP_PROJECTIONS, entity=entity_name,
                    ),
                ))
                continue
            if col.ref is None:
                findings.append(Finding(
                    FindingCode.PROJECTION_COLUMN_HAS_NO_REF,
                    f"lookup_projections: {entity_name}.{column} has no ref:",
                    location=Location(
                        Section.LOOKUP_PROJECTIONS,
                        entity=entity_name, column=column,
                    ),
                ))
                continue
            if column in vc.cross_site_columns(entity_name):
                findings.append(Finding(
                    FindingCode.PROJECTION_ON_CROSS_SITE_REF,
                    f"lookup_projections: {entity_name}.{column} is a "
                    "cross-site reference, which expands to Choice and URL "
                    "fields rather than a primary lookup, so it cannot carry "
                    "a dependent projection.",
                    location=Location(
                        Section.LOOKUP_PROJECTIONS,
                        entity=entity_name, column=column,
                    ),
                ))
                continue
            target_table = vc.tables_by_name.get(col.ref.target_table)
            target_rendered = (
                rendered_columns(
                    target_table,
                    vc.cross_site_columns(col.ref.target_table),
                )
                | {"Title"}
                if target_table is not None else set()
            )
            for target in targets:
                generated = f"{column}{target}"
                if len(generated) > MAX_INTERNAL_NAME:
                    findings.append(Finding(
                        FindingCode.PROJECTION_NAME_TOO_LONG,
                        f"lookup_projections {entity_name}.{column}: generated "
                        f"name {generated!r} is {len(generated)} chars; "
                        f"SP internal-name limit is {MAX_INTERNAL_NAME}.",
                        location=Location(
                            Section.LOOKUP_PROJECTIONS,
                            entity=entity_name, column=column, sub=generated,
                        ),
                    ))
                if target_table is not None and target not in target_rendered:
                    findings.append(Finding(
                        FindingCode.PROJECTION_UNKNOWN_TARGET_COLUMN,
                        f"lookup_projections {entity_name}.{column}: target "
                        f"{col.ref.target_table}.{target} is not a rendered "
                        f"column of the lookup target.",
                        location=Location(
                            Section.LOOKUP_PROJECTIONS,
                            entity=entity_name, column=column, sub=target,
                        ),
                    ))
                if (
                    generated in generated_here
                    or any(c.name == generated for c in table.columns)
                ):
                    findings.append(Finding(
                        FindingCode.PROJECTION_NAME_COLLIDES,
                        f"lookup_projections {entity_name}.{column}: generated "
                        f"field {generated!r} collides with another generated "
                        f"or declared column.",
                        location=Location(
                            Section.LOOKUP_PROJECTIONS,
                            entity=entity_name, column=column, sub=generated,
                        ),
                    ))
                generated_here.add(generated)
    return findings


def _indexes(vc: ValidationContext) -> list[Finding]:
    """The indexes one list declares, and the ceiling they count against.

    DBML table indexes are the sole source of ordinary SharePoint indexes.
    The deployer can represent only a one-column index and SharePoint does
    not expose DBML's SQL name/type options, so unsupported structure is a
    build error rather than silently discarded metadata.
    """
    findings: list[Finding] = []
    for entity_name in vc.bundle.mapping.entities:
        table = vc.tables_by_name.get(entity_name)
        if table is None:
            continue
        indexed = _index_targets(table)
        findings += _index_declarations(entity_name, table)
        findings += _duplicate_indexes(vc, entity_name, indexed)
        findings += _index_ceiling(vc, entity_name)
        findings += _indexable_columns(vc, entity_name, table, indexed)
    return findings


def _index_targets(table: Table) -> list[str]:
    """The column each representable index names, in declaration order."""
    return [index.columns[0] for index in table.indexes if len(index.columns) == 1]


def _index_declarations(entity_name: str, table: Table) -> list[Finding]:
    """Refuse index structure the deployer cannot represent."""
    findings: list[Finding] = []
    for position, index in enumerate(table.indexes):
        ctx = f"{entity_name}.indexes[{position}]"
        if len(index.columns) != 1:
            findings.append(Finding(
                FindingCode.COMPOSITE_INDEX_UNSUPPORTED,
                f"{ctx}: composite index {index.columns!r} is unsupported; "
                "SharePoint deployment supports one column per DBML index.",
                location=Location(
                    Section.SCHEMA, entity=entity_name,
                    sub=f"indexes[{position}]",
                ),
            ))
            continue
        settings = {
            "name": index.name,
            "unique": index.unique or None,
            "type": index.type,
            "pk": index.pk or None,
            "note": index.note or None,
        }
        configured = {key: value for key, value in settings.items() if value is not None}
        if configured:
            findings.append(Finding(
                FindingCode.INDEX_SETTINGS_UNSUPPORTED,
                f"{ctx}: DBML index settings {configured!r} are unsupported by "
                "SharePoint. Declare a bare column index; use the column's "
                "[unique] setting when uniqueness is required.",
                location=Location(
                    Section.SCHEMA, entity=entity_name,
                    sub=f"indexes[{position}]",
                ),
            ))
    return findings


def _duplicate_indexes(
    vc: ValidationContext, entity_name: str, indexed: list[str],
) -> list[Finding]:
    """One column indexed twice, by two entries or by an entry and [unique]."""
    findings: list[Finding] = []
    for duplicate in sorted({name for name in indexed if indexed.count(name) > 1}):
        findings.append(Finding(
            FindingCode.DUPLICATE_INDEX_TARGET,
            f"{entity_name}.indexes: duplicate index target {duplicate!r}.",
            location=Location(
                Section.SCHEMA, entity=entity_name, column=duplicate, sub="index",
            ),
        ))
    # Unique fields carry an implicit SharePoint index and count toward
    # the same per-list ceiling as explicit declarations.
    unique_indexes = vc.unique_indexes_by_entity.get(entity_name, set())
    for duplicate in sorted(set(indexed) & unique_indexes):
        findings.append(Finding(
            FindingCode.INDEX_DUPLICATES_UNIQUE_COLUMN,
            f"{entity_name}.indexes: {duplicate!r} is already indexed by "
            "its column [unique] setting; remove the redundant indexes entry.",
            location=Location(
                Section.SCHEMA, entity=entity_name, column=duplicate, sub="index",
            ),
        ))
    return findings


def _index_ceiling(vc: ValidationContext, entity_name: str) -> list[Finding]:
    """The per-list index ceiling, counting the implicit indexes too."""
    effective_indexes = vc.effective_indexes(entity_name)
    unique_indexes = vc.unique_indexes_by_entity.get(entity_name, set())
    if len(effective_indexes) > MAX_LIST_INDEXES:
        # Name the implicit contributors. The old message said only
        # "(including unique columns)", which on the case this rule exists
        # for (twenty declared indexes on a lookup target, no unique
        # columns anywhere) is both unhelpful and false: the author counts
        # twenty and is told the twenty-first comes from something that is
        # not there.
        declared = vc.explicit_indexes_by_entity.get(entity_name, set())
        extra: list[str] = []
        implicit_unique = sorted(unique_indexes - declared)
        if implicit_unique:
            extra.append(
                ", ".join(repr(name) for name in implicit_unique)
                + (" from a [unique] column" if len(implicit_unique) == 1
                   else " from [unique] columns"),
            )
        display_index = vc.display_index_by_entity.get(entity_name)
        if display_index is not None and display_index not in declared | unique_indexes:
            extra.append(
                f"{display_index!r}, indexed automatically because this "
                f"list is a lookup target -- a picker cannot enumerate an "
                f"unindexed column past {LIST_VIEW_THRESHOLD:,} items",
            )
        return [Finding(
            FindingCode.INDEX_LIMIT_EXCEEDED,
            f"{entity_name}.indexes: {len(effective_indexes)} "
            f"effective indexes exceed SharePoint's limit of "
            f"{MAX_LIST_INDEXES}. "
            f"{len(declared)} declared in indexes {{ }}"
            + "".join(f", plus {item}" for item in extra)
            + ".",
            location=Location(Section.SCHEMA, entity=entity_name, sub="indexes"),
        )]
    if len(effective_indexes) >= INDEX_WARN_AT:
        # Why the warning band exists at all (the count this build can see
        # is a floor, not a total) is recorded once, beside INDEX_WARN_AT
        # in analysis/limits.py, along with the 2026-07-31 measurement.
        return [Finding(
            FindingCode.INDEX_LIMIT_APPROACHING,
            f"{entity_name}.indexes: {len(effective_indexes)} of the "
            f"{MAX_LIST_INDEXES} "
            f"available indexes are already spoken for. SharePoint also "
            f"creates indexes by itself -- opening a sorted view on an "
            f"unindexed column adds one -- and those are invisible to this "
            f"build, so leave headroom.",
            location=Location(Section.SCHEMA, entity=entity_name, sub="indexes"),
        )]
    return []


def _indexable_columns(
    vc: ValidationContext, entity_name: str, table: Table, indexed: list[str],
) -> list[Finding]:
    """Refuse an index on a column the deploy never creates or cannot index."""
    findings: list[Finding] = []
    xcols = vc.cross_site_columns(entity_name)
    rendered = rendered_columns(table, xcols)
    columns_by_name = {col.name: col for col in table.columns}
    for col_name in indexed:
        if col_name not in rendered:
            hint = (
                " (cross-site logical columns are replaced by generated "
                "companion fields and cannot be indexed from DBML)"
                if col_name in xcols
                else ""
            )
            findings.append(Finding(
                FindingCode.INDEX_COLUMN_NOT_RENDERED,
                f"{entity_name}.indexes: {col_name!r} is not a "
                f"rendered column of {entity_name}{hint}.",
                location=Location(
                    Section.SCHEMA, entity=entity_name, column=col_name, sub="index",
                ),
            ))
            continue
        column = columns_by_name.get(col_name)
        unindexable = (
            None if column is None else unsupported_index_reason(column.type)
        )
        if column is not None and is_multi_value(column.type):
            # Ahead of the generic rule rather than beside it -- both
            # would otherwise fire, since `unsupported_index_reason` is
            # arity-aware. The specific one exists for its second remedy:
            # the generic message can only say "SharePoint cannot index
            # this type", and the fix it implies is a different column,
            # while here the SAME enum without the brackets is indexable.
            # That is usually what the author wants to hear.
            #
            # Measured 2026-08-10 and read WITH ITS CONTROL: setting
            # Indexed=true on a live MultiChoice was refused ("This column
            # type is not supported for indexing") and read back false,
            # while the same run set Indexed=true on a single-value Choice
            # in the same list and it stuck. So the refusal belongs to the
            # field type and not to the probe.
            findings.append(Finding(
                FindingCode.MULTI_VALUE_INDEX_UNSUPPORTED,
                f"{entity_name}.indexes: {col_name!r} is a multi-value "
                f"column, which SharePoint refuses to index -- it is a "
                f"{MULTI_VALUE_SP_TYPE_NAME} column. Remove it from "
                f"indexes {{ }}, or declare it as a single-value "
                f"{element_type(column.type)!r} column, which can carry "
                f"an index.",
                location=Location(
                    Section.SCHEMA, entity=entity_name, column=col_name, sub="index",
                ),
            ))
        elif unindexable is not None:
            findings.append(Finding(
                FindingCode.INDEX_COLUMN_TYPE_UNINDEXABLE,
                f"{entity_name}.indexes: {col_name!r} is a "
                f"{unindexable} column, which SharePoint "
                f"cannot index.",
                location=Location(
                    Section.SCHEMA, entity=entity_name, column=col_name, sub="index",
                ),
            ))
    return findings


def _entity_keyed_sections(vc: ValidationContext) -> list[Finding]:
    """The three sections keyed by an entity name nothing else validates.

    watched_lists, polymorphic_patterns and versioning.overrides were the
    three entity-keyed sections nothing validated at all. Every other
    section names its unknown entities; these three silently dropped a
    typo, the versioning one in the fail-open direction, leaving a list
    with versioning ON when the author declared it off.
    """
    return [
        *_watched_lists(vc),
        *_polymorphic_patterns(vc),
        *_versioning_overrides(vc),
    ]


def _watched_lists(vc: ValidationContext) -> list[Finding]:
    """Each watched (entity, column) pair must be a column the deploy renders."""
    findings: list[Finding] = []
    for i, watched in enumerate(vc.bundle.mapping.watched_lists):
        watched_table = vc.tables_by_name.get(watched.entity)
        if watched_table is None:
            findings.append(Finding(
                FindingCode.UNKNOWN_ENTITY,
                f"watched_lists[{i}]: unknown entity {watched.entity!r}.",
                location=Location(Section.WATCHED_LISTS),
            ))
            continue
        watched_cols = rendered_columns(
            watched_table, vc.cross_site_columns(watched.entity),
        )
        if watched.column not in watched_cols:
            findings.append(Finding(
                FindingCode.WATCHED_COLUMN_NOT_RENDERED,
                f"watched_lists[{i}]: {watched.column!r} is not a rendered "
                f"column of {watched.entity}.",
                location=Location(Section.WATCHED_LISTS),
            ))
    return findings


def _polymorphic_patterns(vc: ValidationContext) -> list[Finding]:
    """Each pattern's field and discriminator must be columns the deploy renders."""
    findings: list[Finding] = []
    for i, pattern in enumerate(vc.bundle.mapping.polymorphic_patterns):
        pattern_table = vc.tables_by_name.get(pattern.list)
        if pattern_table is None:
            findings.append(Finding(
                FindingCode.UNKNOWN_ENTITY,
                f"polymorphic_patterns[{i}]: unknown entity {pattern.list!r}.",
                location=Location(Section.POLYMORPHIC_PATTERNS),
            ))
            continue
        pattern_cols = rendered_columns(
            pattern_table, vc.cross_site_columns(pattern.list),
        )
        for role, col_name in (("field", pattern.field), ("discriminator", pattern.discriminator)):
            if col_name not in pattern_cols:
                findings.append(Finding(
                    FindingCode.POLYMORPHIC_COLUMN_NOT_RENDERED,
                    f"polymorphic_patterns[{i}]: {role} {col_name!r} is not a "
                    f"rendered column of {pattern.list}.",
                    location=Location(Section.POLYMORPHIC_PATTERNS),
                ))
    return findings


def _versioning_overrides(vc: ValidationContext) -> list[Finding]:
    """A versioning override keyed by a name no list carries is read by nobody."""
    findings: list[Finding] = []
    for entity_name in vc.bundle.mapping.versioning_overrides:
        if entity_name not in vc.tables_by_name:
            findings.append(Finding(
                FindingCode.UNKNOWN_ENTITY,
                f"versioning.overrides: unknown entity {entity_name!r} -- the "
                f"override is read by nobody, so the real list keeps the "
                f"defaults.",
                location=Location(Section.VERSIONING, sub="overrides"),
            ))
    return findings


def _calculated_columns(vc: ValidationContext) -> list[Finding]:
    """Calculated columns (SP.FieldCalculated).

    Every calculated_* column must have a formula in the mapping, every
    mapping formula must target a calculated_* column, formulas must satisfy
    SP's constraints, and calculated columns cannot be indexed (handled here
    separately from the other unsupported index field kinds `_indexes` checks).
    """
    return [
        *_calculated_formulas(vc),
        *_formula_targets(vc),
        *_calculated_column_indexes(vc),
    ]


def _deferred_lookups(schema: Schema) -> dict[str, set[str]]:
    """Lookups the deploy plan defers to Phase 2.

    Self-references and one side of every cycle. They exist by the end of the
    run but not when Phase 1 fields are created.
    """
    deferred: dict[str, set[str]] = {}
    for entity_name, col_name in compute_phases(schema).phase2_lookups:
        deferred.setdefault(entity_name, set()).add(col_name)
    return deferred


def _calculated_formulas(vc: ValidationContext) -> list[Finding]:
    """Every calculated column's formula, against the columns it names."""
    deferred = _deferred_lookups(vc.schema)
    findings: list[Finding] = []
    for table in vc.schema.tables:
        # Per TABLE, not per calculated column: all three are pure functions
        # of the table, and rebuilding them inside the column loop was three
        # identical derivations per calculated field.
        #
        # Checked against the RENDERED columns, not the declared ones.
        # `Id int [pk, increment]` is skipped at render time and a cross-site
        # column is expanded into <col>Abbreviation and <col>SiteUrl, so both
        # are names the deploy never creates while sitting in table.columns,
        # and a formula naming either passed this very check before dying at
        # paste time.
        xcols = vc.cross_site_columns(table.name)
        rendered = rendered_columns(table, xcols)
        columns_by_name = {candidate.name: candidate for candidate in table.columns}
        for col in table.columns:
            if col.type not in CALCULATED_TYPES:
                continue
            findings += _calculated_formula(
                vc, table, col, rendered, columns_by_name, deferred,
            )
    return findings


def _calculated_formula(
    vc: ValidationContext,
    table: Table,
    col: Column,
    rendered: set[str],
    columns_by_name: dict[str, Column],
    deferred: dict[str, set[str]],
) -> list[Finding]:
    """One calculated column's formula: its presence, shape and references."""
    formula = vc.bundle.mapping.calculated_formulas.get(
        table.name, {},
    ).get(col.name)
    if formula is None:
        return [Finding(
            FindingCode.CALCULATED_COLUMN_HAS_NO_FORMULA,
            f"{table.name}.{col.name}: calculated column has no "
            f"formula -- add calculated_formulas.{table.name}."
            f"{col.name} to the mapping.",
            location=Location(
                Section.CALCULATED_FORMULAS, entity=table.name, column=col.name,
            ),
        )]
    findings: list[Finding] = []
    if not formula.startswith("="):
        findings.append(Finding(
            FindingCode.CALCULATED_FORMULA_MISSING_EQUALS,
            f"{table.name}.{col.name}: calculated formula must start "
            f"with '='.",
            location=Location(
                Section.CALCULATED_FORMULAS, entity=table.name, column=col.name,
            ),
        ))
    if len(formula) > MAX_CALCULATED_FORMULA:
        findings.append(Finding(
            FindingCode.CALCULATED_FORMULA_TOO_LONG,
            f"{table.name}.{col.name}: calculated formula is "
            f"{len(formula)} chars; SharePoint's limit is "
            f"{MAX_CALCULATED_FORMULA}.",
            location=Location(
                Section.CALCULATED_FORMULAS, entity=table.name, column=col.name,
            ),
        ))
    # SharePoint resolves [Column] references when the field is
    # CREATED and rejects the POST (HTTP 500, "The formula refers to
    # a column that does not exist") on any miss. Fail at build, not
    # at paste.
    refs = formula_column_refs(formula)
    if col.name in refs:
        findings.append(Finding(
            FindingCode.CALCULATED_FORMULA_SELF_REFERENCE,
            f"{table.name}.{col.name}: calculated formula references "
            f"itself.",
            location=Location(
                Section.CALCULATED_FORMULAS, entity=table.name, column=col.name,
            ),
        ))
    for ref in sorted(refs - rendered):
        findings.append(Finding(
            FindingCode.CALCULATED_FORMULA_UNKNOWN_COLUMN,
            f"{table.name}.{col.name}: calculated formula references "
            f"[{ref}], which is not a rendered column of "
            f"{table.name} -- SharePoint would reject the field "
            f"creation at deploy time.",
            location=Location(
                Section.CALCULATED_FORMULAS, entity=table.name, column=col.name,
            ),
        ))
    findings += _formula_operands(table, col, refs & rendered, columns_by_name)
    # A DEFERRED lookup exists by the end of the deploy but not when
    # this field is created. jsgen orders calculated fields only
    # within fields_phase1 and never consults phase2_lookups, so the
    # formula is posted in Phase 1 against a column Phase 2 has not
    # added yet. Rejected rather than deferred: moving the calculated
    # field into Phase 2 would mean a second creation path for
    # calculated columns, and the declaration has a cheap rewrite
    # (compute from the column the lookup mirrors, or drop it).
    for ref in sorted(refs & deferred.get(table.name, set())):
        findings.append(Finding(
            FindingCode.CALCULATED_FORMULA_DEFERRED_LOOKUP,
            f"{table.name}.{col.name}: calculated formula references "
            f"[{ref}], a lookup deferred to Phase 2 because its "
            f"target is created later (a self-reference or a "
            f"circular one). The calculated field is created in "
            f"Phase 1, so the column does not exist yet.",
            location=Location(
                Section.CALCULATED_FORMULAS, entity=table.name, column=col.name,
            ),
        ))
    return findings


def _formula_operands(
    table: Table,
    col: Column,
    refs: AbstractSet[str],
    columns_by_name: dict[str, Column],
) -> list[Finding]:
    """Refuse an operand type SharePoint will not accept in a formula."""
    findings: list[Finding] = []
    for ref in sorted(refs):
        operand = columns_by_name.get(ref)
        # No Column object means a generated cross-site companion
        # (<ref>Abbreviation or <ref>SiteUrl, both plain Text/Hyperlink
        # fields and both fine in a formula). The LOGICAL ref they
        # replace cannot reach here at all: `refs` is intersected with the
        # rendered columns, which drop it, so it is already reported
        # above as not a rendered column. Do not add an `in xcols`
        # test here expecting it to fire. It cannot.
        if operand is None:
            continue
        if is_multi_value(operand.type):
            # Asked by arity, because `_FORBIDDEN_CALCULATED_OPERANDS`
            # is keyed by DBML type name and `audit_event[]` is not a
            # key it could hold -- the key would have to be minted per
            # enum per schema, so a membership test looks like it
            # covers the type and does not.
            #
            # Measured 2026-08-10 on a live tenant, and the answer was
            # the same sentence the five denylisted types gave:
            # HTTP 500, "One or more column references are not
            # allowed, because the columns are defined as a data type
            # that is not supported in formulas."
            findings.append(Finding(
                FindingCode.MULTI_VALUE_OPERAND_UNSUPPORTED,
                f"{table.name}.{col.name}: calculated formula "
                f"references [{ref}], a multi-value column. "
                f"SharePoint refuses this operand when the calculated "
                f"field is created -- HTTP 500, \"the columns are "
                f"defined as a data type that is not supported in "
                f"formulas\" -- after earlier deploy phases may "
                f"already have written to the site. Compute from a "
                f"supported operand type instead "
                f"({_SUPPORTED_CALCULATED_OPERANDS}), or drop the "
                f"formula.",
                location=Location(
                    Section.CALCULATED_FORMULAS,
                    entity=table.name, column=col.name,
                ),
            ))
            continue
        forbidden_kind = (
            "lookup"
            if operand.ref is not None
            else operand.type
        )
        description = _FORBIDDEN_CALCULATED_OPERANDS.get(forbidden_kind)
        if description is None:
            continue
        findings.append(Finding(
            FindingCode.CALCULATED_FORMULA_UNSUPPORTED_OPERAND,
            f"{table.name}.{col.name}: calculated formula references "
            f"[{ref}], {description}. SharePoint refuses this operand "
            f"when the calculated field is created -- HTTP 500, \"the "
            f"columns are defined as a data type that is not supported "
            f"in formulas\" -- after earlier deploy phases may already "
            f"have written to the site. Compute from a supported "
            f"operand type instead ({_SUPPORTED_CALCULATED_OPERANDS}), "
            f"or drop the formula.",
            location=Location(
                Section.CALCULATED_FORMULAS,
                entity=table.name, column=col.name,
            ),
        ))
    return findings


def _formula_targets(vc: ValidationContext) -> list[Finding]:
    """Every declared formula must name a calculated column of its entity."""
    findings: list[Finding] = []
    for entity_name, cols in vc.bundle.mapping.calculated_formulas.items():
        calc_names = vc.calculated_by_entity.get(entity_name, set())
        for col_name in cols:
            if col_name not in calc_names:
                findings.append(Finding(
                    FindingCode.FORMULA_TARGET_NOT_CALCULATED,
                    f"calculated_formulas[{entity_name}]: {col_name!r} is not "
                    f"a calculated column of {entity_name} -- its DBML type "
                    f"must be one of {CALCULATED_TYPE_LIST}.",
                    location=Location(
                        Section.CALCULATED_FORMULAS, entity=entity_name,
                    ),
                ))
        findings += _formula_cycle(entity_name, cols, calc_names)
    return findings


def _formula_cycle(
    entity_name: str, cols: dict[str, str], calc_names: set[str],
) -> list[Finding]:
    """Refuse mutually dependent calculated columns.

    Calc-on-calc chains are provisioned in dependency order by jsgen;
    a cycle has no valid creation order (each field's formula would
    reference a not-yet-existing column).
    """
    remaining = {
        name: (formula_column_refs(f) & calc_names) - {name}
        for name, f in cols.items()
        if name in calc_names
    }
    while remaining:
        ready = [n for n, deps in remaining.items() if not deps & remaining.keys()]
        if not ready:
            return [Finding(
                FindingCode.CALCULATED_FORMULA_CYCLE,
                f"calculated_formulas[{entity_name}]: circular reference "
                f"among {sorted(remaining)} -- no creation order can "
                f"satisfy mutually dependent calculated columns.",
                location=Location(
                    Section.CALCULATED_FORMULAS, entity=entity_name,
                ),
            )]
        for name in ready:
            del remaining[name]
    return []


def _calculated_column_indexes(vc: ValidationContext) -> list[Finding]:
    """SharePoint cannot index a calculated column, however it was declared."""
    findings: list[Finding] = []
    for table in vc.schema.tables:
        calc_names = vc.calculated_by_entity.get(table.name, set())
        for index in table.indexes:
            if len(index.columns) != 1:
                continue
            col_name = index.columns[0]
            if col_name in calc_names:
                findings.append(Finding(
                    FindingCode.INDEX_ON_CALCULATED_COLUMN,
                    f"{table.name}.indexes: {col_name!r} is a "
                    f"calculated column -- SharePoint cannot index calculated "
                    f"columns.",
                    location=Location(
                        Section.SCHEMA,
                        entity=table.name, column=col_name, sub="index",
                    ),
                ))
    return findings
