# src/dbml_sharepoint/analysis/checks/_views.py
"""Field sets and declared views."""

from dbml_sharepoint.analysis.checks._context import ValidationContext
from dbml_sharepoint.analysis.conditions import (
    CAML,
    SYSTEM_COLUMN_TYPES,
    condition_fields,
    effective_column_types,
    leaves,
    validate_condition,
)
from dbml_sharepoint.analysis.typemap import NUMERIC_ONLY_TOTALS
from dbml_sharepoint.analysis.validator import (
    SYSTEM_COLUMNS,
    Finding,
    _rendered_columns,
    formatter_field_refs,
)
from dbml_sharepoint.model.mapping_loader import view_url_slug

# What SharePoint can add up. A calculated_number is included deliberately:
# three of the five columns declared totals exist for in this library are
# calculated day-counts, and the `string;#` prefix that complicates
# calculated text is a COLUMN-formatting concern that never reaches a
# view's Aggregations property.
_NUMERIC_FOR_TOTALS = frozenset({"int", "number", "calculated_number"})

# Columns SharePoint will not add up, subtract or order, whatever their
# declared DBML type says. Separated from the numeric rule so the message
# can say "not at all" rather than pointing at `count`.
#
# `count` is NOT blocked on these: it counts rows, and SharePoint offers
# Count on a person or hyperlink column.
_NON_ARITHMETIC = frozenset({"person", "richtext", "longtext", "hyperlink"})

# SharePoint Online's list view threshold is 5,000 items. Microsoft states it
# CANNOT be changed for SharePoint, and that the effective number "is not
# always 5,000" because it varies with the site and database activity — so
# 5,000 is the documented figure, not a precise cutoff.
#
# The consequence is worse than an error, which is why this is worth warning
# about at all: with Metadata Navigation and Filtering (on by default) a query
# no index can serve falls back to returning up to 1,250 of the NEWEST items,
# and may return none. A view that silently shows a truncated answer is the
# failure this check exists to prevent.
# https://support.microsoft.com/en-us/office/manage-large-lists-and-libraries-b8588dae-9387-48c2-9248-c24122f07c59
_LIST_VIEW_THRESHOLD = 5_000
_FALLBACK_ROW_COUNT = 1_250

# Microsoft, verbatim: "Although you can index a lookup column to improve
# performance, using an indexed lookup column to prevent exceeding the List
# View Threshold doesn't work. Use another type of column as the primary or
# secondary index."
#
# The same article's supported-column table annotates "Person or Group (single
# value)" and "Managed Metadata" as lookup fields, and its note says to consult
# that table to decide what counts as one. So a PERSON column is a lookup field
# for this purpose even though its DBML declaration looks nothing like a `ref`,
# and indexing it does not avert a threshold breach either. Read narrowly —
# `col.ref is not None` only — this check would score an indexed Person filter
# as safe when Microsoft says it is not.
# https://support.microsoft.com/en-us/office/add-an-index-to-a-sharepoint-column-f3f00554-b7dc-44d1-a2ed-d477eac463b0
_LOOKUP_FIELD_TYPES = frozenset({"person"})

# SYSTEM_COLUMNS (ID, Created, Modified, Author, Editor) are dropped from this
# check entirely, and there is no companion "natively indexed" set to pair with
# them — that set would be unreachable, because the names are gone before any
# intersection runs.
#
# They are filterable but NOT declarable, so no `indexes` entry can ever name
# one: `indexes { Created }` is rejected by the DBML parser itself, a system
# column not being a DBML column. Warning about them would name a remedy
# nobody can carry out. ID is indexed by the platform and would need excluding
# anyway; for the other four it is NOT established either way — nothing here
# has measured it and Microsoft does not document it, so silence beats a guess
# in either direction. test/manual/native-index-probe.js settles it.

# Operators that test only for presence. Microsoft's threshold guidance is
# written for comparison filters; whether an index serves a CAML <IsNull> is
# unverified here. A null-only filter therefore still gets the exposure
# warning — the truncation risk is real either way — but NOT the "add an
# index" remedy, which this project cannot yet claim would help.
# test/manual/native-index-probe.js settles this too.
_NULL_TEST_OPS = frozenset({"is_null", "is_not_null"})


def check(vc: ValidationContext) -> list[Finding]:
    bundle = vc.bundle
    tables_by_name = vc.tables_by_name
    cross_site_by_entity = vc.cross_site_by_entity
    findings: list[Finding] = []
    # Field sets: named column lists a view's `fields` pulls in with
    # "@setname". The loader expands them into ViewDef.fields before
    # anything downstream reads a view, so what is checked here is the
    # DECLARATION — otherwise a bad set surfaces as a confusing error about
    # the expanded columns, or (for an unresolved @name) as a CAML field
    # reference SharePoint rejects live in the browser.
    for entity_name, entity_sets in bundle.mapping.field_sets.items():
        set_table = tables_by_name.get(entity_name)
        if set_table is None or entity_name not in bundle.mapping.entities:
            findings.append(Finding(
                "error", f"field_sets[{entity_name}]: unknown entity.",
            ))
            continue
        set_rendered = (
            _rendered_columns(set_table, cross_site_by_entity.get(entity_name, set()))
            | {"Title"} | SYSTEM_COLUMNS
        )
        # A set is "referenced" if some view on this entity actually
        # expanded it — ViewDef.expanded_sets is the loader's record of
        # that, since the "@name" tokens themselves are gone by the time we
        # see fields.
        referenced_sets = {
            name
            for view in bundle.mapping.views.get(entity_name, [])
            for name in view.expanded_sets
        }
        set_retired = bundle.mapping.retired_columns.get(entity_name, {})
        for set_name, set_columns in entity_sets.items():
            ctx = f"field_sets[{entity_name}].{set_name}"
            if "@" in set_name:
                findings.append(Finding(
                    "error",
                    f"{ctx}: a field set name cannot contain '@' — that is "
                    f"the marker a view's fields uses to reference a set.",
                ))
            if not set_columns:
                findings.append(Finding(
                    "error",
                    f"{ctx}: field set is empty; declare at least one column "
                    f"or remove the set.",
                ))
            for col_name in set_columns:
                if col_name not in set_rendered:
                    findings.append(Finding(
                        "error",
                        f"{ctx}: references {col_name!r}, which is not a "
                        f"rendered column of {entity_name}.",
                    ))
                elif col_name in set_retired:
                    # Expansion runs first, so the strip is recorded against
                    # each VIEW; without this the only report points at a
                    # view whose fields no longer mention the column, and
                    # the set is where the author fixes it.
                    findings.append(Finding(
                        "warning",
                        f"{ctx}: {col_name!r} is retired; retirement stripped "
                        f"it from every view that expands this set, and the "
                        f"build continues.",
                    ))
            if set_name not in referenced_sets:
                findings.append(Finding(
                    "warning",
                    f"{ctx}: declared but no {entity_name} view references "
                    f"'@{set_name}'.",
                ))

    # Declared views: everything checkable at build time IS checked at build
    # time — a deploy-time CAML rejection in the browser console is exactly
    # the failure class this tool exists to prevent.
    for entity_name, views in bundle.mapping.views.items():
        view_table = tables_by_name.get(entity_name)
        if view_table is None or entity_name not in bundle.mapping.entities:
            findings.append(Finding(
                "error", f"views[{entity_name}]: unknown entity.",
            ))
            continue
        xcols = cross_site_by_entity.get(entity_name, set())
        # The built-in Title always exists on a provisioned list, declared or not.
        view_rendered = _rendered_columns(view_table, xcols) | {"Title"} | SYSTEM_COLUMNS
        # The type map must cover everything view_rendered admits, or a
        # column that IS filterable reports "no declared type" and aborts the
        # build. Two are rendered without being DBML columns: the built-in
        # Title, which every provisioned list has, and the Choice+URL pair a
        # cross-site reference expands into. Both are text.
        types_by_col = effective_column_types(
            {c.name: c.type for c in view_table.columns}, xcols,
        )
        # Entity-level: the totals check needs it too, and a lookup's DBML
        # type is `int`, so nothing downstream can infer it from the type.
        entity_lookups = {c.name for c in view_table.columns if c.ref is not None}
        titles = [v.title for v in views]
        if "All Items" in titles:
            findings.append(Finding(
                "error",
                f"views[{entity_name}]: 'All Items' is generated with every "
                f"rendered column and no filter; remove the declaration "
                f"instead of overriding that recovery view.",
            ))
        # Case-insensitively: SharePoint resolves views/getbytitle that way
        # and will not hold two views on one list differing only in case, so
        # the second create collides mid-deploy.
        folded: dict[str, list[str]] = {}
        for title in titles:
            folded.setdefault(title.casefold(), []).append(title)
        for variants in sorted(folded.values(), key=lambda v: v[0]):
            if len(variants) < 2:
                continue
            distinct = sorted(set(variants))
            findings.append(Finding(
                "error",
                f"views[{entity_name}]: duplicate view title {distinct[0]!r}."
                + (f" {distinct[1]!r} differs only in case, and SharePoint "
                   f"treats them as one view." if len(distinct) > 1 else ""),
            ))
        previous_claims: dict[str, list[str]] = {}
        for view in views:
            for previous in view.renamed_from:
                ctx = f"views[{entity_name}].{view.title}.renamed_from"
                if not previous.strip():
                    findings.append(Finding(
                        "error", f"{ctx}: previous titles cannot be empty.",
                    ))
                if previous == view.title:
                    findings.append(Finding(
                        "error",
                        f"{ctx}: {previous!r} is the view's own title, not a "
                        f"previous title.",
                    ))
                if previous == "All Items":
                    findings.append(Finding(
                        "error",
                        f"{ctx}: 'All Items' is reserved for the generated "
                        f"recovery view and cannot be adopted.",
                    ))
                if previous in titles and previous != view.title:
                    findings.append(Finding(
                        "error",
                        f"{ctx}: {previous!r} is another declared view's "
                        f"current title.",
                    ))
                previous_claims.setdefault(previous, []).append(view.title)
        for previous, claimants in previous_claims.items():
            if len(claimants) > 1:
                findings.append(Finding(
                    "error",
                    f"views[{entity_name}]: previous title {previous!r} is "
                    f"claimed by more than one view ({', '.join(claimants)}).",
                ))
        defaults = [v.title for v in views if v.default]
        if len(defaults) > 1:
            findings.append(Finding(
                "error",
                f"views[{entity_name}]: more than one default view "
                f"({', '.join(defaults)}); SharePoint lists have exactly one.",
            ))
        # Views are created under a URL slug derived from the title (the
        # .aspx name is fixed at creation); two titles collapsing to one
        # slug would fight over the same page.
        slugs_seen: dict[str, str] = {"allitems": "All Items"}
        for view in views:
            slug = view_url_slug(view.title)
            if not slug:
                findings.append(Finding(
                    "error",
                    f"views[{entity_name}].{view.title}: title yields an "
                    f"empty URL slug; include at least one letter or digit.",
                ))
            elif slug.casefold() in slugs_seen:
                findings.append(Finding(
                    "error",
                    f"views[{entity_name}]: titles {slugs_seen[slug.casefold()]!r} and "
                    f"{view.title!r} share the URL slug {slug}.aspx; retitle "
                    f"one so the view pages differ.",
                ))
            else:
                slugs_seen[slug.casefold()] = view.title
        for view in views:
            ctx = f"views[{entity_name}].{view.title}"
            # Any "@name" still in fields is one the loader could not
            # resolve; report it as the field-set reference it is rather
            # than as a column that does not exist.
            findings.extend(
                Finding(
                    "error",
                    f"{ctx}: fields references field set {name!r}, but "
                    f"{entity_name} declares no field set named {name[1:]!r}.",
                )
                for name in view.fields
                if name.startswith("@")
            )
            referenced = (
                [("fields", name) for name in view.fields if not name.startswith("@")]
                + [("sort", sort.field) for sort in view.sort]
                + [
                    ("group_by", name)
                    for name in (view.group_by.fields if view.group_by else [])
                ]
            )
            for part, name in referenced:
                if name not in view_rendered:
                    findings.append(Finding(
                        "error",
                        f"{ctx}: {part} references {name!r}, which is not a "
                        f"rendered column of {entity_name}.",
                    ))
            if view.where is not None:
                # The shared grammar owns operator, operand and capability
                # rules for every conditional surface; duplicating them here
                # is how the two would drift.
                lookup_cols = entity_lookups
                findings.extend(
                    Finding("error", message)
                    for message in validate_condition(
                        view.where,
                        target=CAML,
                        rendered=view_rendered,
                        types={**SYSTEM_COLUMN_TYPES, **types_by_col},
                        lookups=lookup_cols,
                        context=f"{ctx}.where",
                    )
                )
                # System columns are dropped before anything is decided. They
                # are filterable but not declarable, so they can neither carry
                # a DBML index nor be reported as missing one.
                filtered = condition_fields(view.where) - SYSTEM_COLUMNS
                # Do not layer an index warning on top of an unknown-field
                # error. Once every field resolves, assess the whole
                # dependency set without pretending to understand AND/OR
                # selectivity in this first pass.
                if filtered and filtered <= view_rendered:
                    indexed_filters = filtered & vc.effective_indexes(entity_name)
                    # Wider than entity_lookups on purpose — see
                    # _LOOKUP_FIELD_TYPES. entity_lookups stays as it is
                    # because the totals check below means the DBML sense.
                    lookup_fields = entity_lookups | {
                        name for name in filtered
                        if types_by_col.get(name) in _LOOKUP_FIELD_TYPES
                    }
                    useful_indexes = indexed_filters - lookup_fields
                    # A filter that only tests presence gets the exposure
                    # warning without the index remedy.
                    compared = {
                        leaf.field for leaf in leaves(view.where)
                        if leaf.op not in _NULL_TEST_OPS
                    }
                    null_only = not (filtered & compared)
                    names = ", ".join(sorted(filtered))
                    exposure = (
                        f"SharePoint Online's list view threshold is "
                        f"{_LIST_VIEW_THRESHOLD:,} items and cannot be raised; "
                        f"past it SharePoint may return only the newest "
                        f"{_FALLBACK_ROW_COUNT:,} items, or none, rather than "
                        f"reporting an error"
                    )
                    if not indexed_filters:
                        remedy = (
                            "Whether an index helps a null test is unverified by "
                            "this project, so none is recommended here — either "
                            "add a selective compared column to the filter, or "
                            "accept the risk for a list that will stay small."
                            if null_only else
                            "Add a bare DBML index to a selective filter column, "
                            "or accept the risk for a list that will stay small. "
                            "An index is necessary but may not be sufficient, "
                            "because SharePoint also considers filter order, "
                            "selectivity and condition shape."
                        )
                        findings.append(Finding(
                            "warning",
                            f"{ctx}.where: filtered columns ({names}) have no "
                            f"effective index. {exposure}. {remedy}",
                        ))
                    elif not useful_indexes:
                        lookup_names = ", ".join(sorted(indexed_filters))
                        findings.append(Finding(
                            "warning",
                            f"{ctx}.where: the only indexed filter column(s), "
                            f"{lookup_names}, are Lookup or Person columns — "
                            f"Microsoft classifies both as lookup fields and "
                            f"documents that indexing one does not prevent "
                            f"exceeding the list view threshold. {exposure}. "
                            f"Index a selective Text, Number, Choice or Date "
                            f"filter column instead.",
                        ))
            # 5000 as a literal, deliberately NOT _LIST_VIEW_THRESHOLD. This is
            # the per-view page-size ceiling, a different limit that happens to
            # share the value; folding them into one constant would tie a view
            # setting to a list-size threshold they have no reason to track.
            if view.row_limit is not None and not 1 <= view.row_limit <= 5000:
                findings.append(Finding(
                    "error", f"{ctx}: row_limit must be between 1 and 5000.",
                ))
            if view.formatting is not None:
                refs = formatter_field_refs(view.formatting)
                for ref in sorted(refs - view_rendered):
                    findings.append(Finding(
                        "error",
                        f"{ctx}: formatting references [${ref}], which is "
                        f"not a rendered column of {entity_name}.",
                    ))
                # A real column the VIEW does not display is the worse case,
                # including built-in system columns such as Created/Author:
                # SharePoint resolves a view formatter's references against
                # the columns that view renders, so the reference yields
                # nothing and the format silently never fires. The build
                # exits 0, the deploy reports the formatter verified, and
                # the only symptom is a row wash nobody sees.
                shown = set(view.fields)
                for ref in sorted((refs & view_rendered) - shown):
                    findings.append(Finding(
                        "error",
                        f"{ctx}: formatting references [${ref}], which this "
                        f"view does not display — a view formatter can only "
                        f"read columns in its own 'fields', so the format "
                        f"would never fire. Add {ref} to fields, or drop the "
                        f"reference.",
                    ))
            # Widths bind to columns the view actually shows; a width on an
            # unshown column is dead config the deployer would emit and SP
            # would silently ignore.
            for width_col, width_px in view.widths.items():
                if width_col not in view.fields:
                    findings.append(Finding(
                        "error",
                        f"{ctx}: widths references {width_col!r}, which is "
                        f"not one of this view's fields.",
                    ))
                if not 16 <= width_px <= 2000:
                    findings.append(Finding(
                        "error",
                        f"{ctx}: widths[{width_col}] must be between 16 and "
                        f"2000 pixels (got {width_px}).",
                    ))
            # Totals bind to a displayed column, like widths — SharePoint
            # accepts an Aggregations entry naming a field the view has no
            # column for, and then renders no figure.
            for total_col, func in view.totals.items():
                if total_col not in view.fields:
                    findings.append(Finding(
                        "error",
                        f"{ctx}: totals references {total_col!r}, which is not one "
                        f"of this view's fields — SharePoint has no column to put "
                        f"the figure under, so no total appears.",
                    ))
                    continue
                # SYSTEM_COLUMN_TYPES for the same reason the `where` check
                # merges it: ID, Created, Modified, Author and Editor are
                # renderable in a view without being DBML columns, and
                # without their types they report as the empty string —
                # which made Author escape the arithmetic rule and produced
                # a message reading "is ." on every system column.
                col_type = {**SYSTEM_COLUMN_TYPES, **types_by_col}.get(total_col, "")
                if func != "count" and total_col in entity_lookups:
                    # A lookup is int-typed in DBML, so without this it
                    # walks straight through the numeric rule. SharePoint
                    # offers only Count on one; a Sum FieldRef round-trips
                    # and renders nothing.
                    findings.append(Finding(
                        "error",
                        f"{ctx}: totals[{total_col}] = {func!r} on a lookup column. "
                        f"SharePoint can only count a lookup — its stored value is a "
                        f"row id, not a quantity. Use 'count'.",
                    ))
                elif func != "count" and col_type in _NON_ARITHMETIC:
                    findings.append(Finding(
                        "error",
                        f"{ctx}: totals[{total_col}] = {func!r} cannot be computed on "
                        f"a {col_type} column. Use 'count', which counts rows.",
                    ))
                elif func in NUMERIC_ONLY_TOTALS and col_type not in _NUMERIC_FOR_TOTALS:
                    findings.append(Finding(
                        "error",
                        f"{ctx}: totals[{total_col}] = {func!r} needs a numeric "
                        f"column; {total_col!r} is {col_type or 'of unknown type'}. "
                        f"Use 'count', which counts rows rather than adding values.",
                    ))

    return findings
