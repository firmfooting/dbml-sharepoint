# Power Query probes

A second probe lane. The probes beside this directory are JavaScript, pasted
into a browser on a live site, and they ask SharePoint questions. These are
Power Query, loaded into Power BI, and they ask the **runtime that executes
the generated pack** questions instead.

## Why this lane exists

The reporting pack is generated M. Nothing in this repository executes M, so
every construct the generator emits is asserted by the generator and measured
by nothing. `node --check` covers the emitted JavaScript; there is no
equivalent for a `.pq` file, and a query that parses can still mean something
other than what the generator intended.

Two runtimes execute it and they are not the same. Power BI Desktop refreshes
on somebody's machine, with that machine's time zone and locale. The Power BI
Service refreshes in UTC with no machine time zone at all, which Microsoft
support has confirmed to customers is expected rather than a defect. A model
is authored in the first and lives in the second.

**So each probe is run twice**, once in Desktop and once published to the
Service, and a row that agrees in one and not the other is the finding. A
probe run only in Desktop has not measured the place the report actually
refreshes.

## The probes

| File | Needs a site | Asks |
| --- | --- | --- |
| `m-runtime-probe.pq` | no | Does the emitted M mean what the generator thinks: the type tests behind the date conversion, the offset lookup, the row-aware replace, the grouped count, the two-field expand, the set comparison, and a cross-query reference |
| `_ProbeOther.pq` | no | Nothing. It exists to be read by name, which is how a derived lookup or count reads another list's query |
| `sharepoint-feed-probe.pq` | yes | What the feed hands back through the exact call the pack makes: the shape of a date-only value, of a calculated date, of a projected dependent lookup, and whether the zone and the list's own folder read at all |

## Running them

1. Power BI Desktop, Get data, Blank query, Advanced Editor, paste the whole
   file, Done.
2. Name each query as its header says. `_ProbeOther` in particular is read by
   name, and a query loaded under a different name is the failure that row is
   looking for.
3. For `sharepoint-feed-probe.pq`, edit the five values under CONFIGURE.
   Unedited, it reads nothing and returns one row saying so.
4. Read the result table. Every row carries the value the generator assumes
   and the value the host produced. `OK` means they agree, `DIFFERS` is a
   finding, and `OBSERVED` is a row that only reports what the host is.
5. Publish the report, refresh it in the Service, and read the same table
   again.

## What comes back

Copy the table out. The probes print dates, shapes and offsets. They do not
print the site URL, a server relative path, an item title or a person, so a
pasted result carries nothing about the tenant. The folder row prints only
the last path segment, which is the list slug the pack needs and nothing
above it.

Transcripts stay untracked, like every other probe's. Quote a finding into a
dated code comment or a test rather than committing the raw table, which is
what the rest of `test/manual` does and why the tenant guard over this
directory has stayed green.

## When to run them again

Any change to the emitted M that a Python test cannot execute. The date
conversion, the derived column steps, the zone table lookup and the cross
query joins are all in that category. A generated query that passes every
gate in this repository has been proved to be the text the generator meant to
write, and nothing more.
