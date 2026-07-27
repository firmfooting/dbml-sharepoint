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

- `where` takes the shared [condition grammar](../api/conditions.md):
  typed operators (`eq`, `neq`, `leq`, `geq`, `in`, `contains`, ...), date
  sentinels such as `today+30`, and nesting through `all_of` / `any_of` /
  `none_of`. A bare list means `all_of`, so every view written before
  nesting existed keeps working unchanged. The same grammar drives
  `form_visibility.when`, `column_validation.when` and
  `list_validation.when` — nobody writes CAML, or a formula, by hand.
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

## `form_visibility`

Which columns appear on which forms, and under what conditions.

```yaml
form_visibility:
  Risk:
    reconcile: exact            # the default — read Reconciliation below
    columns:
      SortOrder:     hidden     # never on any form
      InternalScore: hidden
      ClosureStatement:
        new: false              # not at creation…
        when:                   # …and only once it is being closed
          - { field: Status, op: eq, value: "Closed" }
      Rationale:
        when:                   # a bare list is all_of
          - { field: Decision, op: eq,  value: "Rejected" }
          - { field: Stage,    op: neq, value: "Draft" }
      Escalated:
        when:                   # groups nest
          any_of:
            - { field: Priority, op: eq,          value: "Critical" }
            - all_of:
                - { field: Priority, op: eq,          value: "High" }
                - { field: DueDate,  op: is_not_null }
```

**The `columns:` level is mandatory.** `form_visibility` → *entity* →
`columns:` → *column* → declaration. Nothing may sit beside `columns:`
except `reconcile:`; anything else is a load error.

Per column, either the string `hidden` or `visible`, or a mapping:

| Key | Type | Default | Meaning |
|---|---|---|---|
| `new` | bool | `true` | Show on the **New** form |
| `existing` | bool | `true` | Show on **existing items** |
| `when` | list or group | — | A condition tree; the column shows only when it holds |

**`existing:` governs the Display form as well as the Edit form, and the
two cannot be separated.** The modern Display form reads `ShowInEditForm`
and ignores `ShowInDisplayForm` entirely, so "readable on Display but not
editable" is not a state SharePoint has. The key is named `existing:`
rather than `edit:` for exactly that reason — a key that misleads is not
fixed by a footnote. If you need a column retired from new records but
still correctable on old ones, that is `{new: false}`, and its history
stays visible in views, item version history and the reporting bundle
regardless.

`hidden` is shorthand for `{new: false, existing: false}`. `visible` is
shorthand for everything default, and is only meaningful under
`reconcile: declared`, where it is how you clear a formula you previously
declared.

`when` uses the shared [condition grammar](../api/conditions.md) —
the same one as `views[].where`. A bare list means `all_of`; `all_of`,
`any_of` and `none_of` nest to a depth of 4 and 32 leaves.

### How it is carried

One property does all of it: `Field.ClientValidationFormula`. Per-form
gating and the `when` tree are composed into a single formula at build
time, because SharePoint gives a column exactly one of these — declaring
both without composing them would silently destroy one. The composed
formula for each column is printed in `deploy-manifest.md`, so you can read
what will be written before you paste anything.

SchemaXml's `ShowInNewForm` / `ShowInEditForm` attributes look like the
obvious mechanism and are deliberately never written. Saving the form
designer migrates them into the content type's `FieldLink.Hidden`, which
hides a column from *every* form and which REST refuses to write (*"The
type SP.FieldLink does not support HTTP PATCH method"*) — so a per-form
declaration would silently become hide-everywhere the first time anyone
opened the designer, and undoing it would need CSOM. A conditional formula
leaves the SchemaXml saying "shown", so the designer sees a ticked column
and never touches the field link.

Because every deployed column is sealed, conditional visibility **cannot be
configured by hand** on anything this tool deploys — a sealed column
discards the write silently. Declaring it is the supported route, and it is
the reproducible one.

### What the build refuses

- An unknown entity, or a column that is not a rendered column of it.
- A **calculated** column — calculated columns never appear on entry forms,
  so declaring their visibility is a mistake.
- `new: false` *and* `existing: false` combined with `when` — the column is
  hidden everywhere, so the condition can never be reached.
- A **required column with no default hidden from the New form** (`hidden`,
  or `new: false`). Every save would fail, and the build can prove it.
- A quoted boolean: `new: "false"` is a load error, not `True`.
- An operator the expression target cannot render — `measure: length`, the
  `today` sentinel, and the text operators that have not been confirmed
  against a live tenant. The
  [condition grammar reference](../api/conditions.md) has the exact
  per-target matrix, generated by running the renderers.

It **warns** — without refusing the build — when a required column with no
default carries a `when` that *may* hide it at creation. Whether the
predicate holds on the New form depends on what the person types, so the
build cannot decide it; if it can be false there, every save under that
branch fails. Give the column a default, or make the condition one that is
always true on a new item.

### Columns you cannot declare on

`Title` and the SharePoint system columns (`Created`, `Modified`,
`Author`, `Editor`, `ID`) are rejected by `form_visibility`,
`column_validation` and `column_formatting` alike:

```
form_visibility[Risk]: 'Title' cannot carry a per-column declaration — the
built-in Title column is provisioned through its own patch, so it never
receives these properties. Declaring it here would validate clean and
deploy nothing.
```

The rule is **"you cannot patch a field the deployer does not own"**, not
"system columns are off limits". Title is provisioned through its own
separate patch and the system columns are not deployed fields at all, so
in both cases the property write has nowhere to land — which used to
produce the worst available outcome: a clean build, a manifest reporting
"(none declared)", and an author believing a rule was in force.

Two places still take these columns, correctly, because they address a
field by name rather than patching a field object:

- `views[].fields` and `form_formatting` body sections.
- A `column_formatting` formatter body may **reference** `[$Created]` —
  SharePoint resolves that at render time. It just cannot be the column
  being formatted.

To change Title's label, use `display_names`.

## `column_validation`

Per-column save-time validation, with the message that column's author
actually wants shown.

```yaml
column_validation:
  Risk:
    reconcile: exact            # the default — read Reconciliation below
    columns:
      Mitigation:
        when:
          - { field: Mitigation, measure: length, op: gt, value: 10 }
        message: "Give at least a sentence — one word is not a mitigation."
      Priority:
        when:
          - { field: Priority, op: neq, value: "Unset" }
        message: "Choose a priority before saving."
```

Same two-level shape as `form_visibility`, and both `when` and `message`
are required. A rule with no message fails the save with SharePoint's
generic text, which tells the person filling in the form nothing — the
message is the feature.

`when` here states **what must be true to save**, which is the inverse of
`form_visibility.when` stating what must be true to *show*. Same grammar,
opposite polarity.

**Self-reference only.** SharePoint permits a column validation formula to
reference only the column being validated. A condition naming any other
column is a build error pointing at `list_validation:`, which is the
cross-column surface and takes the identical `when` + `message` shape.

This lands on `Field.ValidationFormula` — a different property from the
visibility formula, in a different expression language, so the two never
interfere and a column may carry both. Person, lookup, rich-text and
multi-line columns cannot be operands in a validation formula; those are
build errors naming the target.

One interaction to keep in mind: a validation rule on a column that
`form_visibility` hides from the New form still runs on create. If the rule
cannot pass with the column empty, every create fails and nobody ever sees
the message.

`Title` and the system columns are rejected here too — see
[Columns you cannot declare on](#columns-you-cannot-declare-on).

## `list_validation`

The cross-column sibling. Identical `when` + `message` shape, but the
condition may name any column on the list.

```yaml
list_validation:
  Risk:
    when:                       # if it is closed, say how it was closed
      any_of:
        - { field: Status, op: neq, value: "Closed" }
        - { field: ClosureStatement, op: is_not_null }
    message: "Closing a risk needs a closure statement."
```

That is the shape most validation rules take: an implication. *If closed,
then a closure statement is required* has no `implies` operator because it
does not need one — `if A then B` is `any_of[not A, B]`, which the grammar
already expresses.

One entity, one rule; there is no `reconcile:` here because there is
nothing to reconcile against — a list has a single `ValidationFormula`.

The raw `formula:` key is **gone**, not deprecated. It was the last place
an author wrote SharePoint syntax by hand, and so the last place the
quoting and operator differences between targets could bite them: single
quotes are rejected here and required in a visibility formula, booleans are
`AND(...)` here and `&&` there, references are `[Col]` here and `[$Col]`
there. Under the grammar none of those is an expressible mistake. Replace
a `formula:` with the equivalent `when:` tree — the loader refuses to load
the old key rather than reinterpreting it.

## Reconciliation — `reconcile:` on `form_visibility` and `column_validation`

:::danger `reconcile:` defaults to `exact`, and `exact` deletes

Per entity, `reconcile` takes `exact` (**the default**) or `declared`.

- **`exact`** — the declaration is authoritative for the **whole entity**.
  Every rendered column of that list with no entry in `columns:` has its
  formula **cleared**. Deployed state becomes a function of the
  declaration rather than of declaration history: delete an entry and the
  next deploy reverts it.
- **`declared`** — only the listed columns are touched. Anything else is
  left exactly as it is.

This is destructive by default and it is not scoped to what you declared.
The `column_validation` example above declares **two** columns of a
13-column list and clears the formula on the other **ten**.
`deploy-manifest.md` lists every one as `— cleared` before you paste
anything; read that section.

**The same key means the opposite thing under
`list_permissions`.** There, the default is `configured` — assert the
declared grants and leave everything else alone — and `exact` is the
strict mode you opt into. Here `exact` is already on. The value
vocabularies differ too (`exact` / `declared` versus `exact` /
`configured`), so nothing carries across between the two sections but the
word.

:::

`exact` is the default deliberately: every deployed column is sealed, so an
operator cannot hand-set a conditional formula on one, and the usual fear —
that exact reconciliation destroys hand-tuned configuration — is largely
fictional here. `declared` exists for mappings running
`seal_columns: false`, where that fear is real.

An entity block with an empty `columns: {}` under `exact` is legal and
meaningful: *nothing on this list is conditional* — clear every declared
column's formula.

"Every rendered column" means every column **declared in the DBML for that
entity**, not every field on the live list. Built-ins other than `Title`
(`ContentType`, `Attachments`, `Author`, `Editor` and the rest) are never
touched, and neither is any column of an entity with no block at all.
`form_visibility` also skips calculated columns, since declaring one is an
error; `column_validation` currently includes them, so a calculated column
picks up a `— cleared` line in the manifest.

One thing `exact` does **not** reach: a **deferred lookup** — a circular or
self-referencing lookup created in Phase 2 rather than Phase 1. A
declaration on one deploys correctly, but it is absent from the manifest's
Form visibility section, so the manifest under-reports what will be written.
Check the declaration itself for those columns rather than the manifest.

## Migrating from `hidden_on_forms` / `hidden_on_display`

Both keys are removed, and both are now load errors rather than silent
no-ops — a removal that failed open would have quietly made hidden columns
visible.

Each error prints the replacement block, indented and complete, including
the `columns:` level. Substitute your entity and column and it loads.

- `hidden_on_forms: {Risk: [SortOrder]}` becomes:

  ```yaml
  form_visibility:
    Risk:
      columns:
        SortOrder: hidden
  ```

- `hidden_on_display:` has **no replacement**, because it never did
  anything on a modern list. The modern Display form reads `ShowInEditForm`
  and ignores `ShowInDisplayForm`, so the old key wrote a setting, verified
  it stuck, reported success, and changed nothing anyone saw. The error
  suggests `hidden`, which removes the column from every form. If you want
  it kept on the New form, `{existing: false}` is the narrower move — and
  it still hides the column from Edit as well as Display, because those two
  cannot be separated.
- `list_validation`'s `formula:` becomes a `when:` tree; see
  [`list_validation`](#list_validation) above.

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

## Security: `permission_levels`, `groups`, `list_permissions`

Three **top-level** sections, not one nested `permissions:` block. All
three are optional; declare none of them and every list simply inherits the
site's permissions.

```yaml
permission_levels:
  - name: "Contribute No Delete"
    description: "Add and edit without delete"
    base_permissions: [ViewListItems, AddListItems, EditListItems]

groups:
  - name: "Register Editors"
    description: "People who maintain the register."
    owner_group: "Site Owners"
    allow_members_edit_membership: false
    allow_request_to_join_leave: false
    auto_accept_request_to_join_leave: false
    only_allow_members_view_membership: true
    require_empty_at_deploy: true        # optional
    enroll_operator_during_deploy: true  # optional, run-scoped

list_permissions:
  default:
    site_role: default        # which site role this default policy applies to
    break_inheritance: true
    reconcile: exact          # or configured (the default)
    assignments:
      - principal: { kind: group, name: "Register Editors" }
        level: "Contribute No Delete"
      - principal: { kind: associated_owner_group }
        level: "Full Control"
  overrides:                  # per entity; same policy shape as default
    Policy:
      break_inheritance: true
      reconcile: configured
      assignments:
        - principal: { kind: associated_member_group }
          level: "Read"
```

A `principal` is `{kind: group, name: "..."}`, or one of the three
site-relative kinds — `associated_owner_group`,
`associated_member_group`, `associated_visitor_group` — which take no
name. Every assignment needs a `level`.

`configured` mode asserts the declared grants and leaves anything else
alone; `exact` additionally **removes undeclared direct grants**, making
the declaration an allowlist. `exact` requires `break_inheritance: true` —
an inherited ACL cannot be reconciled as a list-scoped allowlist, and the
loader refuses the combination. Group owner assignment uses CSOM where REST
cannot express it.

`site_role:` is read on `list_permissions.default` only. Setting it inside
an `overrides:` entry is accepted by the loader and then discarded — an
override applies to its entity wherever that entity deploys.

:::note There was never a nested `permissions:` block

Earlier versions of this page documented `permissions:` with `levels:`,
`groups:`, `default_policy:` and `overrides:` nested underneath. Nothing in
the code ever read that key. A mapping using it built successfully and
produced a bundle byte-identical to one with no security declared at
all — inherited permissions, no group, no level, no reconciliation, and a
clean build report. It was documentation describing a design that was never
implemented.

`permissions:` is now rejected at load rather than ignored, so the failure
is loud. The keys above are the real ones, and are what every shipped
template and example uses.

:::

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
