# src/dbml_sharepoint/analysis/checks/_views.py
"""Field sets and declared views."""

from dbml_sharepoint.analysis.checks._context import ValidationContext
from dbml_sharepoint.analysis.conditions import (
    CAML,
    SYSTEM_COLUMN_TYPES,
    effective_column_types,
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

# Columns with no aggregation semantics in any function, including count.
# Separated from the numeric rule so the message can say "not at all"
# rather than pointing at `count` as an alternative that is also useless
# here.
_UNAGGREGATABLE = frozenset({"person", "richtext", "longtext", "hyperlink"})


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
        titles = [v.title for v in views]
        if "All Items" in titles:
            findings.append(Finding(
                "error",
                f"views[{entity_name}]: 'All Items' is generated with every "
                f"rendered column and no filter; remove the declaration "
                f"instead of overriding that recovery view.",
            ))
        for title in sorted({t for t in titles if titles.count(t) > 1}):
            findings.append(Finding(
                "error", f"views[{entity_name}]: duplicate view title {title!r}.",
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
                lookup_cols = {c.name for c in view_table.columns if c.ref is not None}
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
                col_type = types_by_col.get(total_col, "")
                if col_type in _UNAGGREGATABLE:
                    findings.append(Finding(
                        "error",
                        f"{ctx}: totals[{total_col}] cannot be aggregated at all — "
                        f"{total_col!r} is a {col_type} column.",
                    ))
                elif func in NUMERIC_ONLY_TOTALS and col_type not in _NUMERIC_FOR_TOTALS:
                    findings.append(Finding(
                        "error",
                        f"{ctx}: totals[{total_col}] = {func!r} needs a numeric "
                        f"column; {total_col!r} is {col_type}. Use 'count', which "
                        f"counts rows rather than adding values.",
                    ))
            # group_by is already checked against the entity's rendered
            # columns above, which is the weaker question. SharePoint groups
            # by a column the view does not display and then has nothing to
            # label the group headers with, so the view renders groups
            # nobody can read. Guarded on view_rendered so an unknown column
            # reports once, as "not a rendered column", rather than twice.
            for group_col in (view.group_by.fields if view.group_by else []):
                if group_col in view_rendered and group_col not in view.fields:
                    findings.append(Finding(
                        "error",
                        f"{ctx}: group_by references {group_col!r}, which is not "
                        f"one of this view's fields — SharePoint groups by the "
                        f"column and then cannot display it, so the group headers "
                        f"read as unlabelled. Add {group_col} to fields.",
                    ))

    return findings
