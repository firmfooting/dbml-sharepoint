// dbml-sharepoint POWER QUERY PROBE (READ-ONLY, NO SITE NEEDED)
//
// QUESTION: does the M this generator emits mean what the generator thinks
// it means, and does it mean the same thing in Power BI Desktop on Windows
// as it does in the Power BI Service?
//
// WHY: every other probe in this repository is pasted into a browser and
// asks SharePoint a question. Nothing asks POWER QUERY one. The reporting
// pack is generated M, no test in this repository executes M, and the two
// hosts that run it are not the same runtime: the Service refreshes in UTC
// with no machine time zone, and Desktop refreshes on somebody's laptop.
// So the constructs below are asserted by the generator and measured by
// nothing until an operator runs this.
//
// WHAT IT PRINTS: one row per question, with the value the generator
// ASSUMES and the value this host produced. `Verdict` is OK where they
// agree, DIFFERS where they do not, and OBSERVED for the rows that only
// report what the host is. A DIFFERS row is a finding: it names a
// construct the emitted queries rely on and this host does not honour.
//
// HOW TO RUN
//   1. Power BI Desktop: Get data, Blank query, Advanced Editor, paste
//      this whole file, Done, Close and Apply. Name the query
//      `_MRuntimeProbe`.
//   2. Paste `_ProbeOther.pq` into a second blank query and name it
//      exactly `_ProbeOther`. One row below reads it by name, which is how
//      a derived lookup or count reads another list's query.
//   3. Read the table. Copy it out.
//   4. Publish the report to the Power BI Service, refresh it there, and
//      read the same table again. RUN BOTH. A row that is OK in Desktop
//      and DIFFERS in the Service is the failure this pack most needs to
//      know about, because the Service is where a published model lives.
//
// Nothing here touches a site, writes anything, or needs a credential.
let
    // ---- helpers -----------------------------------------------------
    // Dates are formatted by hand rather than through Date.ToText, whose
    // signature has changed and whose default is culture-dependent. This
    // probe must not measure the host's locale by accident.
    Ymd = (d as nullable date) as text =>
        if d = null then "null"
        else Text.From(Date.Year(d))
            & "-" & Text.PadStart(Text.From(Date.Month(d)), 2, "0")
            & "-" & Text.PadStart(Text.From(Date.Day(d)), 2, "0"),

    Yn = (b as any) as text =>
        if b = null then "null" else if b then "true" else "false",

    // ---- the conversion the pack emits for a date-only column --------
    // A date-only value is site-local midnight served as a UTC instant, so
    // the offset that lands it back on midnight is the one that was in
    // force for it. Copied from `reportgen._AS_DATE_M`; a currency test
    // keeps the two the same.
    AsDateProbe = (Stamp as datetime, offsets as list) as nullable date =>
        let
            Landed =
                List.Select(
                    List.Transform(offsets, each Stamp + #duration(0, 0, _, 0)),
                    each DateTime.Time(_) = #time(0, 0, 0)
                )
        in
            if not List.IsEmpty(Landed) then DateTime.Date(List.First(Landed))
            else Date.From(Stamp),

    // Melbourne: +10 standard, +11 daylight, and zero for a value that
    // arrived already local.
    Candidates = {0, 600, 660},

    // ---- the offset lookup a declared time zone emits ----------------
    Transitions = List.Buffer({
        {#datetime(2025, 4, 5, 16, 0, 0), 600},
        {#datetime(2025, 10, 4, 16, 0, 0), 660},
        {#datetime(2026, 4, 4, 16, 0, 0), 600}
    }),
    OffsetAt = (stamp as datetime) as number =>
        let
            Before = List.Select(Transitions, each _{0} <= stamp)
        in
            if List.IsEmpty(Before) then 660 else List.Last(Before){1},

    // ---- the row-aware replace a `replace: true` column emits ---------
    ReplaceSource = #table(
        type table [A = nullable text, B = text],
        {{null, "from B"}, {"kept", "ignored"}}
    ),
    Replaced = Table.ReplaceValue(
        ReplaceSource,
        each [A],
        each if [A] = null then [B] else [A],
        Replacer.ReplaceValue,
        {"A"}
    ),

    // ---- the group and join a derived `count` emits -------------------
    Parent = #table(type table [Key = text], {{"k1"}, {"k2"}}),
    Child = #table(
        type table [ParentKey = text, Amount = number],
        {{"k1", 3}, {"k1", 5}, {"k9", 7}}
    ),
    Grouped = Table.Group(
        Child, {"ParentKey"}, {{"N", each Table.RowCount(_), type any}}
    ),
    Joined = Table.NestedJoin(
        Parent, {"Key"}, Grouped, {"ParentKey"}, "_j", JoinKind.LeftOuter
    ),
    Expanded = Table.ExpandTableColumn(Joined, "_j", {"N"}, {"N"}),
    Coalesced = Table.TransformColumns(
        Expanded, {{"N", each if _ = null then 0 else _, Int64.Type}}
    ),
    MinGrouped = Table.Group(
        Child, {"ParentKey"}, {{"Lowest", each List.Min(_[Amount]), type any}}
    ),

    // ---- the two-field record expand a projection emits ---------------
    RecordSource = #table(
        type table [Id = number, Lk = record],
        {{1, [Title = "T", Status = "S"]}}
    ),
    TwoFields = Table.ExpandRecordColumn(
        RecordSource, "Lk", {"Title", "Status"}, {"LkTitle", "LkStatus"}
    ),

    // ---- the set comparison the zone agreement check emits ------------
    SameSet = (a as list, b as list) as logical =>
        List.IsEmpty(List.Difference(a, b))
            and List.IsEmpty(List.Difference(b, a)),

    // ---- another query, read by name ---------------------------------
    // A derived lookup or count reads the target list's query exactly this
    // way. The quoted form is emitted because a bare identifier is not
    // valid for every query name.
    OtherQuery = try Table.RowCount(#"_ProbeOther") otherwise -1,

    Rows = #table(
        type table [Id = text, Question = text, Expected = text, Observed = text],
        {
            {
                "m.host.utc-now",
                "The host's UTC clock, for the record",
                "(observation)",
                DateTime.ToText(
                    DateTimeZone.RemoveZone(DateTimeZone.UtcNow()),
                    [Format = "yyyy-MM-dd HH:mm"]
                )
            },
            {
                "m.host.local-offset-hours",
                "Hours between the host's local clock and UTC. The Service "
                    & "refreshes in UTC and reports 0; a Desktop outside UTC "
                    & "does not. This row says which host produced the table",
                "(observation)",
                Text.From(DateTimeZone.ZoneHours(DateTimeZone.LocalNow()))
            },
            {
                "m.type.datetimezone-is-datetimezone",
                "`v is datetimezone` for a zoned literal. AsStamp tests this "
                    & "branch first",
                "true",
                Yn(#datetimezone(2026, 9, 3, 14, 0, 0, 0, 0) is datetimezone)
            },
            {
                "m.type.datetimezone-is-not-datetime",
                "`v is datetime` for a ZONED literal. If this is true the "
                    & "branch order in AsStamp is wrong and a zoned value "
                    & "never reaches ToUtc",
                "false",
                Yn(#datetimezone(2026, 9, 3, 14, 0, 0, 0, 0) is datetime)
            },
            {
                "m.type.datetime-is-datetime",
                "`v is datetime` for a naive literal",
                "true",
                Yn(#datetime(2026, 9, 3, 14, 0, 0) is datetime)
            },
            {
                "m.type.date-is-date",
                "`v is date` for a date literal, the third AsStamp branch",
                "true",
                Yn(#date(2026, 9, 3) is date)
            },
            {
                "m.asdate.standard-offset-lands-next-day",
                "2026-09-03T14:00Z is local midnight at +10, so the date the "
                    & "list shows is the 4th. This is the defect the fix closed",
                "2026-09-04",
                Ymd(AsDateProbe(#datetime(2026, 9, 3, 14, 0, 0), Candidates))
            },
            {
                "m.asdate.daylight-offset-lands-next-day",
                "2026-01-03T13:00Z is local midnight at +11. The SAME value "
                    & "set resolves both sides of a transition, which is why "
                    & "no transition date is needed for a date-only column",
                "2026-01-04",
                Ymd(AsDateProbe(#datetime(2026, 1, 3, 13, 0, 0), Candidates))
            },
            {
                "m.asdate.already-local-midnight-is-unchanged",
                "A calculated column arriving as a bare local midnight must "
                    & "resolve through the zero candidate and not move",
                "2026-09-04",
                Ymd(AsDateProbe(#datetime(2026, 9, 4, 0, 0, 0), Candidates))
            },
            {
                "m.asdate.nothing-lands-falls-back-to-truncation",
                "A value that is not local midnight under any candidate "
                    & "truncates, which is what this did before the zone was "
                    & "read at all",
                "2026-09-03",
                Ymd(AsDateProbe(#datetime(2026, 9, 3, 5, 30, 0), Candidates))
            },
            {
                "m.zone.offset-lookup-takes-the-last-transition",
                "An instant after the October change takes the daylight "
                    & "offset. This is SiteOffsetAt over the shipped table",
                "660",
                Text.From(OffsetAt(#datetime(2025, 12, 1, 0, 0, 0)))
            },
            {
                "m.zone.offset-lookup-before-the-first-row",
                "An instant before every row in the table takes the offset "
                    & "in force when the window opened",
                "660",
                Text.From(OffsetAt(#datetime(2024, 1, 1, 0, 0, 0)))
            },
            {
                "m.zone.set-comparison-is-symmetric",
                "The agreement check must refuse a site that reports ONE of "
                    & "the declared zone's two offsets, such as a site set to "
                    & "a neighbouring zone that has no daylight saving",
                "false",
                Yn(SameSet({600}, {600, 660}))
            },
            {
                "m.zone.set-comparison-accepts-a-match",
                "The same check on a site whose two offsets are the declared "
                    & "zone's",
                "true",
                Yn(SameSet({660, 600}, {600, 660}))
            },
            {
                "m.replace.expression-sees-the-whole-row",
                "`replace: true` computes a fallback from OTHER columns of "
                    & "the row. Table.TransformColumns would pass the value "
                    & "alone, so the emitted step uses Table.ReplaceValue",
                "from B",
                Text.From(Table.Column(Replaced, "A"){0})
            },
            {
                "m.replace.leaves-a-populated-cell-alone",
                "The same step must not overwrite a row that has a value",
                "kept",
                Text.From(Table.Column(Replaced, "A"){1})
            },
            {
                "m.count.grouped-child-joins-back",
                "A derived `count` groups the child by its key and joins the "
                    & "aggregate back onto the parent",
                "2",
                Text.From(Table.Column(Coalesced, "N"){0})
            },
            {
                "m.count.no-child-rows-coalesce-to-zero",
                "A parent with no children reads zero rather than null",
                "0",
                Text.From(Table.Column(Coalesced, "N"){1})
            },
            {
                "m.count.min-reads-a-column-of-the-group",
                "`List.Min(_[Column])` inside Table.Group, which is how the "
                    & "min, max and names aggregates read the child rows",
                "3",
                Text.From(Table.Column(MinGrouped, "Lowest"){0})
            },
            {
                "m.expand.two-fields-out-of-one-record",
                "A lookup that also projects a column takes both out of ONE "
                    & "expand, because the record is consumed by the first",
                "T|S",
                Text.From(Table.Column(TwoFields, "LkTitle"){0})
                    & "|" & Text.From(Table.Column(TwoFields, "LkStatus"){0})
            },
            {
                "m.crossquery.quoted-identifier-resolves",
                "A derived lookup or count names another query. If this "
                    & "reads -1 the second query is absent or named "
                    & "differently, and every such column fails at refresh",
                "1",
                Text.From(OtherQuery)
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
    )
in
    WithVerdict
