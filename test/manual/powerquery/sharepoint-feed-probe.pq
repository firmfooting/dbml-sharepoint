// dbml-sharepoint POWER QUERY PROBE (READ-ONLY): WHAT THE FEED ACTUALLY
// HANDS POWER QUERY
//
// QUESTION: through the exact call the reporting pack makes, what SHAPE
// does SharePoint hand back for a date-only column, for a calculated date
// column, for a projected dependent lookup, and for the site's time zone?
//
// WHY: the pack decides all four from the wire shape. `AsStamp` branches on
// whether a value arrives zoned, naive, a date or text. The zone read
// assumes `OData.Feed` surfaces `Information` as a record. The projection
// fix assumes `$select=Lookup/Column` with `$expand=Lookup` returns the
// target's column. None of that is exercised by any test in this
// repository, and the Power BI Service does not have to agree with Power BI
// Desktop about any of it.
//
// WHAT IT PRINTS: one row per question, with the value the generator
// ASSUMES and the value this host observed. It prints DATES and SHAPES. It
// never prints the site URL, a server-relative path, an item title or a
// person, so the table can be pasted back safely.
//
// HOW TO RUN
//   1. Edit the five values under CONFIGURE below. Leave them as they are
//      and the probe returns a single row telling you so; nothing is read.
//   2. Power BI Desktop: Get data, Blank query, Advanced Editor, paste,
//      Done. Sign in with an account that can read the list.
//   3. Read the table and copy it out.
//   4. Publish and refresh in the Power BI Service, and read it again. RUN
//      BOTH. The Service is where a published model refreshes, and it is a
//      different runtime.
//
// It reads. It writes nothing and creates nothing.
let
    // ---- CONFIGURE ---------------------------------------------------
    // The SITE, not a list, a form or a page.
    SiteUrl = "https://contoso.sharepoint.com/sites/Example",
    // A list this pack generated, and four of its column INTERNAL names.
    ListTitle = "SET_ME",
    // A `date` column: the kind that was reading a day early.
    DateOnlyColumn = "SET_ME",
    // A calculated column whose output type is Date, or "" if none.
    CalculatedDateColumn = "",
    // A lookup column, and a column of ITS TARGET that the mapping
    // projects onto this list under `lookup_projections`. Both "" to skip.
    LookupColumn = "",
    LookupTargetColumn = "",

    // ---- gate --------------------------------------------------------
    Configured =
        ListTitle <> "SET_ME"
        and DateOnlyColumn <> "SET_ME"
        and not Text.Contains(SiteUrl, "contoso"),

    // ---- helpers -----------------------------------------------------
    Yn = (b as any) as text =>
        if b = null then "null" else if b then "true" else "false",
    Ymd = (d as nullable date) as text =>
        if d = null then "null"
        else Text.From(Date.Year(d))
            & "-" & Text.PadStart(Text.From(Date.Month(d)), 2, "0")
            & "-" & Text.PadStart(Text.From(Date.Day(d)), 2, "0"),
    // What the value IS, as the four tests AsStamp makes, in its order.
    Shape = (v as any) as text =>
        if v = null then "null"
        else "datetimezone=" & Yn(v is datetimezone)
            & " datetime=" & Yn(v is datetime)
            & " date=" & Yn(v is date)
            & " text=" & Yn(v is text),

    // The site root, trimmed the way every generated query trims it.
    SiteRoot = Text.TrimEnd(SiteUrl, "/"),
    Feed = (path as text) as any =>
        OData.Feed(SiteRoot & path, null, [Implementation = "2.0"]),

    // ---- the reads ---------------------------------------------------
    ZoneInfo = try Feed("/_api/web/RegionalSettings/TimeZone")[Information],
    Bias = try Number.From(Record.FieldOrDefault(ZoneInfo[Value], "Bias", "x")),
    StandardBias =
        try Number.From(Record.FieldOrDefault(ZoneInfo[Value], "StandardBias", "x")),
    DaylightBias =
        try Number.From(Record.FieldOrDefault(ZoneInfo[Value], "DaylightBias", "x")),

    Selected =
        "Id," & DateOnlyColumn
        & (if CalculatedDateColumn = "" then "" else "," & CalculatedDateColumn)
        & (if LookupColumn = "" then ""
           else "," & LookupColumn & "Id,"
                & LookupColumn & "/" & LookupTargetColumn),
    Expanded = if LookupColumn = "" then "" else "&$expand=" & LookupColumn,
    Items =
        try Feed(
            "/_api/web/lists/getbytitle('" & ListTitle & "')/items"
                & "?$select=" & Selected & Expanded & "&$top=50"
        ),
    // A ROW WHERE THE LOOKUP IS SET, not simply the first row. An optional
    // lookup is blank on most rows, and reading a field off the null record
    // errors, which this probe reported as the expand not working. It could
    // not tell "no related item" from "the mechanism is broken", which sent
    // a real investigation down the wrong path once.
    Populated =
        if LookupColumn = "" then Items
        else
            try Table.SelectRows(
                Items[Value], each Record.Field(_, LookupColumn) <> null
            )
            otherwise Items,
    Rows = try (if LookupColumn = "" then Items[Value] else Populated[Value]),
    FirstRow =
        try (if Table.RowCount(Rows[Value]) = 0
             then Table.First(Items[Value])
             else Table.First(Rows[Value])),
    LookupRows = try Table.RowCount(Rows[Value]) otherwise 0,
    DateRaw = try Record.Field(FirstRow[Value], DateOnlyColumn),
    CalcRaw =
        if CalculatedDateColumn = "" then null
        else try Record.Field(FirstRow[Value], CalculatedDateColumn),
    LookupRecord =
        if LookupColumn = "" then null
        else try Record.Field(FirstRow[Value], LookupColumn),
    Projected =
        if LookupColumn = "" then null
        else try Record.Field(LookupRecord[Value], LookupTargetColumn),

    RootFolder =
        try Feed(
            "/_api/web/lists/getbytitle('" & ListTitle & "')"
                & "/RootFolder?$select=ServerRelativeUrl"
        )[ServerRelativeUrl],
    // The LAST segment only. The full path carries the site, and a probe
    // transcript is pasted into a chat window.
    Slug =
        if not RootFolder[HasError]
        then List.Last(Text.Split(Text.TrimEnd(RootFolder[Value], "/"), "/"))
        else "(unreadable)",

    // The pack's own resolution, so the operator can compare it with what
    // the list shows on screen for the same item.
    Candidates =
        if Bias[HasError] then {0}
        else List.Distinct({
            0,
            - (Bias[Value] + StandardBias[Value]),
            - (Bias[Value] + DaylightBias[Value])
        }),
    AsStamp = (v as any) as nullable datetime =>
        if v is datetimezone then DateTimeZone.RemoveZone(DateTimeZone.ToUtc(v))
        else if v is datetime then v
        else if v is date then DateTime.From(v)
        else try DateTimeZone.RemoveZone(DateTimeZone.From(Text.From(v)))
            otherwise null,
    AsDate = (v as any) as nullable date =>
        let
            Stamp = AsStamp(v),
            Landed =
                if Stamp = null then {}
                else List.Select(
                    List.Transform(Candidates, each Stamp + #duration(0, 0, _, 0)),
                    each DateTime.Time(_) = #time(0, 0, 0)
                )
        in
            if not List.IsEmpty(Landed) then DateTime.Date(List.First(Landed))
            else try Date.From(Stamp) otherwise null,

    Rows = #table(
        type table [Id = text, Question = text, Expected = text, Observed = text],
        {
            {
                "feed.host.local-offset-hours",
                "Hours between this host's clock and UTC. The Service reports "
                    & "0. This row says which host produced the table",
                "(observation)",
                Text.From(DateTimeZone.ZoneHours(DateTimeZone.LocalNow()))
            },
            {
                "feed.zone.information-is-a-record",
                "The zone read assumes OData.Feed surfaces `Information` as a "
                    & "record carrying Bias. If this is false the query falls "
                    & "back and every date-only column truncates in UTC",
                "true",
                Yn(not Bias[HasError])
            },
            {
                "feed.zone.biases",
                "Bias, StandardBias and DaylightBias as this site reports "
                    & "them, in minutes",
                "(observation)",
                if Bias[HasError] then "(unreadable)"
                else Text.From(Bias[Value])
                    & " / " & Text.From(StandardBias[Value])
                    & " / " & Text.From(DaylightBias[Value])
            },
            {
                "feed.zone.candidate-offsets",
                "The offsets the pack tries, in minutes east of UTC. A site "
                    & "that observes daylight saving reports two beside zero",
                "(observation)",
                Text.Combine(List.Transform(Candidates, Text.From), ", ")
            },
            {
                "feed.date.date-only-arrives-as",
                "Which of AsStamp's four tests a date-only value answers to. "
                    & "The branch order assumes datetimezone is asked first",
                "(observation)",
                if DateRaw[HasError] then "(unreadable)" else Shape(DateRaw[Value])
            },
            {
                "feed.date.raw-instant",
                "The value as served. On a site east of UTC a date-only "
                    & "column reads as the PREVIOUS day at 24 hours minus the "
                    & "offset, which is the whole defect",
                "(observation)",
                if DateRaw[HasError] then "(unreadable)"
                else Text.From(DateRaw[Value])
            },
            {
                "feed.date.pack-resolves-to",
                "The date the pack derives. COMPARE THIS BY EYE with the date "
                    & "the list shows for the same item. They must match",
                "(observation)",
                if DateRaw[HasError] then "(unreadable)" else Ymd(AsDate(DateRaw[Value]))
            },
            {
                "feed.calculated-date.arrives-as",
                "A calculated column of output type Date was measured in 2026 "
                    & "as arriving untyped. AsStamp's text branch handles that",
                "(observation)",
                if CalculatedDateColumn = "" then "(not configured)"
                else if CalcRaw[HasError] then "(unreadable)"
                else Shape(CalcRaw[Value])
            },
            {
                "feed.calculated-date.pack-resolves-to",
                "The date the pack derives from that calculated column",
                "(observation)",
                if CalculatedDateColumn = "" then "(not configured)"
                else if CalcRaw[HasError] then "(unreadable)"
                else Ymd(AsDate(CalcRaw[Value]))
            },
            {
                "feed.projection.rows-with-the-lookup-set",
                "How many of the rows read carry the lookup at all. Zero "
                    & "means the two rows below tested nothing, which is not "
                    & "the same as the expand failing",
                "(observation)",
                if LookupColumn = "" then "(not configured)"
                else Text.From(LookupRows)
            },
            {
                "feed.projection.expand-returns-the-target-column",
                "`$select=Lookup/Column` with `$expand=Lookup` must return the "
                    & "target's column. This is the path the dependent-lookup "
                    & "fix reads every projection through",
                "true",
                if LookupColumn = "" then "(not configured)"
                else if LookupRows = 0 then "(no row carries this lookup)"
                else Yn(not Projected[HasError])
            },
            {
                "feed.projection.value-shape",
                "What that projected column arrives as, which decides the type "
                    & "the pack ascribes it",
                "(observation)",
                if LookupColumn = "" then "(not configured)"
                else if Projected[HasError] then "(unreadable)"
                else Shape(Projected[Value])
            },
            {
                "feed.rootfolder.readable",
                "The item link is built from the list's own folder, because a "
                    & "renamed list keeps the slug it was created under. False "
                    & "means ItemURLResolved is false on every row",
                "true",
                Yn(not RootFolder[HasError])
            },
            {
                "feed.rootfolder.slug",
                "The last segment of that folder. Where it differs from the "
                    & "list title, this list was renamed and the fallback would "
                    & "have produced a dead link for every row",
                "(observation)",
                Slug
            }
        }
    ),
    WithVerdict = Table.AddColumn(
        Rows,
        "Verdict",
        each if [Expected] = "(observation)" then "OBSERVED"
            else if [Observed] = [Expected] then "OK"
            else "DIFFERS",
        type text
    ),
    NotConfigured = #table(
        type table [Id = text, Question = text, Expected = text, Observed = text,
                    Verdict = text],
        {{
            "feed.gate",
            "Edit SiteUrl, ListTitle and DateOnlyColumn at the top of this "
                & "query, then refresh. Nothing was read",
            "(observation)", "unedited", "OBSERVED"
        }}
    )
in
    if Configured then WithVerdict else NotConfigured
