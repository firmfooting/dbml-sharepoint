// dbml-sharepoint POWER QUERY PROBE (READ-ONLY, NO SITE NEEDED)
//
// `m-runtime-probe.pq` calls this by name, with an argument. It exists so
// that one row of that probe can ask whether a FUNCTION query, loaded
// under its file name and invoked from another query, resolves and runs.
// Since 2026-09-18 every derived `lookup` and `count` over another list
// calls that list's `_Base` function this way, passing the caller's own
// site root, rather than naming the list's query: two queries that name
// each other are a cyclic reference, and a function that reads nothing
// cannot be part of one.
//
// Name this query exactly `_Probe_Base`. The emitted call is
// `#"<Query>_Base"(SiteRoot)`, and a query loaded under any other name is
// what the failure looks like. Nothing here reads a site: the argument is
// echoed back so the row can see it arrived.
(SiteUrl as text) as table =>
    #table(type table [Site = text, Marker = text], {{SiteUrl, "present"}})
