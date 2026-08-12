---
title: Reporting pack
sidebar_position: 5
---

# Reporting pack

Every build ships `build/reporting/` — the analysis surface for the
deployed lists.

## Contents

- **One Power Query (M) file per list**, plus dictionary, model-info and
  user-added-column audit queries. Paste each one into a blank query in
  Power BI or Excel and load it — there is nothing to configure. Each
  query is self-contained, including the site it reads and the lookup of
  that site's own display title — see below.
- **`sql/views.sql`** — a SQLCMD views script for warehouse-landed
  copies of the lists.
- **`guide.md`** — includes the Power BI relationship table
  (which columns join which lists, matching the declared lookups).
- **`data-dictionary.md`** — every list and column with types,
  descriptions and enum values, generated from the same schema the
  deploy used.

## Empty lists load

The first refresh after a deploy runs against lists with no rows in them,
and a zero-row SharePoint feed comes back without the expanded person and
lookup record columns at all. Measured on a live tenant on 2026-08-11, an
unguarded expand step failed the whole query with `Expression.Error: The
column 'Owner' of the table wasn't found` — an error that names a column
and so reads as a broken query rather than an empty list, and that fixes
itself the moment anybody adds a row.

Every expand step is now guarded: the column is expanded when the record
is there and added as typed nulls when it is not, so the shape of the
table is the same either way and the rest of the query — typing, keys,
display-name renames — does not care.

## Where the site URL comes from

`build` is already told the target with `--site-url`, so it writes that
site into every query it ships. The first line of each `.pq` is the
binding:

```
let
    SiteUrl = "https://tenant.sharepoint.com/sites/YourSite",
    SiteRoot = …
```

There is no parameter to create and nothing to type in. The
`sql/views.sql` script is the same: its `:setvar SiteUrl` line already
holds the real site.

`dbml-sharepoint report` is the exception. It generates from a schema
alone and has no site to name, so its queries open with a header asking
for a *Text* parameter called `SiteUrl`, and its SQL script leaves a
`https://yourtenant.sharepoint.com/sites/YourSite` placeholder. Everything
below that first line is identical in both shapes.

### Which URL, if you are typing one

The **site** root — `https://tenant.sharepoint.com/sites/YourSite` — and
not the URL of a list, a form or a page.

This is easy to get wrong, because the address bar shows the *list* URL
(`https://tenant.sharepoint.com/sites/YourSite/Lists/YourList`) the whole
time you are looking at a list, which is exactly when you are most likely
to copy it. Pasted as `SiteUrl`, it used to build endpoints like
`.../Lists/YourList/_api/web/lists/getbytitle('YourList')/items` — the
list title twice over and `_api` hung off a list rather than a web — and
SharePoint answered `DataSource.NotFound: OData: Request failed (404)`,
which names neither the parameter at fault nor the fix.

The queries trim that back for you: each one cuts the value at the first
`/_api/`, `/_layouts/`, `/lists/` or `/sitepages/` segment and drops any
trailing `/`, so a list, form, site-page or API URL all resolve to the
same site root. A correct site URL passes through untouched, and a root
site collection (`https://tenant.sharepoint.com`, no `/sites/` segment)
is left alone rather than rejected. The `Site Url` and `… Key` columns
carry the trimmed value, so two people who pasted the same site in
different shapes still append cleanly.

The trim still runs when the URL was baked in. A URL `build` supplied is
already a site root, but that one line is now the documented place to
edit for a second site (below), so it is more likely to receive a pasted
list URL than the parameter ever was, not less.

## Several sites in one report

A template is deployed one site at a time, but a report usually wants all
of them — every region, service or committee running the same lists,
sliced by site.

Every table carries **`Site Url`**, **`Site Name`** and **`List Title`**
for that, so an appended model slices by site and by list. The site name
is read from the site rather than configured: nothing to type in, and a
site renamed in SharePoint shows its new name at the next refresh.

Each query resolves that name itself, from whichever URL it was given —
deliberately, rather than sharing one lookup query. A shared query binds
to a single `SiteUrl`, so every copy of a list pointed at a different
site would still be stamped with the *first* site's name.

So: duplicate each list query once per site, change the single
`SiteUrl = "…"` line in each copy to that site's URL, append the copies,
and build relationships on the **`… Key`** columns. Nothing else in a
duplicate needs editing — the rows, the item links, the site name and the
keys all follow that one line. (If you would rather manage the URLs in
one place, point each copy's `SiteUrl` at a per-site text parameter
instead; nothing below it cares which it is.)

:::warning Join on the Key columns, not on `Id`
`Id` is unique within one list on one site and nowhere wider. Append three
sites and three different rows all have `Id = 1` — and so do the first
rows of any two lists on a single site, because every SharePoint list
numbers its items from 1. A relationship on `Id` cannot be many-to-one —
Power BI degrades it to many-to-many and joins each child to the
same-numbered parent everywhere. The report still renders; the numbers
are wrong.

Each table exposes `<Entity> Key` — `Site Url`, the list title and the id
joined with `|` — and a matching `<Target> Key` for every lookup, spelled
with the *target's* list title so the two sides meet. The relationship
table in `guide.md` already names these.

The list *title* rather than its GUID, deliberately: a GUID would survive
a rename, but each query already addresses its list by title
(`getbytitle('<title>')`), so a rename breaks the query outright either
way. The title adds no failure mode the query does not already have, and
it saves a round trip to the site on every refresh.
:::

## Schema-only reports

`dbml-sharepoint report` emits the same queries without needing a site
URL — which is why those queries, and only those, ask for the `SiteUrl`
parameter described above (layout: `powerquery/`, `sql/`, `guide.md`,
`data-dictionary.md`) — useful for warehouse or BI work that starts
before any site exists. See the [CLI reference](../reference/cli.md).
