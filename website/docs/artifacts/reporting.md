---
title: Reporting pack
sidebar_position: 5
---

# Reporting pack

Every build ships `build/reporting/` — the analysis surface for the
deployed lists.

## Contents

- **One Power Query (M) file per list**, plus dictionary, model-info and
  user-added-column audit queries. Point the queries' `SiteUrl`
  parameter at the deployed site and load them in Power BI or Excel.
  Each query is self-contained, including the lookup of the site's own
  display title — see below.
- **`sql/views.sql`** — a SQLCMD views script for warehouse-landed
  copies of the lists.
- **`guide.md`** — includes the Power BI relationship table
  (which columns join which lists, matching the declared lookups).
- **`data-dictionary.md`** — every list and column with types,
  descriptions and enum values, generated from the same schema the
  deploy used.

## Several sites in one report

A template is deployed one site at a time, but a report usually wants all
of them — every region, service or committee running the same lists,
sliced by site.

Every table carries **`Site Url`** and **`Site Name`** for that, and the
name is read from the site rather than configured: nothing to type in,
and a site renamed in SharePoint shows its new name at the next refresh.

Each query resolves that name itself, from whichever URL it was given —
deliberately, rather than sharing one lookup query. A shared query binds
to a single `SiteUrl`, so every copy of a list pointed at a different
site would still be stamped with the *first* site's name.

So: add one text parameter per site, duplicate each list query and change
its `SiteUrl` reference, append the copies, and build relationships on the
**`… Key`** columns. Nothing else in a duplicate needs editing — the rows,
the item links, the site name and the keys all follow that one reference.

:::warning Join on the Key columns, not on `Id`
`Id` is unique within one list on one site and nowhere wider. Append three
sites and three different rows all have `Id = 1`, so a relationship on
`Id` cannot be many-to-one — Power BI degrades it to many-to-many and
joins each child to the same-numbered parent on *every* site. The report
still renders; the numbers are wrong.

Each table exposes `<Entity> Key` (`Site Url` and the id together) and a
matching `<Target> Key` for every lookup. The relationship table in
`guide.md` already names these.
:::

## Schema-only reports

`dbml-sharepoint report` emits the same queries without needing a site
URL (layout: `powerquery/`, `sql/`, `guide.md`,
`data-dictionary.md`) — useful for warehouse or BI work that starts
before any site exists. See the [CLI reference](../reference/cli.md).
