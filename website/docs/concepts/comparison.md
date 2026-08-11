---
title: "Why not PnP, site scripts, or Graph?"
sidebar_position: 6
---

# Why not PnP, site scripts, or Graph?

Anyone who has provisioned SharePoint lists before will ask this before
evaluating this tool any further, so it is worth answering in the open
rather than in passing. Four ways to get a SharePoint Online list schema
onto a site, compared honestly: **PnP** (PnP PowerShell / PnP Framework's
provisioning engine / PnP Core SDK), **site designs and site scripts**,
**Microsoft Graph**, and this tool.

Every claim below about a competitor's capability, cost or status carries a
citation to Microsoft Learn or an official PnP source, checked while writing
this page. Two of the claims commonly repeated about site scripts — that
they cannot create Lookup columns, and that their views cannot filter — do
not hold up against the current [site template JSON
schema](https://learn.microsoft.com/sharepoint/dev/declarative-customization/site-design-json-schema);
they are corrected below rather than repeated.

## At a glance

| | PnP | Site designs / scripts | Microsoft Graph | This tool |
|---|---|---|---|---|
| Tool install required | Yes — PnP PowerShell module or PnP Framework/.NET package | No (REST) or SharePoint Online Management Shell for the PowerShell path | No (REST); optional SDKs | No — browser only |
| Admin rights required | Site-level for most templates; site collection admin for some | Yes — registering/applying a script or design is a SharePoint-admin operation | An Entra admin must consent the app's permission scope | No — runs as the signed-in operator, bounded by their own SharePoint permissions |
| App registration for unattended automation | Yes, for app-only auth (cert or secret) | Not for interactive admin PowerShell; yes for unattended REST automation | Yes, always — Graph calls require an OAuth bearer token | Never — there is no unattended mode |
| Lookup column support | Yes (CAML Field XML in the template) | Yes — dedicated `addSPLookupFieldXml` action | Yes — documented `lookup` column facet | Yes (same-site only) |
| Calculated column support | Yes (CAML Field XML) | Undocumented — no listed field type for it; only reachable, if at all, through the generic `addSPFieldXml` CAML escape hatch | Yes — documented `calculated` column facet | Yes, with a live-verified operand matrix |
| View support (filter, grouping, formatting) | Full CAML views | Filter (CAML `query`) and per-column JSON formatting; no documented grouping property | None — the `list` resource exposes no view-creation method | Full: filter, up to two-level grouping, per-column formatting, widths, totals |
| Idempotent re-run | Documented delta provisioning: reapplying updates rather than duplicates | Documented non-destructive re-run, **except** a field/column added without a pinned `id` risks re-creation on the next run | Undocumented for repeated `POST` list/column creation | Yes — read-verify-reconcile, the deployer's own design |
| Unattended CI suitability | Yes, with app-only auth | Yes, with SharePoint-admin service credentials or app-only REST | Yes — built for it | No — interactive browser-console paste, by design |
| Content-type support | Yes | Yes (`createContentType`, `addContentType`, `addContentTypesFromHub`) | Partial — `contentTypes` is a documented relationship on `list` | No — not part of this tool's model |
| Extraction from an existing site | Yes — `Get-PnPSiteTemplate` | Partial — `Get-SPOSiteScriptFromList` extracts one list, not a whole site | No comparable feature | No — schema-first, not extraction |
| Official vs. community | Community project; "no SLA for the open-source tool support from Microsoft" | Official Microsoft feature | Official Microsoft API | This project (community, MIT-licensed) |
| Maintenance status | Active, but the provisioning engine is mid-migration to PnP Core SDK (below) | Actively maintained | Actively maintained, Microsoft's primary automation surface | Active |

## PnP (PowerShell / Framework / Core SDK)

**Where it wins.** PnP's provisioning engine reads and writes a template
that covers content types, site columns, tenant-wide look-and-feel, and
**extraction from a live site** with `Get-PnPSiteTemplate` — there is no
equivalent to "point PnP at an existing site and get a template back" in
this tool, which is schema-first by design. Delta provisioning is a
documented platform feature of the engine itself: "You can apply
provisioning templates on top of existing sites. The provisioning engine
supports delta provisioning, and, as such, will add/update sites based on
whichever scope is provided" ([PnP provisioning
framework](https://learn.microsoft.com/sharepoint/dev/solution-guidance/pnp-provisioning-framework)).
With an app-only credential (certificate or client secret), it runs
unattended in CI, which this tool's browser-paste model cannot.

**What it costs.** PnP PowerShell or the PnP Framework .NET package must be
installed on the machine running it. Extracting or applying most templates
needs meaningful site-level rights, and some tenant-wide scenarios need a
site collection administrator. Unattended use needs an app registration and
a consent grant — an app-only decision to review, which this tool has no
equivalent of because it has no second identity at all. Microsoft's own docs
are explicit that this is a community tool: *"The PnP Provisioning Framework
& PnP Provisioning Engine are open-source solutions with active community
providing support for it. There is no SLA for the open-source tool support
from Microsoft"* ([Introducing the PnP provisioning
engine](https://learn.microsoft.com/sharepoint/dev/solution-guidance/introducing-the-pnp-provisioning-engine)).

**Status, re-verified for this page.** The PnP team's own roadmap post,
published 16 June 2026, states the Provisioning Engine and the Modernization
Engine are being copied into PnP Core SDK as new projects there; once that
lands, *"the Provisioning and Modernization parts of PnP Framework will be
marked as deprecated. Developers using those features will receive
deprecation warnings in their build output pointing them to the equivalent
APIs in PnP Core SDK."* The PnP Framework GitHub repository itself is
scheduled for public-archive status **in Q2 2027** — after which no
maintenance, pull requests or releases continue, though the archived code
and its NuGet packages stay available ([PnP Framework roadmap
update](https://pnp.github.io/blog/post/pnp-framework-roadmap-update-1/)).
As of this writing PnP Framework is still actively released (v1.19.0 shipped
.NET 10 support) — it is on a deprecation *path*, not deprecated yet.

## Site designs and site scripts

**Where it wins.** This is Microsoft's own no-install, no-app-registration
provisioning surface, and it is more capable than it is usually given credit
for. Its `createSPList` action supports a dedicated `addSPLookupFieldXml`
verb for Lookup columns targeting another list by name or URL, `addSPView`
accepts a CAML `query` (the filter/where clause), a row limit, paging and a
default flag, and `setSPFieldCustomFormatter` applies the same JSON column
formatting this tool emits — none of that matches the "no lookup columns, no
complex views" description sometimes repeated about site scripts, and none
of it is claimed here without the schema page itself as the source
([Site template JSON
schema](https://learn.microsoft.com/sharepoint/dev/declarative-customization/site-design-json-schema)).
Re-running a script is explicitly non-destructive at the platform level:
*"Actions can be run more than once on a site. Rerunning actions on the same
site with the same parameters will result in an update to the existing
schema and not duplication of schema"* — the platform itself owns
idempotency here, where this tool's deploy script has to implement it
itself. `Get-SPOSiteScriptFromList` extracts a script from an existing list.

**What it costs.** Registering a script (`Add-SPOSiteScript`) or applying a
design (`Invoke-SPOSiteDesign`, `Add-SPOSiteDesignTask`) is a SharePoint-admin
operation, done through the SharePoint Online Management Shell or the
matching REST calls — not something a Site Owner can do unassisted, unlike
this tool. Action counts are capped: *"We'd previously capped the limit of
site script actions to 30. This remains the limit for scripts applied
synchronously using Invoke-SPOSiteDesign... we have bumped this limit to 300
actions (or 100,000 characters) when the scripts are applied asynchronously…
There is also a limit of 100 site scripts and 100 site templates per
tenant"* ([SharePoint site template and site script
overview](https://learn.microsoft.com/sharepoint/dev/declarative-customization/site-design-overview#anatomy-of-a-site-script)) —
re-verified current for this page, matching the figures the July 2026
landscape analysis flagged for re-checking. There is no documented grouping
property on `addSPView`, and no field type is claimed for the generic
`addSPFieldXml` CAML escape hatch, so a Calculated column's support is
unstated rather than confirmed either way. The re-run guarantee has one
documented trap: an `addSPField` (or `createSiteColumn`) action without a
pinned `id` GUID is not guaranteed to be the same field on the next run — the
schema's own advice is *"Providing a value for this is recommended to ensure
the field isn't added multiple times if the script is rerun."* A script
authored without that discipline can silently duplicate columns on reapply.

## Microsoft Graph

**Where it wins.** It is the official, versioned, nationally-deployed REST
surface Microsoft is investing in across all of Microsoft 365, and it is
built for unattended automation from the ground up — a genuine strength this
tool does not have and does not try to have. Its `columnDefinition` resource
documents `lookup` and `calculated` facets directly
([columnDefinition resource
type](https://learn.microsoft.com/graph/api/resources/columndefinition?view=graph-rest-1.0)),
so both column kinds are part of the documented surface — contrary to a
claim sometimes made about Graph's list API, which is not repeated here.
Content types have a documented `contentTypes` relationship on `list`.

**What it costs.** Every call needs an OAuth bearer token, so an Entra app
registration is mandatory even for the simplest script — there is no
"already signed in" path the way there is for a browser session or an admin
PowerShell shell. Creating a list or a column needs the delegated or
application permission `Sites.Manage.All` at minimum, a broad scope an
admin must consent to
([Create a new list](https://learn.microsoft.com/graph/api/list-create?view=graph-rest-1.0),
[Create a columnDefinition in a
list](https://learn.microsoft.com/graph/api/list-post-columns?view=graph-rest-1.0)).
Most significant for this comparison: the `list` resource type's own
methods table has no view-creation method at all — `Get list`, `Create
list`, `Get items`, `List activities`, plus item/permission/operation
methods, and nothing else
([List resource type](https://learn.microsoft.com/graph/api/resources/list?view=graph-rest-1.0#methods)).
Grouping, filtered views, formatting — everything this tool's `views:`
section builds — has no Graph equivalent; you would fall back to the same
SharePoint REST view endpoints this tool itself calls. Graph also documents
no site-creation capability at all: *"Read-only support for site resources
(no ability to create new sites)"*
([Working with SharePoint sites in Microsoft
Graph](https://learn.microsoft.com/graph/api/resources/sharepoint?view=graph-rest-1.0)).
Repeated `POST` calls to create the same list or column are not documented
as idempotent the way PnP's delta provisioning or a site script's re-run
guarantee are — building safe re-runs on Graph is the caller's own
responsibility.

## This tool's own limitations

The no-admin, browser-paste model is a trade, not a free lunch — the same
honesty this page asks of the alternatives:

- **SharePoint Online only.** No on-premises SharePoint Server support.
- **Same-site lookups only.** A DBML `Ref` becomes a same-site SharePoint
  Lookup column; a cross-site relationship needs the mapping's
  `cross_site_reference_columns` pattern instead of a real Lookup. See the
  [SharePoint limits page](sharepoint-limits.md).
- **No unattended CI mode.** The deploy script is an interactive
  browser-console paste by design — that is what removes the app
  registration and the stored credential, and it is also what makes it
  unsuitable for a scheduled pipeline.
- **Clean-first-provision plus same-release resume, not a general migration
  tool.** A schema *upgrade* whose immutable shapes changed (field types,
  lookup targets, list templates) fails closed for explicit migration rather
  than attempting one.
- **No content-type support, no extraction from an existing site.** The
  schema is authored in DBML, not reverse-engineered from a live tenant.

## When this comparison should be re-evaluated

Each column above changes on its own timeline, and the honest thing is to
say what would move it:

- If **PnP Core SDK** ships a first-class, low-privilege list-provisioning
  path once the migration above completes, PnP's install/rights trade-off
  narrows.
- If **site scripts** gain a documented Calculated-column type and a
  `groupBy` property on `addSPView`, their capability gap versus this tool
  closes further than it already has.
- If **Graph** adds a view-creation endpoint to the `list` resource, its
  remaining capability gap versus this tool closes on that axis too.

None of that changes the other half of this comparison: no install, no
admin rights, and no app registration is a property of running inside an
already-authenticated browser session, not of feature parity. That half of
the trade holds regardless of what the alternatives ship next.
