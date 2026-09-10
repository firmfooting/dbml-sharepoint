# src/dbml_sharepoint/generators/report_m.py
"""The Power Query side of the reporting pack.

One M query per list, ``OData.Feed`` against the list's REST endpoint, with
lookup and person columns expanded to a join key plus display column and
column types applied from the deployer's own typemap; the ``_Users``
dimension; and the three loadable tables (``_DataDictionary``,
``_ModelInfo`` and the ``_UserAddedColumns`` drift audit).

Everything here returns M text, and every string that reaches it goes
through :func:`_m_string`. What the queries CARRY is decided by
``analysis/reporting/plan.py``; this module only writes it down. ``build``
knows the site (``--site-url``) and bakes it into every query, so a shipped
bundle has nothing to configure; the standalone ``report`` command knows
no site and falls back to a ``SiteUrl`` text parameter.
"""

from datetime import datetime

from dbml_sharepoint.analysis.exports import MULTI_VALUE_JOIN
from dbml_sharepoint.analysis.report_columns import (
    DATE_ZONE_RESOLVED_COLUMN,
    ITEM_URL_COLUMN,
    ITEM_URL_RESOLVED_COLUMN,
    REPORT_FIXED_COLUMNS,
    REPORT_KEY_SUFFIX,
    USERS_KEY_LIST,
    fk_key_column,
    person_key_column,
)
from dbml_sharepoint.analysis.reporting.dictionary import (
    LOADABLE_COLUMNS,
    PRINCIPAL_KINDS,
    USERS_COLUMNS,
    dictionary_rows,
    metadata_rows,
)
from dbml_sharepoint.analysis.reporting.plan import (
    TOLERANT_DATE_TYPES,
    ListPlan,
    build_plans,
    grouped_record_expands,
    reads_zone,
    tables_for_role,
    tolerant_date_columns,
)
from dbml_sharepoint.analysis.timezones import WINDOW_END, WINDOW_START, ZoneTable
from dbml_sharepoint.model.mapping_types import MappingBundle
from dbml_sharepoint.model.parser import Schema
from dbml_sharepoint.model.release import Release


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
_SITE_NAME_M: list[str] = [
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
]

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

# The scheme and host of SiteRoot on their own, which is what turns a SERVER-
# relative path (what SharePoint answers with) back into a URL a browser can
# open. Bound after `_SITE_ROOT_M`, which it reads.
#
# A root site collection is legitimately https://tenant.sharepoint.com with no
# path segment at all, so that shape falls through whole rather than being
# treated as malformed.
_SITE_ORIGIN_M: list[str] = [
    "    SiteOrigin =",
    "        let",
    '            afterScheme = Text.PositionOf(SiteRoot, "//"),',
    "            rest =",
    '                if afterScheme < 0 then ""',
    "                else Text.Range(SiteRoot, afterScheme + 2),",
    '            slash = Text.PositionOf(rest, "/")',
    "        in",
    "            if afterScheme < 0 or slash < 0 then SiteRoot",
    "            else Text.Start(SiteRoot, afterScheme + 2 + slash),",
]

# MEASURED on a live tenant, 2026-09-07: a calculated column of output type
# Date is served as a PLAIN STRING. In one /items response `LastReviewedDate`
# carried m:type="Edm.DateTime" and the calculated `NextReviewDue` beside it
# carried no m:type at all, so OData.Feed landed the second as text, the
# `type date` conversion errored on every row, and Power BI's default
# `returnErrorValuesAsNull` turned each error into a blank. The column read as
# empty rather than as broken, which is why the refresh reported nothing.
#
# One converter takes whichever shape arrives, so no step has to know which
# kind of column it holds. Every branch ends in a value: a shape nobody
# anticipated blanks one column, as today, rather than failing the batch.
#
# MEASURED again, and reported by a consumer 2026-09-09: a DATE-ONLY column
# holds site-local midnight and is served as the UTC instant of it, so on a
# UTC+10 site `LastReviewedDate` reads 2026-09-03T14:00:00Z where the list
# shows 4 September. Truncating that in UTC gives the 3rd, and every
# date-only column in the pack was a day early east of UTC (#467).
#
# WHY THE OFFSET IS IDENTIFIED RATHER THAN APPLIED. `web/RegionalSettings/
# TimeZone` answers with an `Information` record carrying `Bias`,
# `StandardBias` and `DaylightBias` and nothing else. MEASURED on a live
# tenant 2026-09-02 by `test/manual/datetime-sentinel-probe.js`, which had to
# call `utctolocaltime` to find out which of the two was in force and
# recorded the ambiguity as closing its gate on nine rows;
# `library-large-list-fixture-probe.js` builds the same two candidates and
# says the same thing. Learn agrees (SP.TimeZoneInformation, three
# properties).
#
# So the three values are static properties of the ZONE, not the offset in
# force on a day. Reading them every refresh, which is what a refresh does,
# still does not say whether daylight saving is on: none of the three
# changes when it starts. That is the obvious reading of a refresh-time read
# and it is the wrong one.
#
# `utctolocaltime` resolves it for ONE instant, at one request. That is fine
# in a probe and not here: per distinct value it is a request per value, and
# once per refresh it dates every row by today's rule, which is wrong for
# exactly the rows a transition just moved.
#
# What resolves it for free is the value itself. A date-only value is local
# midnight by construction (`date-storage-probe.js`: a date picked as the 2nd
# stores as `...-01T14:00:00Z` on a UTC+10 site), so of the candidate offsets
# exactly one lands it back on midnight, and that one was in force when the
# value was written. Rows either side of a transition each pick their own and
# no transition date is needed anywhere.
#
# The candidates are therefore TRIED, not chosen, which also makes this
# independent of the units and the sign convention the API answers in: a
# wrong candidate does not land on midnight and is discarded rather than
# believed. Zero is among them, which is what a calculated column arriving as
# a bare local date needs, and it is tried first so the precedence is fixed.
#
# A DECLARED ZONE (the build's `--time-zone`) adds a second use of the same
# read. The pack then ships that zone's transitions (see `_site_zone_m`), which
# is only right if the site is set to that zone, and nothing else in the pack
# can tell. So `resolved` also requires the site's two candidates to be exactly
# the offsets the declared zone uses under its CURRENT rule, and a build
# declaring Melbourne against a site set to London reads false on every row
# rather than converting by the wrong table.
#
# Current rule, not the window's history: the three biases describe the rule
# the site's zone is under today, so a zone that abolished daylight saving
# inside the window (Brazil 2019, Iran 2022) reports one offset, and a check
# against both of its historical offsets would read false on every row of
# every table for ever, with nothing wrong. A standing false is what destroys
# a flag whose meaning is "false is worth investigating".
#
# Symmetric, and written with `List.Difference` in both directions rather
# than list equality: a site set to Brisbane, which has one offset, against a
# declared Melbourne must still read false, and nothing here can execute M,
# so the check leans on nothing whose behaviour could be in question.


def _zone_m(zone: ZoneTable | None) -> list[str]:
    """The `Zone` binding: the site's zone, read once per refresh, and
    whether the read `resolved`, which with a declared zone also means it
    agreed with the declaration."""
    if zone is None:
        resolved = ["                    resolved = true,"]
    else:
        declared = "{" + ", ".join(str(o) for o in zone.current_offsets) + "}"
        resolved = [
            "                    // Read, AND agreeing with the declared zone",
            f"                    // ({zone.zone}): the offsets the site",
            "                    // answers with must be exactly the ones that",
            "                    // zone uses under its current rule, or every",
            "                    // conversion through the shipped table is by",
            "                    // the wrong rule.",
            "                    resolved =",
            "                        let",
            "                            SiteOffsets =",
            "                                List.Distinct(",
            "                                    {- (Bias + Standard), - (Bias + Daylight)}",
            "                                ),",
            f"                            DeclaredOffsets = {declared}",
            "                        in",
            "                            List.IsEmpty(",
            "                                List.Difference(SiteOffsets, DeclaredOffsets)",
            "                            )",
            "                            and List.IsEmpty(",
            "                                List.Difference(DeclaredOffsets, SiteOffsets)",
            "                            ),",
        ]
    return [
        "    // The site's time zone, read once per refresh; see AsDate below for",
        "    // what is done with it and why both biases are candidates.",
        "    Zone =",
        "        try",
        "            let",
        "                Info = OData.Feed(",
        '                    SiteRoot & "/_api/web/RegionalSettings/TimeZone",',
        "                    null,",
        '                    [Implementation = "2.0"]',
        "                )[Information],",
        '                Bias = Number.From(Record.FieldOrDefault(Info, "Bias", 0)),',
        "                Standard =",
        '                    Number.From(Record.FieldOrDefault(Info, "StandardBias", 0)),',
        "                Daylight =",
        '                    Number.From(Record.FieldOrDefault(Info, "DaylightBias", 0))',
        "            in",
        "                [",
        *resolved,
        "                    // Minutes EAST of UTC. A Win32 bias is the number of",
        "                    // minutes to ADD to local time to reach UTC, so the",
        "                    // sign is flipped. If that convention is ever wrong,",
        "                    // neither candidate lands on midnight and the value",
        "                    // falls through rather than shifting by 20 hours.",
        "                    offsets =",
        "                        List.Distinct(",
        "                            {0, - (Bias + Standard), - (Bias + Daylight)}",
        "                        )",
        "                ]",
        "        otherwise [resolved = false, offsets = {0}],",
    ]

# `Date.From` handles date, datetime and datetimezone directly. The text
# branch uses `DateTimeZone.From`, which parses ISO 8601 including the `Z`
# without depending on the machine's culture, which `Date.From` over text
# would. `RemoveZone` and no `ToUtc`, deliberately: text carrying `Z` is
# already the UTC wall clock, and text carrying no zone at all is already
# local, so converting would move the second kind by the REPORT MACHINE's
# offset, which has nothing to do with the site's.
#
# `AsStamp` is its own block because two converters read it: `AsDate` below,
# and the declared-zone helpers in `_site_zone_m`, which a query can carry
# with no date-only column at all. Emitted once, before whichever of the two
# the query needs.
_AS_STAMP_M: list[str] = [
    "    // The wall clock behind whichever shape the value arrived in.",
    "    AsStamp = (v as any) as nullable datetime =>",
    "        if v is datetimezone then",
    "            DateTimeZone.RemoveZone(DateTimeZone.ToUtc(v))",
    "        else if v is datetime then v",
    "        else if v is date then DateTime.From(v)",
    "        else",
    "            try DateTimeZone.RemoveZone(DateTimeZone.From(Text.From(v)))",
    "            otherwise null,",
]

_AS_DATE_M: list[str] = [
    "    AsDate = (v as any) as nullable date =>",
    "        if v = null then null",
    "        else",
    "            let",
    "                Stamp = AsStamp(v),",
    "                // The candidate offsets that land this value on local",
    "                // midnight, which is what a date-only value is.",
    "                Landed =",
    "                    if Stamp = null then {}",
    "                    else",
    "                        List.Select(",
    "                            List.Transform(",
    "                                Zone[offsets],",
    "                                each Stamp + #duration(0, 0, _, 0)",
    "                            ),",
    "                            each DateTime.Time(_) = #time(0, 0, 0)",
    "                        )",
    "            in",
    "                if not List.IsEmpty(Landed) then",
    "                    DateTime.Date(List.First(Landed))",
    "                // Nothing landed: not a date-only value, or the zone",
    "                // read failed. Truncate, which is what this did before",
    "                // the zone was read at all, and say so in",
    f"                // {DATE_ZONE_RESOLVED_COLUMN}.",
    "                else",
    "                    try Date.From(Stamp)",
    "                    otherwise try Date.From(v)",
    "                    otherwise null,",
]


def _m_datetime_literal(stamp: datetime) -> str:
    """A `#datetime(...)` literal for a UTC instant, to the second."""
    return (
        f"#datetime({stamp.year}, {stamp.month}, {stamp.day}, "
        f"{stamp.hour}, {stamp.minute}, {stamp.second})"
    )


def _site_zone_m(zone: ZoneTable) -> list[str]:
    """The declared zone's transition table and the helpers that read it.

    Emitted whenever a zone is declared, whether or not anything in the
    query calls them: a derived column may, and predictable output beats
    an emission rule that can be got wrong. About 100 rows for the window.

    `SiteOffsetAt` takes the last transition at or before the instant, which
    is `ZoneTable.offset_at` in M, so a test can pin the two together. The
    date-only conversion is NOT this: `AsDate` resolves the offset from the
    value itself and needs no declaration, so it stays the default for a
    date-only column. These helpers are for TIMESTAMPS.
    """
    rows = [
        f"        {{{_m_datetime_literal(at)}, {offset}}},"
        for at, offset in zone.transitions
    ]
    if rows:
        # M list literals do not allow a trailing comma.
        rows[-1] = rows[-1].rstrip(",")
    window = f"{WINDOW_START:%Y-%m-%d} to {WINDOW_END:%Y-%m-%d}"
    return [
        "    // The declared zone's daylight-saving transitions, generated from",
        f"    // the IANA database at build time ({zone.zone}, {window}):",
        "    // {UTC instant of the change, minutes east of UTC from then on}.",
        "    // M has no zone database and SharePoint serves no transition",
        "    // dates, so they ship here. Regenerate the pack when the zone's",
        "    // rules change; a timestamp past the last row takes that row's",
        "    // offset.",
        "    SiteTransitions = List.Buffer({",
        *rows,
        "    }),",
        "    // The offset in force at a UTC instant: the last transition at or",
        "    // before it, or the offset the window opened with.",
        "    SiteOffsetAt = (stamp as datetime) as number =>",
        "        let",
        "            Before = List.Select(SiteTransitions, each _{0} <= stamp)",
        "        in",
        f"            if List.IsEmpty(Before) then {zone.start_offset}",
        "            else List.Last(Before){1},",
        "    // The site-local wall clock behind a UTC timestamp, whichever shape",
        "    // it arrived in; see AsStamp above.",
        "    AsSiteDateTime = (v as any) as nullable datetime =>",
        "        let",
        "            Stamp = AsStamp(v)",
        "        in",
        "            if Stamp = null then null",
        "            else Stamp + #duration(0, 0, SiteOffsetAt(Stamp), 0),",
        "    // The site-local date of a UTC timestamp. Not for a date-only",
        "    // column, which AsDate resolves from the value itself.",
        "    AsSiteDate = (v as any) as nullable date =>",
        "        let",
        "            Local = AsSiteDateTime(v)",
        "        in",
        "            if Local = null then null else DateTime.Date(Local),",
    ]


def _item_url_base_m(plan: ListPlan) -> list[str]:
    """The display-form prefix for one list, read from the list at refresh.

    MEASURED on a live tenant, 2026-09-07: a list RENAMED in place keeps the
    URL slug it was created under, so a form path built from the declared
    title is a dead link for every row while ``getbytitle`` on the new title
    keeps working. The slug cannot be derived at build time; a mapping's
    ``renamed_from`` records rename CANDIDATES rather than an ordered history,
    and deriving it was tried against ten live lists and got two wrong, which
    is worse than not trying because the two wrong ones are indistinguishable
    from the eight right ones.

    Same single-entity ``OData.Feed`` read as the site name above, evaluated
    once per refresh rather than once per row, and it fails soft the same way
    and for the same reason: a link is a convenience, the rows are the data.

    THE FALLBACK CARRIES A FLAG, because failing soft here restores exactly
    the defect the folder read exists to fix. A permission that grants items
    but not the folder, a throttled call or a transient 503 all end in a URL
    built from the declared title, which on a renamed list is a dead link on
    every row while the refresh reports success. Fails soft AND visibly: the
    branch that ran rides beside the URL, so a report can suppress the link
    rather than ship a 404.
    """
    endpoint = (
        f"/_api/web/lists/getbytitle('{plan.list_title}')"
        "/RootFolder?$select=ServerRelativeUrl"
    )
    return [
        "    ItemUrl =",
        "        try",
        "            [",
        "                resolved = true,",
        "                base =",
        "                    SiteOrigin",
        "                        & OData.Feed(",
        f'                            SiteRoot & "{endpoint}",',
        "                            null,",
        '                            [Implementation = "2.0"]',
        "                        )[ServerRelativeUrl]",
        f'                        & "{plan.item_url_suffix}"',
        "            ]",
        "        otherwise",
        "            [",
        "                resolved = false,",
        f'                base = SiteRoot & "{plan.item_url_path}"',
        "            ],",
    ]


def _ensured_m(prev: str, columns: list[str]) -> list[str]:
    """Add any declared column the response left out, before anything reads it.

    MEASURED on a live tenant, 2026-09-07: a list with ZERO items answers with
    a table that has NO COLUMNS AT ALL, so the typing step failed on the first
    name it asked for ("The column 'Id' of the table wasn't found") and Power
    BI reported every other query in the batch as blocked behind it. Adding
    one item and refreshing again succeeded with no other change.

    A fresh deploy leaves every list empty, so that is the first refresh an
    adopter runs. The 2026-08-11 guard covers only the expanded record
    columns, which is the same failure seen from a list that had lookups.

    The placeholder type does not matter: every one of these columns is
    re-typed one step later, and over zero rows there is no value to convert.
    """
    names = ", ".join(f'"{name}"' for name in columns)
    return [
        "    Ensured = List.Accumulate(",
        f"        {{{names}}},",
        f"        {prev},",
        "        (t, c) =>",
        "            if List.Contains(Table.ColumnNames(t), c) then t",
        "            else Table.AddColumn(t, c, each null, type text)",
        "    ),",
    ]


#: How each aggregate reads the child rows. `_` is the group's sub-table, so
#: `_[Column]` is that column as a list. A `names` cell is for READING: it is
#: sorted and de-duplicated, and unlike a multi-value column nothing
#: guarantees a member does not itself contain the separator, so it must not
#: be split back apart.
_DERIVED_AGGREGATE_M: dict[str, str] = {
    "count": "each Table.RowCount(_)",
    "min": "each List.Min(_[{column}])",
    "max": "each List.Max(_[{column}])",
    "names": (
        "each Text.Combine("
        "List.Sort(List.Distinct(List.RemoveNulls(_[{column}]))), "
        f'"{MULTI_VALUE_JOIN}")'
    ),
}


def _query_ref(name: str) -> str:
    """One query named as M identifier syntax, always quoted.

    `#"..."` is valid for ANY name, and a bare identifier is not: `_Users`
    leads with an underscore and a family whose prefix carries a space or a
    dash would not be an identifier at all. Quoting unconditionally means
    the emitted reference never depends on what a prefix happens to contain.

    THE QUERY MUST CARRY THIS NAME. A cross-query reference resolves by
    name, so a derived join works only where each `.pq` was loaded under the
    name its file has; guide.md says so beside the instruction to paste them.
    """
    return f'#"{name}"'


def _derived_site_bindings(plan: ListPlan) -> tuple[list[str], dict[str, str]]:
    """One binding per query a `count` reads, and the name each got.

    WHY A COUNT ASKS WHICH SITE ITS CHILD QUERY IS ON. A derived join reads
    the other query as it stands in the model. The pack's guide tells an
    operator building a multi-site report to duplicate each query per site,
    and a duplicate pointed at another site would still read THIS copy of the
    child. Every key carries its site, so nothing matches, and a count then
    reads as a confident ZERO where the truth is not zero. That is a wrong
    number with nothing able to notice it.

    So a count coalesces its blank to zero only where the child query is on
    the same site, and to null otherwise. An EMPTY child list still reads
    zero: it names no site, there are no rows to miss, and zero is the right
    answer.
    """
    lines: list[str] = []
    named: dict[str, str] = {}
    for step in plan.derived:
        if step.kind != "count" or step.source_query in named:
            continue
        binding = f"DerivedSite{len(named) + 1}"
        named[step.source_query] = binding
        lines += [
            f"    // Which site {step.source_query} reads; see the count",
            "    // steps below for why a blank there is not always a zero.",
            f"    {binding} =",
            "        try",
            "            List.First(",
            (f"                Table.Column({_query_ref(step.source_query)}, "
             f'"{REPORT_FIXED_COLUMNS[0]}"),'),
            "                null",
            "            )",
            "        otherwise null,",
        ]
    return lines, named


def _derived_m(plan: ListPlan, prev: str, sites: dict[str, str]) -> tuple[list[str], str]:
    """The derived-column steps for one list, and the step they end on."""
    lines: list[str] = []
    index = 0

    def step_name() -> str:
        nonlocal index
        index += 1
        return f"Derived{index}"

    for entry in plan.derived:
        if entry.description:
            lines.append(f"    // {entry.description}")
        if entry.kind == "expr":
            name = step_name()
            if entry.replace:
                # `Table.ReplaceValue` with `each` over the row, so the
                # expression can read the column it is replacing (which is
                # the whole point of a fallback) and the column keeps its
                # position. `Table.TransformColumns` would hand it the value
                # alone and no other column of the row.
                lines += [
                    f"    {name} = Table.ReplaceValue(",
                    f"        {prev},",
                    f"        each [{entry.name}],",
                    f"        each {entry.m},",
                    "        Replacer.ReplaceValue,",
                    f'        {{"{entry.name}"}}',
                    "    ),",
                ]
                prev = name
                name = step_name()
                lines += [
                    f"    {name} = Table.TransformColumnTypes(",
                    f"        {prev},",
                    f'        {{{{"{entry.name}", {entry.m_type}}}}}',
                    "    ),",
                ]
            else:
                lines += [
                    f"    {name} = Table.AddColumn(",
                    f'        {prev}, "{entry.name}",',
                    f"        each {entry.m},",
                    f"        {entry.m_type}",
                    "    ),",
                ]
            prev = name
            continue
        lines.append(
            f"    // Reads the {entry.source_query} query. Both are keyed by "
            "site,",
        )
        lines.append(
            "    // so a copy of this query pointed at another site matches "
            "nothing.",
        )
        if entry.kind == "lookup":
            picks = [source for source, _out, _t in entry.picks]
            outs = [out for _source, out, _t in entry.picks]
            name = step_name()
            lines += [
                f"    {name} = Table.NestedJoin(",
                f'        {prev}, {{"{entry.own_key}"}},',
                "        Table.SelectColumns(",
                f"            {_query_ref(entry.source_query)},",
                "            {" + ", ".join(
                    f'"{c}"' for c in [entry.other_key, *picks]
                ) + "}",
                "        ),",
                (f'        {{"{entry.other_key}"}}, "_derived{index}", '
                 "JoinKind.LeftOuter"),
                "    ),",
            ]
            prev = name
            expanded = step_name()
            lines += [
                f"    {expanded} = Table.ExpandTableColumn(",
                f'        {prev}, "_derived{index - 1}",',
                "        {" + ", ".join(f'"{c}"' for c in picks) + "},",
                "        {" + ", ".join(f'"{c}"' for c in outs) + "}",
                "    ),",
            ]
            prev = expanded
            typed = step_name()
            lines += [
                f"    {typed} = Table.TransformColumnTypes(",
                f"        {prev},",
                "        {" + ", ".join(
                    f'{{"{out}", {m_type}}}'
                    for _source, out, m_type in entry.picks
                ) + "}",
                "    ),",
            ]
            prev = typed
            continue
        child = _query_ref(entry.source_query)
        if entry.where:
            child = f"Table.SelectRows({child}, each {entry.where})"
        aggregate = _DERIVED_AGGREGATE_M[entry.aggregate].format(
            column=entry.column,
        )
        name = step_name()
        lines += [
            f"    {name} = Table.NestedJoin(",
            f'        {prev}, {{"{entry.own_key}"}},',
            "        Table.Group(",
            f"            {child},",
            f'            {{"{entry.other_key}"}},',
            f'            {{{{"{entry.name}", {aggregate}, type any}}}}',
            "        ),",
            (f'        {{"{entry.other_key}"}}, "_derived{index}", '
             "JoinKind.LeftOuter"),
            "    ),",
        ]
        prev = name
        expanded = step_name()
        lines += [
            f"    {expanded} = Table.ExpandTableColumn(",
            f'        {prev}, "_derived{index - 1}",',
            f'        {{"{entry.name}"}}, {{"{entry.name}"}}',
            "    ),",
        ]
        prev = expanded
        typed = step_name()
        if entry.aggregate == "count":
            binding = sites[entry.source_query]
            blank = (
                f"if {binding} = null or {binding} = SiteRoot "
                "then 0 else null"
            )
            lines += [
                f"    {typed} = Table.TransformColumns(",
                f"        {prev},",
                "        {",
                f'            {{"{entry.name}",',
                f"                each if _ = null then ({blank}) else _,",
                f"                {entry.m_type}}}",
                "        }",
                "    ),",
            ]
        else:
            lines += [
                f"    {typed} = Table.TransformColumnTypes(",
                f"        {prev},",
                f'        {{{{"{entry.name}", {entry.m_type}}}}}',
                "    ),",
            ]
        prev = typed
    return lines, prev


def _render_m(plan: ListPlan, *, site_url: str | None = None) -> str:
    query_string = "?$select=" + ",".join(plan.selects)
    # Every column a step below names. `multi_value_joins` is the one output
    # column deliberately absent from `m_types` (its join step ascribes the
    # type), and a set built from `m_types` alone would leave that one column
    # unguarded and unselected.
    declared = (
        [name for name, _ in plan.m_types]
        + [name for name, _ in plan.multi_value_joins]
    )
    dates = tolerant_date_columns(plan)
    zone_read = reads_zone(plan)
    # Bound once: the step lines and the names the count steps read must
    # come from ONE call, or a rename here would leave the counts reading a
    # binding that is not there.
    site_lines, site_bindings = _derived_site_bindings(plan)
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
        *_SITE_NAME_M,
        *_SITE_ORIGIN_M,
        *_item_url_base_m(plan),
        *site_lines,
        *(_zone_m(plan.zone) if zone_read else []),
        *(_AS_STAMP_M if zone_read else []),
        *(_AS_DATE_M if dates else []),
        *(_site_zone_m(plan.zone) if plan.zone is not None else []),
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
    # GROUPED BY SOURCE RECORD, because a lookup that also projects columns
    # takes more than one field out of the same record and the record is
    # CONSUMED by the first expand. Two steps against it would fail the
    # second with "The column 'Stakeholder' of the table wasn't found", which
    # reads as a broken query. Order of first appearance, so a query with no
    # projections renders exactly as it did.
    for i, (record_col, fields) in enumerate(
        grouped_record_expands(plan), start=1,
    ):
        step = f"Expand{i}"
        inners = ", ".join(f'"{inner}"' for inner, _, _ in fields)
        outs = ", ".join(f'"{out}"' for _, out, _ in fields)
        lines += [
            f"    {step} =",
            f'        if List.Contains(Table.ColumnNames({prev}), "{record_col}")',
            (f'        then Table.ExpandRecordColumn({prev}, "{record_col}", '
             f"{{{inners}}}, {{{outs}}})"),
        ]
        if len(fields) == 1:
            _inner, out, m_type = fields[0]
            lines.append(
                f'        else Table.AddColumn({prev}, "{out}", each null, '
                f"{m_type}),",
            )
        else:
            # One accumulator rather than nested AddColumn calls, so the
            # shape does not change with the number of projected columns.
            lines += [
                "        else",
                "            List.Accumulate(",
                "                {",
            ]
            lines += [
                f'                    [Name = "{out}", Kind = {m_type}],'
                for _inner, out, m_type in fields
            ]
            lines[-1] = lines[-1].rstrip(",")
            lines += [
                "                },",
                f"                {prev},",
                "                (t, c) =>",
                "                    Table.AddColumn(t, c[Name], each null, c[Kind])",
                "            ),",
            ]
        prev = step
    lines += _ensured_m(prev, declared)
    prev = "Ensured"
    if dates:
        lines += [
            "    // Whichever shape each date arrived in; see AsDate above.",
            "    Dates = Table.TransformColumns(",
            f"        {prev},",
            "        {",
        ]
        lines += [
            f'            {{"{name}", each AsDate(_), type date}},'
            for name in dates
        ]
        # M list literals do not allow a trailing comma.
        lines[-1] = lines[-1].rstrip(",")
        lines += [
            "        }",
            "    ),",
        ]
        prev = "Dates"
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
        for name, members_are_text in plan.multi_value_joins:
            # A multi-value lookup's members are ids, and Text.Combine over a
            # list of numbers raises, so they are converted first.
            members = "_" if members_are_text else "List.Transform(_, Text.From)"
            lines += [
                (f'            {{"{name}", each if _ = null '
                 "or List.IsEmpty(_) then null"),
                (f'                else Text.Combine({members}, '
                 f'"{MULTI_VALUE_JOIN}"), type text}},'),
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
    # Dates are already converted and typed by the step above; a bare
    # conversion is exactly what put an error value in every one of their
    # cells.
    for name, m_type in plan.m_types:
        if m_type in TOLERANT_DATE_TYPES:
            continue
        lines.append(f'            {{"{name}", {m_type}}},')
    # M list literals do not allow a trailing comma.
    lines[-1] = lines[-1].rstrip(",")
    # Whatever SharePoint adds unasked rides through every step above, so the
    # declared set is selected here.
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
        # The list's real URL, not one built from its declared title: see
        # `_item_url_base_m`. Bound above, so it is one read per refresh.
        "    WithItemURL = Table.AddColumn(",
        f'        Declared, "{ITEM_URL_COLUMN}",',
        "        each ItemUrl[base] & Number.ToText([Id]),",
        "        type text",
        "    ),",
        # Whether the URL beside it was read from the list or guessed from
        # the declared title. False means every link in this table may 404,
        # which is worth suppressing a link over and impossible to see
        # otherwise: the refresh succeeds either way.
        "    WithItemURLResolved = Table.AddColumn(",
        f'        WithItemURL, "{ITEM_URL_RESOLVED_COLUMN}",',
        "        each ItemUrl[resolved],",
        "        type logical",
        "    ),",
        # Where the row came from. One build covers one site, but a report
        # routinely appends several deployments of the same template, and
        # without these two columns there is nothing to slice by.
        "    WithSiteUrl = Table.AddColumn(",
        (f'        WithItemURLResolved, "{REPORT_FIXED_COLUMNS[0]}", '
         "each SiteRoot, type text"),
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
    if zone_read:
        # The same argument as ItemURLResolved above: without the site's
        # zone every date-only column silently truncates in UTC, which is a
        # day early east of UTC, and the refresh succeeds. A report that
        # cannot see which branch ran cannot tell a correct date from one
        # the zone read failed to correct. With a declared zone the same
        # flag says whether the site agreed with it; see `_zone_m`.
        lines[-1] += ","
        lines += [
            "    WithDateZoneResolved = Table.AddColumn(",
            f'        {prev}, "{DATE_ZONE_RESOLVED_COLUMN}",',
            "        each Zone[resolved],",
            "        type logical",
            "    )",
        ]
        prev = "WithDateZoneResolved"
    for i, (fk_col, target_title, _display, _proj) in enumerate(
        plan.joins, start=1,
    ):
        step = f"WithFkKey{i}"
        lines[-1] += ","
        lines += [
            f"    {step} = Table.AddColumn(",
            f'        {prev}, "{fk_key_column(fk_col)}",',
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
    if plan.users_table:
        # One key per person column into `_Users`, in the same shape as a
        # lookup key and null-guarded for the same reason. Namespaced under
        # USERS_KEY_LIST rather than a list title because the users
        # dimension is not a list of this schema.
        for i, name in enumerate(plan.person_columns, start=1):
            step = f"WithUserKey{i}"
            lines[-1] += ","
            lines += [
                f"    {step} = Table.AddColumn(",
                f'        {prev}, "{person_key_column(name)}",',
                f"        each if [{name}Id] = null then null",
                f"              else {_row_key_m(USERS_KEY_LIST, f'[{name}Id]')},",
                "        type text",
                "    )",
            ]
            prev = step
    if plan.derived:
        lines[-1] += ","
        lines += [
            "    // Reporting-only columns, declared under `derived_columns`.",
            "    // No SharePoint field stands behind any of these: they are",
            "    // computed here and exist nowhere else. After the keys,",
            "    // because a join reads them; before the rename, so a",
            "    // derived column takes a display title like any other.",
        ]
        derived_lines, prev = _derived_m(plan, prev, site_bindings)
        lines += derived_lines
        # The steps above each close with their own comma; the chain has to
        # end without one for whatever follows to attach.
        lines[-1] = lines[-1].rstrip(",")
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
    time_zone: str | None = None,
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

    ``time_zone`` is the site's IANA zone, which both commands supply: each
    query then carries its transitions and the site-date helpers. See
    `build_plans` for why it is optional here.
    """
    queries = {
        f"{plan.list_title}.pq": _render_m(plan, site_url=site_url)
        for plan in build_plans(schema, bundle, site_role, time_zone=time_zone)
    }
    if bundle.mapping.reporting.users_table:
        queries[f"{USERS_KEY_LIST}.pq"] = _render_users_m(site_url=site_url)
    return queries


def _render_users_m(*, site_url: str | None = None) -> str:
    """The `_Users` dimension: the site's user information list, one row per
    principal the site has ever resolved, keyed like every list table."""
    select = ",".join(name for name, _, _ in USERS_COLUMNS) + ",ContentTypeId"
    kind_expression = "each if [ContentTypeId] = null then \"Other\""
    for prefix, label in PRINCIPAL_KINDS:
        kind_expression += (
            f' else if Text.StartsWith([ContentTypeId], "{prefix}") then "{label}"'
        )
    kind_expression += ' else "Other"'
    # One per line, like every list query: the typing step is the one place a
    # column can silently stop being typed, so it is read by tests and by
    # people, and a single long line hides both.
    typed = [
        f'            {{"{name}", {m_type}}},' for name, m_type, _ in USERS_COLUMNS
    ] + ['            {"ContentTypeId", type text}']
    declared = ", ".join(f'"{name}"' for name, _, _ in USERS_COLUMNS)
    renames = ", ".join(
        f'{{"{name}", "{display}"}}'
        for name, _, display in USERS_COLUMNS if display != name
    )
    lines = [
        f"// {USERS_KEY_LIST}: generated by dbml-sharepoint; regenerate rather than hand-edit.",
        "// The site's user information list (/_api/web/siteuserinfolist) as a",
        "// dimension: one row per person, SharePoint group or domain group the",
        "// site has ever resolved, keyed like every list table (User Key), so",
        "// the `... Key` on any person column joins here. See guide.md for the",
        "// one-active-relationship rule when a list has several person columns.",
        *([
            "// Requires the same SiteUrl text parameter as the list queries.",
        ] if site_url is None else []),
        "let",
        *_site_url_binding_m(site_url),
        *_SITE_ROOT_M,
        *_SITE_NAME_M,
        "    // MEASURED on a live tenant, 2026-09-02, by a site admin: these are",
        "    // the list's own internal names, a person column's ids resolve to",
        "    // its rows with the same Title, and ContentTypeId starts 0x010A for",
        "    // a person, 0x010B for a SharePoint group and 0x010C for a domain",
        "    // group. A reader-tier account was NOT measured: a 403 here means",
        "    // the reporting account needs read access to this list.",
        "    Source = OData.Feed(",
        '        SiteRoot & "/_api/web/siteuserinfolist/items"',
        f'            & "?$select={select}",',
        "        null,",
        '        [Implementation = "2.0"]',
        "    ),",
        # The users list is read like any other list and answers like one, so
        # a site whose user information list the reporting account can see but
        # that holds no rows fails the same way. See `_ensured_m`.
        *_ensured_m(
            "Source",
            [name for name, _, _ in USERS_COLUMNS] + ["ContentTypeId"],
        ),
        "    Typed = Table.TransformColumnTypes(",
        "        Ensured,",
        "        {",
        *typed,
        "        }",
        "    ),",
        "    // Groups sit in the same list as people; this says which is which,",
        "    // so a report can keep the people and drop the rest.",
        "    WithKind = Table.AddColumn(",
        '        Typed, "Principal Kind",',
        f"        {kind_expression},",
        "        type text",
        "    ),",
        "    // Only the declared columns go on: SharePoint adds an uppercase `ID`",
        "    // beside `Id`, which a case-insensitive model would load as \"ID 2\".",
        "    Declared = Table.SelectColumns(",
        "        WithKind,",
        f'        {{{declared}, "Principal Kind"}}',
        "    ),",
        "    WithSiteUrl = Table.AddColumn(",
        f'        Declared, "{REPORT_FIXED_COLUMNS[0]}", each SiteRoot, type text',
        "    ),",
        "    WithSiteName = Table.AddColumn(",
        f'        WithSiteUrl, "{REPORT_FIXED_COLUMNS[1]}", each SiteName, type text',
        "    ),",
        "    // Site user ids are per site collection, so the key carries the",
        "    // site, and the same person on two sites is two rows. Email is on",
        "    // the row for anyone who needs a cross-site people table.",
        "    WithUserKey = Table.AddColumn(",
        f'        WithSiteName, "User{REPORT_KEY_SUFFIX}",',
        f"        each {_row_key_m(USERS_KEY_LIST, '[Id]')},",
        "        type text",
        "    ),",
        "    // Model-facing names, always: there is no schema whose internal",
        "    // names a report author would recognise here.",
        "    RenamedForModel = Table.RenameColumns(",
        "        WithUserKey,",
        f"        {{{renames}}}",
        "    )",
        "in",
        "    RenamedForModel",
        "",
    ]
    return "\n".join(lines)


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
    plans: list[ListPlan], *, site_url: str | None = None,
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
    time_zone: str | None = None,
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
        "{" + ", ".join([
            str(i), _m_string(list_title), *(_m_string(cell) for cell in row),
        ]) + "}"
        for i, (list_title, row) in enumerate(
            dictionary_rows(schema, bundle, site_role), start=1,
        )
    ]
    tables = tables_for_role(schema, bundle, site_role)
    mi_rows = [
        "{" + _m_string(field_name) + ", " + _m_string(value) + "}"
        for field_name, value in metadata_rows(
            bundle, site_role, len(tables),
            release, generated_at, source_schema, source_mapping,
        )
    ]
    return {
        "_DataDictionary.pq": _render_m_table(
            "_DataDictionary",
            "Load and add a report page with a table visual over this query "
            "(sorted by SortOrder) to surface the data dictionary in the report.",
            "SortOrder = Int64.Type, List = text, "
            + ", ".join(f"{name} = text" for name in LOADABLE_COLUMNS),
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
            build_plans(schema, bundle, site_role, time_zone=time_zone), site_url=site_url,
        ),
    }
