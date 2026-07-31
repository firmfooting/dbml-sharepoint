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
from dbml_sharepoint.analysis.typemap import (
    NUMERIC_ONLY_TOTALS,
    UNSUPPORTED_INDEX_TYPES,
)
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
#
# TWO citations, and keep both. The support article carries the supported-column
# table that makes Person a lookup field. The schema reference carries the same
# threshold rule attached to the `Indexed` attribute itself, which is the
# property the deployer writes — so it is the one a reader checking THIS code
# against the platform contract will want. A review of this file removed it as
# "a schema page that says nothing about thresholds"; that was wrong, the Note
# under `Indexed` says exactly this, and it went back in.
# https://support.microsoft.com/en-us/office/add-an-index-to-a-sharepoint-column-f3f00554-b7dc-44d1-a2ed-d477eac463b0
# https://learn.microsoft.com/sharepoint/dev/schema/field-element-field
#
# THAT RULE IS NOT FOLLOWED HERE: it is measured, and it does not hold. This is
# the only place in this project where a Microsoft-documented statement is set
# aside, so the evidence is set out in full and reinstating it is one line —
# put "person" back in the frozenset and restore the branch in check().
#
# MEASURED 2026-07-31 AT ODDS WITH THAT RULE, on the shape this check governs.
# At 6,000 items, with both controls valid in the same run — indexed Text
# comparison served, unindexed twin of identical selectivity refused
# SPQueryThrottledException — an indexed Person and an indexed Lookup filtered
# to 60 of 6,000 were SERVED across seven query shapes: OData; CAML in the
# LookupId form; CAML in the projected-value form; and CAML naming the lookup
# column in <ViewFields>, which is what a real view renders.
#
# The last pair is the one that counts, and it is self-verified: the probe reads
# the returned rows' keys back and records `PROJECTED: Title=Title,
# Parent=Parent`. So the JOIN was paid for and the query was still served.
# Without that readback the row is unreadable — RenderListDataAsStream sends a
# standard field preamble whatever is asked for, so ViewFields being silently
# ignored looks exactly like a join that succeeded.
#
# THE APPARENT COUNTER-EXAMPLE IS NOT ONE. Adding `Parent` to an All Items view
# of the same fixture does fail — "The number of items in the list exceeds the
# list view threshold, which is 5000 items." That view has NO selective filter,
# so the join runs across all 6,000 rows. No index on any column averts that,
# lookup or otherwise. The two observations agree: the index makes the FILTER
# selective, and the join is then cheap because it runs over 60 rows.
#
# THE TARGET'S SIZE DOES NOT RESCUE THE RULE EITHER. The projecting query is
# measured at two target sizes, because a join into a one-item list is the
# cheapest that exists and proves nothing on its own. With 6,500 items in the
# TARGET and 6,000 in the source, it is served, 60 of 60.
#
# SCOPE, and it is the usual scope: one tenant, one day, one selectivity — 60 of
# 6,000, which is 1%. A less selective filter is untested and Microsoft's claim
# is general, so an indexed lookup filter is safe at high selectivity and
# unmeasured below it.
#
# A LARGE LOOKUP TARGET IS STILL A REAL PROBLEM — just not this check's. With
# the target list past 5,000 the NEW-ITEM FORM breaks: the lookup picker refuses
# with "This is a lookup column that displays data from another list that
# currently exceeds the List View Threshold defined by the administrator
# (5000)." Views read the column fine; nobody can set it. That is a form and
# column concern, not a view filter concern, and this check says nothing about
# it. A lookup into a large list is not safe; it is safe to READ in a view.
# Whatever warns about the form should cite the same fixture.
_LOOKUP_FIELD_TYPES: frozenset[str] = frozenset()

# SYSTEM_COLUMNS (ID, Created, Modified, Author, Editor) are dropped from this
# check entirely, and there is no companion "natively indexed" set to pair with
# them — that set would be unreachable, because the names are gone before any
# intersection runs.
#
# The reason is the DBML side, not the SharePoint side, and that matters: they
# are filterable but NOT declarable, so no `indexes` entry can ever name one.
# `indexes { Created }` is rejected by the DBML parser itself, a system column
# not being a DBML column. Warning about any of the five would therefore name a
# remedy nobody can carry out, whatever SharePoint does internally.
#
# Which is fortunate, because what SharePoint does internally is NOT
# established for any of the five — INCLUDING ID. "SharePoint indexes ID
# natively" is repeated widely and by this repository (see the comment in
# validator._rendered_columns), and Microsoft documents it nowhere: not in the
# index article, not in the large-list article, and the protocol spec defines
# tp_Id as a column without enumerating the table's indexes.
#
# test/manual/native-index-probe.js was RUN on 2026-07-30 and established
# NOTHING. Its control failed: SP.Field.Indexed — documented as "TRUE if the
# column is indexed for use in view filters" — read FALSE for ID itself on 7 of
# 7 lists. Either that property reports only registered list-column indexes and
# whatever serves ID sits outside that model, or ID carries no such index. The
# probe cannot separate those and neither can the documentation, so this comment
# will not pick one. The behavioural half of the probe needs a list past the
# threshold, which the site did not have.
#
# None of it changes the exclusion, because the exclusion rests on the DBML
# side. That is why it is safe to leave standing while the question stays open.
#
# test/manual/threshold-index-probe.js is the fixture that can answer this. It
# provisions a list past the threshold and filters Created, Modified, Author and
# Editor directly — a behavioural answer, where a flag read is what failed. Note
# what it will NOT settle: those four are set by the loader on every row, so no
# selective filter over them exists, and a refusal there is attributable to
# result-set size rather than to indexing. Only a SERVED would be informative.
#
# Measured 2026-07-31 at 6,000 items, and STILL NOT ESTABLISHED — exactly as
# that probe warns it cannot be. All four were refused with HTTP 500
# SPQueryThrottledException, which is uninformative here: the loader owns every
# row, so each filter matches the whole list and breaches on result-set size
# alone. Only a SERVED would have said anything about indexing. Answering this
# needs a fixture whose rows are created by more than one principal over more
# than one interval — a different fixture, not a longer run.
#
# The exclusion rests on the DBML side, so this check is unaffected either way.

# FILTER ORDER DOES NOT DECIDE IT, measured 2026-07-31 at 6,000 items. The
# fixture's unindexed column carries byte-identical data to its indexed twin, so
# `indexed='Z' AND unindexed='Z'` matches exactly the rows either matches alone
# — the AND restricts nothing, and the pair differs only in which condition is
# written first. Both orderings were served, 60 of 60.
#
# The unindexed condition ALONE is refused with SPQueryThrottledException in the
# same run. So an indexed condition anywhere in an AND rescues one that would
# breach on its own, whichever is authored first: SharePoint picks the index, it
# does not take the first column and stop. Widely-repeated advice to "put the
# indexed column first" is not describing this platform's behaviour.
#
# What that does NOT license: the AND here is degenerate, both conditions
# matching the same 60 rows. An AND whose conditions select different sets, or
# an OR, is unmeasured — OR especially, since it cannot narrow to either index.
#
# NEITHER A CALCULATED NOR A MULTI-LINE TEXT COLUMN CAN CARRY AN INDEX. Both
# were created and MERGEd with Indexed=true; the request was accepted and the
# flag read back false. So no remedy anywhere in this file may name one, and a
# status code alone would have reported both as indexed.

# Operators that test only for presence. Microsoft's threshold guidance is
# written for comparison filters; whether an index serves a CAML <IsNull> is
# unverified here. A null-only filter therefore still gets the exposure
# warning — the truncation risk is real either way — but NOT the "add an
# index" remedy, which this project cannot yet claim would help.
#
# test/manual/native-index-probe.js asks this too and, as of its 2026-07-30
# run, has not answered it: the test needs a list past the threshold, and the
# site it ran on topped out at 21 items. Still open.
#
# test/manual/threshold-index-probe.js builds the list that run lacked. It asks
# CAML rather than only OData, because a view renders CAML and `eq null` is not
# in Microsoft's documented operator list for the REST service at all.
#
# ONE CAVEAT ON THE PAIRING, stated because an earlier version of this comment
# overclaimed it: CMPCAM compares an indexed TEXT column and NULCAM tests an
# indexed DATETIME one, so the two differ in field type as well as in operator.
# Both match the same 60 of 6,000, so selectivity is held constant, but a
# divergence between them alone could not distinguish IsNull behaviour from
# field-type behaviour.
#
# It does not have to. The conclusion below rests on NNIDX and NNUNI, which are
# two DateTime columns holding identical values on the same rows and differing
# ONLY in the index — and on NULIDX, the same presence test over the same
# column on the OData path. Making CMPCAM and NULCAM a true one-variable pair
# needs an equality population on the DateTime column, which is a generator
# change rather than a probe one.
#
# ANSWERED 2026-07-31, revision 1799a1e8, at 6,000 items on one site: YES, a
# CAML <IsNull> on an INDEXED DateTime column IS served past the threshold.
# NULCAM returned HTTP 200 with exactly its 60 expected rows, while the negative
# control — an UNINDEXED Text comparison of identical selectivity, 60 of 6,000 —
# was refused HTTP 500 SPQueryThrottledException, "the attempted operation is
# prohibited because it exceeds the list view threshold", and the positive
# control on an indexed column was served. Controls valid in both directions, so
# the null test is not riding on a threshold that failed to engage. OData
# `ClosedAt eq null` was served at 60 rows too — a second code path agreeing.
#
# The remedy below therefore recommends an index for a null-only filter.
#
# THE INDEX IS NECESSARY, NOT MERELY SUFFICIENT, and the way it fails without
# one is the reason this whole check exists. Measured with a matched pair: two
# DateTime columns holding identical values on the same 60 of 6,000 rows,
# written in a single MERGE per row so they cannot diverge, differing ONLY in
# the index. At 6,000 items, a CAML <IsNotNull> over each:
#
#   INDEXED    HTTP 200, 60 rows — correct
#   UNINDEXED  HTTP 200, 50 rows — WRONG, AND NOT AN ERROR
#
# The unindexed column was not refused. It returned a partial answer, with a
# success status and nothing to say it was partial. A separate readback through
# an indexed filter confirmed all 60 rows really do hold both values, so this is
# SharePoint truncating rather than data that was never there.
#
# That is the silent truncation described at the top of this block, caught in
# the act — and note it truncated to 50, not to the documented 1,250 fallback,
# so that figure is a ceiling rather than a prediction. A view built this way
# does not break. It quietly shows the wrong rows, forever, and nothing in a
# build or a deploy can see it.
#
# Recorded because it contradicts the paragraph above: OData `eq null` is absent
# from Microsoft's documented operator list for the REST service, and the only
# Microsoft-hosted statement found says that service does not support filtering
# on null. It does here, under and over the threshold. That reasoning described
# the documentation rather than the behaviour.
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
                    # An index on a Lookup or Person column counts here, same
                    # as any other: measured at 6,000 items with the column
                    # projected and the join verified, the query is served. See
                    # _LOOKUP_FIELD_TYPES.
                    #
                    # entity_lookups is read only by the totals check below,
                    # which means it in the DBML sense.
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
                    # An index is only a remedy for a column that can carry one.
                    # SharePoint refuses one on a Note or Hyperlink field and
                    # cannot put one on a Calculated column at all, and
                    # _structure.py errors on exactly those — so recommending an
                    # index there prescribes a change that fails the build. A
                    # CAML null test over such a column is otherwise legal, so
                    # the exposure is real and only the remedy has to change.
                    indexable = {
                        name for name in filtered
                        if types_by_col.get(name) not in UNSUPPORTED_INDEX_TYPES
                        and name not in vc.calculated_by_entity.get(entity_name, set())
                    }
                    if not indexed_filters:
                        remedy = (
                            (
                                "Add a bare DBML index to the tested column. "
                                "Measured on a matched pair at 6,000 items, the "
                                "indexed column returned all 60 expected rows and "
                                "the unindexed one returned 50 of 60 with HTTP 200 "
                                "and no error — the view does not break, it "
                                "quietly shows the wrong rows. Selectivity still "
                                "matters: a blank that most rows share is not a "
                                "selective filter."
                                if indexable else
                                "No index is possible here: SharePoint cannot "
                                "index a Multiple lines of text, Hyperlink or "
                                "Calculated column, so the only remedies are a "
                                "different filter column or a list that will "
                                "stay small. Measured on a matched pair at 6,000 "
                                "items, an unindexed presence test returned 50 of "
                                "60 rows with HTTP 200 and no error."
                            )
                            if null_only else
                            "Add a bare DBML index to a selective filter column, "
                            "or accept the risk for a list that will stay small. "
                            "One indexed condition is enough and its position in "
                            "the filter does not matter, but selectivity does: "
                            "an index over a value most rows share will not save "
                            "the query."
                        )
                        findings.append(Finding(
                            "warning",
                            f"{ctx}.where: filtered columns ({names}) have no "
                            f"effective index. {exposure}. {remedy}",
                        ))
                    # One branch only, deliberately. A view whose sole indexed
                    # filter column is a Lookup or a Person needs no warning: an
                    # index on either is served past the threshold. See
                    # _LOOKUP_FIELD_TYPES for the measurement.
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
