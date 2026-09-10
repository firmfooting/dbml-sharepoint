// dbml-sharepoint POWER QUERY PROBE (READ-ONLY, NO SITE NEEDED)
//
// The second query `m-runtime-probe.pq` reads by name. It exists only so
// that one row of that probe can ask whether a cross-query reference
// resolves, which is how every derived `lookup` and `count` reads the
// target list's query.
//
// Name this query exactly `_ProbeOther`. The name is the whole point: the
// emitted reference is `#"_ProbeOther"`, and a query loaded under any other
// name is what the failure looks like.
#table(type table [Marker = text], {{"present"}})
