---
title: Mapping YAML
sidebar_position: 3
---

# Mapping reference

`mapping.yaml` owns everything physical: which DBML tables deploy where,
as what, with which views, formatting, protection and permissions.
Relative paths inside it (formatter files, `enum_sources`,
`retention_policies_source`) resolve against the mapping file's own
directory, so builds work from any working directory.

## Identity

```yaml
prefix: "APP_"
prefix_owner: "Team name"
prefix_registry: "docs/list-prefix-registry.md"
extension: null            # or an extension name (entry-point resolved)
```

Every deployed list is named `<prefix><EntityName>`. The owner and
registry fields document who claims the prefix — they are provenance,
stamped into the manifest.

## `entities`

```yaml
entities:
  Risk:   { kind: List, base_template: 100, site_role: default }
  Policy: { kind: DocumentLibrary, base_template: 101, site_role: default }
```

| Key | Meaning |
|---|---|
| `kind` | `List`, `DocumentLibrary`, or `HubOnlyList` |
| `base_template` | SP base template id (100 generic list, 101 document library) |
| `site_role` | Free label; `build --site-role X` deploys the entities labelled `X` |
| `singleton` | Optional; a one-row configuration list (enables extension seed rows) |
| `display_column` | Optional; which column represents the row in lookups |

Site roles are the multi-site story: one schema, several mappings of
entities to site types, one build per site.

## `views`

```yaml
views:
  Risk:
    - title: "Open by score"
      default: true
      fields: [Title, Category, RiskScore, Status]
      where:
        - { field: Status, op: neq, value: "Closed" }
      sort:
        - { field: RiskScore, direction: desc }
      group_by: { field: Category, collapsed: true }
      row_limit: 100
      formatting: formatting/row-extreme.json
      widths:
        Title: 280
        RiskScore: 140
```

- `where` supports typed operators (`eq`, `neq`, `leq`, `geq`, ...) and
  date sentinels such as `today+30`.
- `formatting` points at a view-level (row) formatter JSON file.
- `widths` sets pixel column widths per view (16–2000, validated against
  the view's fields). Widths are applied through SharePoint's own
  `SetViewXml` mechanism with a guarded read-splice-write — see
  [deploy.js](../artifacts/deploy.md#views).
- Views are created under a URL slug derived from the title ("Open by
  score" lives at `OpenByScore.aspx`) and renamed to the declared title,
  so view URLs never contain `%20`.
- Undeclared views are user content and are never touched.

## `display_names`

```yaml
display_names:
  mode: auto
  overrides:
    Risk:
      RiskManReference: "RiskMan Ref"
```

Internal names stay authoritative (they are what the schema, lookups
and reporting bind to); `auto` derives human display titles from
PascalCase names, with per-column overrides.

## `column_formatting`

The fleet style standard: parameterised styles that expand at build time
into SharePoint's own formatter JSON, using only documented
`sp-field-severity--*` and sanctioned Fluent classes — never raw hexes.

```yaml
column_formatting:
  Risk:
    Status:    { style: severity, map: { Open: low, Closed: good } }
    RiskScore: { style: data-bar, max: 25 }
    DueDate:   { style: overdue-date, guard: { field: Status, not: [Closed] } }
```

Available styles: `severity`, `pill`, `data-bar`, `trend`,
`overdue-date`. Semantic tokens: `good`, `low`, `warning`, `severe`,
`blocked`, `neutral`, `muted`. A bespoke formatter JSON file can be used
where a parameterised style does not fit; the validator checks either
form. The [style guide](style-guide.md) defines the tokens, icon rules
and authoring rules in full.

## `form_formatting`

```yaml
form_formatting:
  Risk:
    header: formatting/risk-form-header.json
    body:   formatting/risk-form-body.json
    # footer: optional
```

Client-form customisation (header/body/footer JSON) reconciled onto the
list's content type. The body JSON is where fields are arranged into
form sections.

## `hidden_on_forms` / `hidden_on_display`

```yaml
hidden_on_forms:
  Risk: [ResidualRiskRating]     # calculated; hidden on new/edit forms
hidden_on_display:
  Risk: [SortOrder]
```

## `list_validation`

```yaml
list_validation:
  Risk:
    formula: '=IF([Status]="Closed",NOT(ISBLANK([ClosureStatement])),TRUE)'
    message: "Closing a risk needs a closure statement."
```

Save-time enforcement, reconciled with the list like any other declared
setting.

## `calculated_formulas`

```yaml
calculated_formulas:
  Risk:
    RiskScore: "=[LikelihoodScore]*[ConsequenceScore]"
```

Formulas for `calculated_*` typed columns. SharePoint's own rules (no
Lookup/Person references, no `[Today]`) are enforced at build time.

## Structure and behaviour

```yaml
indexed_columns:
  Risk: [Status]

versioning:
  default:
    enable_versioning: true
    major_version_limit: 50
    enable_minor_versions: false
  overrides:
    Issue:                  # per entity; unlisted keys inherit the default
      major_version_limit: 25

enum_sources:            # shared enum vocabularies loaded from YAML
  risk_rating: enums/risk-rating.yaml

cross_site_reference_columns: []   # Choice + URL pattern for cross-site links
polymorphic_patterns: []           # discriminator-typed reference columns
watched_lists: []                  # lists to flag in the manifest for watching
retention_policies_source: null    # documented retention posture (manifest)
```

## Protection

```yaml
seal_columns: true            # SP.Field.Sealed on every deployed column
prevent_list_deletion: true   # AllowDeletion off on every deployed list
```

Sealing blocks UI schema edits even for admins; the deployer unseals for
its own maintenance runs and re-seals in the protection phase. Rollback
[handles both](../artifacts/rollback.md#protection-handling) without
ever stranding a lock.

## `permissions`

```yaml
permissions:
  levels:
    - name: "Contribute No Delete"
      description: "Add and edit without delete"
      base_permissions: [ViewListItems, AddListItems, EditListItems, ...]
  groups:
    - name: "Register Editors"
      description: "..."
      owner_group: "Site Owners"
      allow_members_edit_membership: false
      allow_request_to_join_leave: false
      auto_accept_request_to_join_leave: false
      only_allow_members_view_membership: true
      require_empty_at_deploy: true        # optional
      enroll_operator_during_deploy: true  # optional, run-scoped
  default_policy:
    break_inheritance: true
    reconcile: exact          # or configured (default)
    assignments:
      - { principal: { kind: group, name: "Register Editors" }, level: "Contribute No Delete" }
      - { principal: { kind: associated_owner_group }, level: "Full Control" }
  overrides: {}               # per-entity ListPermissionPolicy
```

`configured` mode asserts the declared grants; `exact` additionally
removes undeclared direct grants (an allowlist). Group owner assignment
uses CSOM where REST cannot express it.

## `demo_items`

```yaml
demo_items:
  Risk:
    - key: risk-low
      values:
        Title: "[DEMO] Local printer outage delays sign-in sheets"
        Likelihood: "Rare"
        RiskOwner: "@me"
        NextReviewDue: "today+30"
  Issue:
    - key: iss-access
      values:
        Title: "[DEMO] ..."
        RelatedRisk: { demo_ref: risk-low }
```

Value grammar:

- `"@me"` — person columns; resolves to the pasting operator.
- `"today+N"` / `"today-N"` — date columns; resolved on the day the
  demo runs.
- `{ demo_ref: key }` — lookup columns; resolves to the Id of the demo
  row created under that key.
- Anything else — a literal, validated against the column type and enum
  membership.

Every Title must start with `[DEMO] ` (validated) — the marker is the
[teardown contract](../artifacts/demo-data.md). Only emitted with
`build --seed`.

## `extensions`

```yaml
extensions:
  my_org:
    # opaque to the core; passed to the resolved extension untouched
```

Project-specific configuration for an [extension](../concepts/architecture.md#the-extension-protocol).
The core loader passes it through untyped; selection honours the
*resolved* extension (a CLI `--extension` override may differ from the
mapping's `extension:` key).
