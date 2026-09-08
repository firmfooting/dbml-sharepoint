# Probe surfaces

The subject axis of the probe suite: what a probe is *about*. It sits beside the
mechanics axis already in `probe-catalog.json` (`harness`, `authority`, `writes`,
`cleanup`, `prerequisites`, scenario `pattern`), which says how a probe runs.
This file says what it asks.

This file is the sole authority for the surface list, the scope registries and
the check-id grammar. `dbml-sharepoint` validates its probes against it and
`dbml-sharepoint-test-agent` validates its evidence against it. Adding a scope
is a one-line edit here plus the probe change in the same commit. Adding a
surface should be rare: if a probe fits none of the twelve, that is a finding
about the map, and it is worth discussing before it is worth encoding.

**A note on the word.** `surface` here means a subject area. It does not mean
`surface_identity`, which is the per-file integrity attestation in a capture
manifest downstream, nor "evidence surface", which is one of screenshot /
accessibility snapshot / visible content. Those are always spelled in full.

## The check-id grammar

```text
<surface>.<scope>.<question>

check-id := surface "." scope "." question
surface  := one of the twelve tokens below
scope    := a token from that surface's registry
question := [ "control-" | "fixture-" ] token
token    := [a-z0-9]+ ( "-" [a-z0-9]+ )*
```

Lowercase only. Exactly two dots. Every part non-empty. Maximum 80 characters.

Reserved: `.` separates parts and may not appear within one. `-` separates words
within a part and may not lead, trail or double. `_`, `/`, `@`, whitespace and
uppercase are not permitted anywhere. `/` is reserved because it separates path
segments in a package reference; `@` is reserved because `check@role` was the
rejected form for observer role, and keeping it unusable stops it returning.

Ids are compared byte-for-byte. Nothing case-folds. There is one spelling of a
check id and it is the same string in a probe, in a machine result, in a review
and in a page slug.

The same id is used by **both lanes**. A machine result and the capture that
answers it carry one identifier, not two.

### The three parts

- **`surface`**: one of the twelve below. Fixed vocabulary.
- **`scope`**: which slot, object or mechanism within the surface. Per-surface
  registry below.
- **`question`**: what is being asked. A phrase, never a number:
  `or-chain-40`, `ampersand`, `basepermissions-readback`.

### Reserved question prefixes

- **`control-`**: this check is a control. If it fails, every check declaring a
  dependency on it is **void**, not open.
- **`fixture-`**: this check asserts the fixture was built correctly.

### The validation regex

Shared by `catalog.py`, `visible_review.py` and `check_upstream_contract.py`.
Parsing is a two-line split, which is the reason for dots over all-kebab: an
all-kebab id needs a lookup table to know where the surface ends.

```python
_CHECK_ID_RE = re.compile(
    r"^(?P<surface>[a-z][a-z0-9]*)"
    r"\.(?P<scope>[a-z0-9]+(?:-[a-z0-9]+)*)"
    r"\.(?P<question>[a-z0-9]+(?:-[a-z0-9]+)*)$"
)
```

Structural validity is not enough. `surface` must be one of the twelve and
`scope` must be in that surface's registry, both read from this file, and the
80-character maximum is checked alongside the pattern rather than inside it.

### What may never enter an id

The id names the **question**. These are facts about a *record* and belong
beside the id, never inside it:

| Fact | Where it lives |
| --- | --- |
| Which lane answered | `lanes` on the merged finding |
| Which run answered | the run directory name |
| Which capture answered | the capture directory name |
| Which identity observed | `observer_role` on the capture |
| That a capture was retaken | `superseded_by` in the run index |

A check answered as Site Owner and again as Enterprise Reader is one question
with two answers, and it is one id with two records.

## The keying rule

> **A check is keyed to the surface of its own question, not to the surface of
> its probe.**

The probe's surface decides where its *package* lives. An individual check may
file elsewhere. A reader who wants to know what is known about CAML predicates
gets the chain-depth spine, the multi-value CAML block and the datetime sentinel
queries all under `query`, without knowing that three probes touched them.

## The twelve surfaces

Reading order, roughly outward from the data model. This is also the catalogue's
sort order.

### 1. `formula`: server-evaluated expressions

Excel-like expressions the server owns the evaluation of: a calculated column's
`Formula` (refused at provisioning, computed at save) and a field's
`ValidationFormula` (refused at field-set, enforced at save). The recurring
question is which operands the server accepts, and what it does when it refuses.

Scopes: `calc`, `validation`, `datetime`, `choice`

Probes: `calculated-operand-probe.js`, `calculated-choice-operand.js`,
`hyperlink-validation-operand-probe.js`, `datetime-sentinel-probe.js`,
`today-semantics-probe.js`, `modified-clock-probe.js`,
`list-modified-clock-probe.js`, `form-validation-probe.js`,
`save-instant-paths-probe.js`, `today-source-probe.js`

### 2. `expression`: client-evaluated expressions

Expressions the browser evaluates when a form renders:
`ClientValidationFormula`, and the JSON expressions that drive conditional field
display. Same syntax family as `formula`, different evaluator, different failure
mode: silently inert instead of a save-time refusal.

Scopes: `client-validation`, `conditional-display`

Probes: `expression-text-operators-probe.js`,
`form-visibility-evidence-probe.js`

> **The distinguishing test.** *Which evaluator owns the language?* The server
> owns `formula`: it refuses at provisioning, field-set and save. Only the
> browser owns `expression`, and the server never parses it. This is the only
> surface boundary that needs an explicit tie-breaker; the rest separate on
> subject matter. The empirical discriminator is the `person-operand` pair,
> `formula.validation.person-operand` against
> `expression.client-validation.person-operand`, and the same pair for
> `lookup-operand`: the same Person and Lookup columns are refused by
> `ValidationFormula` and accepted by `ClientValidationFormula` in the same run.

#### Settled

The parallel investigation confirmed the split. `Formula` and
`ValidationFormula` are evaluated by the server (provisioning refusal, field-set
refusal, save-time enforcement); `ClientValidationFormula` is evaluated only by
the browser. The boundary holds on the "which evaluator owns the language" test,
not on "when is it evaluated", which was false for `Formula` (refused at
provisioning, before any item exists) and incomplete for `ValidationFormula`
(five of six refusal rows are set-time). Nothing relocates.

### 3. `query`: predicates that select rows

CAML and OData: which items come back. Chain depth, operator support, predicates
over awkward column types, ad-hoc query versus stored query. About the *rows
returned*, not the view object that stores the predicate.

Scopes: `caml`, `caml-adhoc`, `view-query`, `odata`

Probes: `caml-chain-depth-probe.js`

### 4. `view`: the `SP.View` object and its rendered page

The stored query's survival across a resave, aggregations and totals, the filter
editor UI, what the view page renders. About the *container*, where `query` is
about the *result*.

Scopes: `filter-editor`, `totals`, `view-page`, `threshold-render`

Probes: `view-aggregations-probe.js`, `view-edit-page-probe.js`

### 5. `form`: New / Edit / Display forms

Which store decides that a column appears on a form, and whether the several
stores (field schema attributes, content-type field links, form layout) agree.
Not about validating what is typed in; that is `expression`.

Scopes: `new-form`, `edit-form`, `display-form`, `field-links`, `panel`

Probes: `form-visibility-probe.js`, `form-visibility-storage-probe.js`,
`form-visibility-interactive.js`

### 6. `field`: column provisioning, typing and item round-trip

Creating a column of a given type and getting a value into and out of an item
intact. Multi-value columns, lookups and their projected columns.

Scopes: `multichoice`, `multilookup`, `lookup`, `person`, `note`, `date`,
`boolean`, `title` (the built-in Title column, which the tool never creates),
`list` (the list object the columns belong to)

Probes: `multi-value-probe.js`, `projected-lookup-probe.js`,
`date-storage-probe.js`, `multilookup-probe.js`, `list-settings-probe.js`,
`lookup-showfield-probe.js`, `boolean-field-probe.js`,
`title-rename-probe.js`, `title-seal-probe.js`

### 7. `text`: does a string survive a write and read back byte-identical

Descriptions, titles, validation messages, formatter JSON and XML bodies. Every
check is the same shape (write a string with an awkward character or an awkward
length, read it back, compare), but the *slot* matters, because these results
are famously not transferable between slots. That is what `scope` is for.

Scopes: `list-desc`, `group-desc`, `role-desc`, `col-desc`, `field-title`,
`view-title`, `valmsg`, `view-fmt`, `col-fmt`, `form-fmt`

Probes: `list-description-probe.js`, `group-description-probe.js`,
`role-definition-probe.js`, `formatter-xml-probe.js`

### 8. `access`: identities, groups, permission levels, ACLs

Role definitions and their base permissions, group membership, resolving a name
to a principal, effective permissions, per-item and per-list ACLs, what a
permission level can actually do.

Scopes: `role-def`, `role-binding`, `built-in-level`, `group`, `principal`,
`item-acl`, `list-acl`, `lookup-acl`, `effective-perms`

`built-in-level` is separate from `role-def` because the question is not what a
role definition can hold but whether the platform defends the six it ships.

Probes: `enterprise-reader-probe.js`, `reader-bindings-probe.js`,
`built-in-levels-probe.js`, `lookup-acl-probe.js`,
`siteuserinfolist-probe.js`

### 9. `scale`: behaviour at and beyond the list view threshold

The 5000-item threshold, indexes, index-guarded queries, join limits. Distinct
from `query` because the question is not "does this predicate select the right
rows" but "does it run at all at size".

Scopes: `threshold`, `index`, `native-idx`, `join`

Probes: `threshold-index-probe.js`, `native-index-probe.js`

### 10. `search`: the search index as a discovery surface

Crawl latency, managed properties, what is discoverable through search that is
not discoverable through the list API.

Scopes: `crawl`, `managed-prop`, `discovery`

Probes: `search-discovery-probe.js`

### 11. `library`: document libraries

Where a library's behaviour diverges from a generic list: files versus items,
what a file is made of over REST, and how metadata columns and list validation
behave on libraries.

Scopes: `doc-lib`, `file-vs-item`, `file`, `column`, `validation`,
`folder`, `content-type`, `form`, `view`, `formula`, `access`, `query`,
`field`, `search`, `index`, `lookup`, `large-list`

Probes: `document-library-probe.js`, `file-operations-probe.js`,
`library-columns-probe.js`, `folder-probe.js`, `library-content-type-probe.js`,
`library-column-interactions-probe.js`, `library-form-probe.js`,
`library-view-probe.js`, `library-formula-probe.js`, `library-access-probe.js`,
`library-query-probe.js`, `library-field-probe.js`,
`library-view-search-probe.js`, `library-index-probe.js`,
`cross-lookup-probe.js`, `library-index-threshold-probe.js`,
`library-grouping-probe.js`, `library-nesting-probe.js`,
`library-view-interaction-probe.js`, `library-large-list-fixture-probe.js`,
`library-large-list-index-probe.js`, `library-large-list-calculated-probe.js`,
`library-large-list-group-view-probe.js`,
`library-large-list-multilevel-group-view-probe.js`,
`library-large-list-preindex-fixture-probe.js`,
`library-large-list-preindex-group-view-probe.js`,
`library-large-list-modern-view-probe.js`

`index` is the newest scope and it is a divergence question, which is what
qualifies it for `library` rather than for `scale`. `scale.index` holds what a
GENERIC LIST does with `SP.Field.Indexed`: `threshold-index-probe.js` measured
that a MERGE of `Indexed: true` is accepted there and reads back true, on Text,
Choice, Person and Lookup columns alike. `library.index` asks whether a
document library answers the same, by the same method, and whether it reaches
the two columns a library has that a list does not name the same way,
`FileLeafRef` and `Title`. The question is worth its own scope because
`templates/deploy/_indexes.js.j2` sends the flag to a library exactly as it
sends it to a list, and verifies the write by reading the field's IDENTITY
rather than its `Indexed` value, so a library that accepts the flag and drops
it passes every deploy phase.

`lookup` is the newest scope and it is about a lookup that CROSSES the two
container kinds, in either direction. `field.lookup` holds what a lookup does
when both ends are generic lists: `projected-lookup-probe.js` measured creation
and projection there, `multilookup-probe.js` the multi-value form. A lookup
whose target is a document library points at rows that are FILES, and a lookup
held on a document library sits on a container whose rows cannot be created by
an item POST at all, so neither is the same question as `field.lookup` and
neither is answered by it. The scope is on `library` rather than on `field`
because the subject is the divergence between the containers, which is the
keying rule applied: a reader asking what is known about libraries should find
both directions without knowing which probe measured them.

`large-list` is about ENUMERATING a document library that holds more than 5,000
rows: what a query, a view, a page and a folder scope return when the container
is past the list view threshold. That is a different subject from `library.index`,
which asks whether a library carries `SP.Field.Indexed` on a given column, and
from `scale.threshold`, which holds what a GENERIC LIST does past the same
figure. The scope was added with `library-large-list-fixture-probe.js`, which
answers nothing and builds the permanent library the enumeration probes read:
its library name, target list name, column names, file names and value formulas
are a contract, and a probe reading that fixture files its rows here.

`library-large-list-index-probe.js` files its INDEX questions here rather than
under `library.index` for the same keying reason. `library.index` holds whether
a library accepts `SP.Field.Indexed` at all, measured on a small library it
creates for itself. The questions here are what an index does once the
container is past the threshold: whether the write is still accepted at that
size, and whether it turns a refused filter or sort into an answered one. The
subject is the threshold, the evidence is the shared fixture, and a reader
asking what is known about a library past 5,000 rows should find it without
knowing which of the two scopes the write half belongs to.

`library-large-list-calculated-probe.js` files here for the same reason, and it
reuses four of that probe's ids rather than minting its own:
`fixture-library-present`, `control-id-query-served`,
`control-absent-column-refused` and `control-unindexed-filter-refused` are the
same questions by the same method against the same fixture, so they are one id
with two records. `index-calculated-column` is reused for the same reason and is
a confirmation rather than a discovery: #478 recorded the flag as refused on a
calculated column, and the four questions after it are only worth reading if that
refusal still holds when they are asked. `control-id-query-served` is answered
there in two shapes, a filter and a sort, and here in the filter shape only,
because nothing in this probe sorts.

`library-large-list-group-view-probe.js` files here for the same reason and
reuses seven ids, including one that changes role. `fixture-library-present`,
`fixture-index-flags-clear`, `control-id-query-served`,
`control-absent-column-refused`, `control-unindexed-filter-refused`,
`control-missing-group-column-ungrouped` and `index-choice-column` are the same
questions by the same method against the same fixture, so they are one id with
more than one record. `control-group-by-single-value-column` is the one that
changes role: in the calculated probe it is an instrument, and its refusal is
what stopped that probe attributing anything to the column being calculated,
which makes the unindexed group-by throttle this probe's SUBJECT. So the id
appears in this probe's findings and NOT in its scenario controls, and no check
here declares a dependency on it. A control voids what depends on it; a subject
that comes back refused is a result, and the two must not be spelled the same
way. The keying rule is what holds them together: one question takes one id
however many probes ask it, and the role a check plays is a property of the
probe rather than of the question.

`library-large-list-multilevel-group-view-probe.js` re-opens what that probe
left unsettled and reuses thirteen ids, one of which changes role for the second
time. #480 waited about a minute for the index on the Choice column to lift the
group-by, and recorded its own result as not conclusive because SharePoint
builds the index behind the flag. So the reused ids are the whole instrument
frame: `fixture-library-present`, `fixture-index-flags-clear`,
`control-id-query-served`, `control-absent-column-refused`,
`control-unindexed-filter-refused`, `control-render-where-absent-refused`,
`control-missing-group-column-ungrouped`, `control-choice-description-sticks`,
`control-choice-unknown-property-refused`, `index-choice-column`,
`index-number-column` and `index-date-column`, each the same question by the
same method against the same fixture.
`control-group-by-single-value-column` is a SUBJECT here as it is in #480, for
the same reason and with nothing declaring a dependency on it: it is the
unindexed before half the generous wait is compared against.
`multilevel-group-by-unindexed` is a subject on the same argument, even though
the authoring brief called it a negative control. A control that fails voids
what depends on it, and a group-by refused at this size is the result this
probe went looking for, so spelling it as a control would make the finding
indistinguishable from a broken instrument. What the probe does take as a
control instead is `control-multilevel-group-by-narrowed-honoured`: a `<GroupBy>`
carrying three `<FieldRef>` children is a shape no probe in this repository had
sent, so it is proved over an `Id`-narrowed row set, where #480 measured the
single-level version honoured and where the threshold cannot reach it. Without
that control a refusal at full size could be the shape rather than the size, and
the three ids that would then be misread declare a dependency on it.

`library-large-list-preindex-fixture-probe.js` files here and mints its own ids
rather than reusing any of that frame, because it reads a DIFFERENT library.
Every index this repository has measured past the threshold was written after
the container was already past it, and the guidance an operator meets says to
index before the container grows past 5,000. So the probe builds a second
permanent library, `dbmlsp Probe PreIndex`, whose group-by column is indexed
while it holds 4,900 files and which is then topped up to 5,100. Its rows all
carry the `preindex-` stem for that reason: `fixture-preindex-columns-created`
and `fixture-preindex-file-count` are the same shape of question as the first
fixture probe's, asked against a different library, and the keying rule makes
that a new id rather than a second record. The one id it does reuse is
`library.doc-lib.fixture-library-created`, because creating a document library
is the same question by the same method whichever library it creates.
`fixture-preindex-index-written-under-threshold` is the row the probe exists
for, and it is the one that cannot be re-observed: the build takes about six
pastes and only one of them writes the index, so that pass stamps the observed
file count and an ISO timestamp into the column's own `Description` and every
later pass reports the row by quoting the stamp. A column reading
`Indexed=true` with no stamp is reported open, because the flag alone is
equally consistent with a write at 4,900 files and one at 5,099.

`library-large-list-preindex-group-view-probe.js` changes the FIXTURE rather
than the query. #481 settled that a column indexed while its library was already
past 5,000 files serves a filter and does not serve a group-by, in the same pair
of requests, for as long as it is asked. The guidance an operator meets says to
index before the library passes 5,000, so this probe reads a second permanent
library, `dbmlsp Probe PreIndex`, whose Choice column was indexed at 4,900 files
and carried past the threshold, and sends #481's queries at it. It reuses six
ids. `fixture-preindex-index-written-under-threshold` and
`fixture-preindex-witness-unindexed` come from
`library-large-list-preindex-fixture-probe.js`, which builds that library and
stamps the count and the moment of the index write into the column's
Description, because `Indexed=true` seen by a later pass cannot say WHEN it was
written and when is the entire subject. `control-id-query-served`,
`control-absent-column-refused`, `control-unindexed-filter-refused`,
`control-render-where-absent-refused` and `control-missing-group-column-ungrouped`
are the same questions by the same method, asked of the second library, and
`group-by-native-index-column` is #480's subject asked there too. What is NOT
reused is `fixture-library-present`: the equivalent row is
`fixture-preindex-library-present`, because a different library is a different
question and a reader must not have to work out which fixture a record came
from. `control-preindex-filter-serves` and
`control-preindex-group-by-narrowed-honoured` are new for the same reason, and
the second one is the instrument: a single-level `<GroupBy>` proved over an
`Id`-narrowed row set on THIS library, since the column names and the build
differ from the fixture #480 measured that composition on.
`preindex-group-by-unindexed-column` is a SUBJECT and not a control, on the
argument #480 and #481 already made: a group-by refused at this size is the
result three probes have now recorded, so spelling it as a control would make
the finding indistinguishable from a broken instrument.

`library-large-list-modern-view-probe.js` changes the LAYER rather than the
fixture or the query. Everything above measures REST: an OData `$filter` and a
`<GroupBy>` sent through `RenderListDataAsStream`. This probe reads the modern
document library page rendering the same views in a browser, on the same
`dbmlsp Probe PreIndex` library, because the effective threshold Microsoft
documents for the modern experience is higher than the 5,000 the query surfaces
enforce. Its questions take the `ui-` stem under `large-list` rather than a
`ui` scope of their own: the subject is still enumerating a document library
past the list view threshold, and the grammar allows exactly two dots, so the
layer belongs in the question rather than in a third part. Three ids are reused
from the fixture probe, `fixture-preindex-library-present`,
`fixture-preindex-index-written-under-threshold` and
`fixture-preindex-witness-unindexed`, since the fixture and the method are the
same. `control-ui-modern-renders-below-threshold` is the row the rest depends
on: `view-aggregations-probe.js` provisions its fixture classic and records
that the modern list web part does not render under the capture browser, so a
blank grid past 5,000 and a capture lane that renders nothing produce the same
screenshot. Reading the same instrument on a library UNDER the threshold is
what separates them, and every rendered row is void rather than open when it
fails. `ui-group-by-unindexed-column-renders` is a witness with nothing
depending on it, because the unindexed column holds a thousand distinct values
over 5,100 files and a refusal there is not attributable to the missing index
alone. `ui-group-by-indexed-column-folder-scoped` is registered and recorded
open: it needs a folder holding fewer than 5,000 files inside a library holding
more than 5,000, and neither permanent fixture has one. Adding a folder to
either would break the `$orderby=Id desc&$top=1` resume read both fixture
probes fail closed on, so answering it needs a large library built with
folders, which is a fixture probe rather than a change to this one.

`search` holds one probe. That is the map doing its job, not a flaw to tidy away
by merging it into something larger: a surface holding one probe is the statement
that the surface is almost entirely unprobed. `library` was in that position
until `file-operations-probe.js`, `library-columns-probe.js`, `folder-probe.js`,
and `library-content-type-probe.js`, the four probes taking it out.

### 12. `transport`: how requests are delivered and throttled

The HTTP transport the emitted scripts ride on: OData `$batch` multipart
encoding and whether batching is counted per request or per operation, how
throttling is signalled (429/503 status versus a redirect to
`/_layouts/15/Throttle.htm`), and `Retry-After` presence.

Scopes: `batch`, `throttle`, `retry`

Probes: `throttle-batch-probe.js`, `batch-field-create-probe.js`

## Checks that file under a different surface than their probe

Applying the keying rule. Every straddle named in the mapping resolves here.

| Probe | Probe surface | Checks | File under |
| --- | --- | --- | --- |
| `caml-chain-depth-probe.js` | `query` | the ten `-editable` shape checks, `readonlyview-*`, `edit-page-*`, `ui-chain-40` (was `E*`, `P*`, `R*`, `T2`, `U2`, `W2`, `W4`, `G*`) | `view.filter-editor.*` |
| `caml-chain-depth-probe.js` | `query` | `chain-40-rows-listed` (was `U1`) | `view.view-page.*` |
| `calculated-choice-operand.js` | `formula` | `person-operand`, `lookup-operand` (was `P2`, `L3`) | `expression.client-validation.*` |
| `datetime-sentinel-probe.js` | `formula` | `control-real-element-selects`, `bogus-element-accepted`, `now-element-*`, `today-element-*`, `today-include-time-*` (`CN` retired, `C1`–`C7`) | `query.caml.*`, `query.caml-adhoc.*`, `query.view-query.*` |
| `datetime-sentinel-probe.js` | `formula` | `now-sentinel-stored` (was `E1`) | `expression.client-validation.*` |
| `multi-value-probe.js` | `field` | `multichoice-eq`, `multichoice-contains`, `multichoice-includes`, `multichoice-notincludes` and the rest of the ad-hoc predicates (was `C1`–`C7`, `C9`–`C13`) | `query.caml-adhoc.*` |
| `multilookup-probe.js` | `field` | the fifteen `multilookup-*` predicate checks, asking what each CAML operator returns over a multi-value lookup | `query.caml-adhoc.*` |
| `multilookup-probe.js` | `field` | `control-ceiling-small-list`, `multi-value-lookup-costs-a-join` | `scale.join.*` |
| `multi-value-probe.js` | `field` | `multichoice-membership-selects`, `multichoice-chain-selects` (was `C8`, `C14`) | `query.view-query.*` |
| `multi-value-probe.js` | `field` | `multichoice-operand` (was `V1`) | `formula.validation.*` |
| `multi-value-probe.js` | `field` | `operand-multichoice` (was `F1`) | `formula.calc.*` |
| `lookup-acl-probe.js` | `access` | `calculated-display-field`, `empty-label-linked-readback`, `picker-omits-empty-label` (was `K5`–`K7`) | `field.lookup.*` |
| `role-definition-probe.js` | `text` | `basepermissions-readback`, `getbyname-absent-status`, `web-assignments-enumerable` (was `R7`–`R9`) | `access.role-def.*` |
| `threshold-index-probe.js` | `scale` | `indexed-filter`, `indexed-filter-guarded`, `unindexed-filter`, `unindexed-filter-guarded` (was `VWIDX`, `VWGRD`, `VWUNI`, `VWUGD`) | `view.threshold-render.*` |
| `threshold-index-probe.js` | `scale` | `plain-clause-rows`, `negated-clause-rows` (was `EDTPLN`, `EDTNEG`) | `view.filter-editor.*` |
| `search-discovery-probe.js` | `search` | `continuation-link-emitted`, `continuation-link-followed` (was `S11`, `S12`) | `query.odata.*` |
| `view-edit-page-probe.js` | `view` | `guarded-single-clause-inert`, `tautology-alone-partitions` (was `S1`, `S2`) | `query.caml.*` |
| `view-edit-page-probe.js` | `view` | `guarded-single-clause-stored` (was `Q1`) | `query.view-query.*` |
| `siteuserinfolist-probe.js` | `access` | `system-columns-item-shape` | `field.person.*` |
| `today-source-probe.js` | `formula` | `profile-regional-settings` | `access.principal.*` |
| `today-source-probe.js` | `formula` | `today-element-*`, `today-offset-element-*`, `today-include-time-*` | `query.caml-adhoc.*` |
| `today-source-probe.js` | `formula` | `dynamic-default-rest-fill` | `field.date.*` |
| `save-instant-paths-probe.js` | `formula` | `hidden-list-readback` | `field.list.*` |
| `list-settings-probe.js` | `field` | the thirteen `*-sticks` rows measured on the document library, with that container's fixture, its two controls and its property enumeration | `library.doc-lib.*` |
| `list-settings-probe.js` | `field` | `read-security-on-list`, `write-security-on-list`, `read-security-on-library`, `write-security-on-library`, because item-level permission trimming is an access question wherever it is set | `access.item-acl.*` |
| `cross-lookup-probe.js` | `library` | `control-list-lookup-ceiling`, `library-lookup-ceiling`, `list-to-library-costs-a-join`, because a ceiling on how many lookups one view may project is a join question whichever container holds them | `scale.join.*` |

Some probes cross a *scope* boundary within their own surface rather than a
surface boundary, and are listed for the same reason:

| Probe | Checks | File under |
| --- | --- | --- |
| `list-description-probe.js` | the `group-description-512-ceiling` header finding | `text.group-desc.ceiling-512` |
| `formatter-xml-probe.js` | `width-attribute` (was `D_WIDTH`) | `text.col-fmt.width-attribute` |
| `multilookup-probe.js` | `source-index-carry`, asked of a SINGLE-value lookup over an indexed source | `field.lookup.source-index-carry` |
| `calculated-choice-operand.js` | `lookup-operand-accepted`, `control-person-operand-refused` (was `L1`, `N1`) | `formula.calc.*` |
| `calculated-choice-operand.js` | `person-operand`, `lookup-operand` (was `P1`, `L2`) | `formula.validation.*` |
| `datetime-sentinel-probe.js` | the four `*-quote-literal` questions (was `Q1`–`Q4`) | `formula.validation.*` |
| `native-index-probe.js` | `odata-comparison-found-list`, `odata-null-found-list` (was `CMPIDX`, `NULIDX`) | `scale.index.*` |
| `file-operations-probe.js` | `fixture-library-created`, its own library-creation control | `library.doc-lib.*` |
| `library-columns-probe.js` | `fixture-library-created`, its own library-creation control | `library.doc-lib.*` |
| `folder-probe.js` | `fixture-library-created`, its own library-creation control | `library.doc-lib.*` |
| `library-content-type-probe.js` | `fixture-library-created`, its own library-creation control | `library.doc-lib.*` |
| `library-column-interactions-probe.js` | `fixture-library-created`, its own library-creation control | `library.doc-lib.*` |
| `library-form-probe.js` | `fixture-library-created`, its own library-creation control | `library.doc-lib.*` |
| `library-index-probe.js` | `fixture-library-created`, its own library-creation control | `library.doc-lib.*` |
| `cross-lookup-probe.js` | `fixture-library-created`, its own library-creation control | `library.doc-lib.*` |
| `library-index-threshold-probe.js` | `fixture-library-created`, its own library-creation control | `library.doc-lib.*` |
| `library-grouping-probe.js` | `fixture-library-created`, its own library-creation control | `library.doc-lib.*` |
| `library-nesting-probe.js` | `fixture-library-created`, its own library-creation control | `library.doc-lib.*` |
| `library-nesting-probe.js` | `control-missing-group-column-ungrouped` and `control-group-by-single-value-column`, the two grouping controls its folder-depth rows rest on, kept under the ids `library-grouping-probe.js` registers for the same questions by the same method | `library.view.*` |
| `library-view-interaction-probe.js` | `fixture-library-created`, its own library-creation control | `library.doc-lib.*` |
| `library-large-list-fixture-probe.js` | `fixture-library-created`, its own library-creation control | `library.doc-lib.*` |
| `library-large-list-preindex-fixture-probe.js` | `fixture-library-created`, its own library-creation control | `library.doc-lib.*` |

`list-description-probe.js` is the instructive one. Its header today carries
`// finding: group-description-512-ceiling`, a finding about a group description
recorded inside the list-description probe. Under the keying rule that is not an
anomaly needing explanation. It is `text.group-desc.ceiling-512`, filed under
the slot it is about, discovered by whichever probe happened to hit it.

## Two subjects, two methods, two ids

Where two probes examine the same subject by different methods, the methods are
different questions and take different ids. They do not merge.

| Subject | Method | Id |
| --- | --- | --- |
| Is `Created` natively indexed | read the `Indexed` property | `scale.native-idx.created-property` |
| Is `Created` natively indexed | filter on it past the threshold | `scale.native-idx.created-threshold-filter` |
| OData comparison on an indexed column past the threshold | a fixture the probe built and indexed itself | `scale.index.odata-comparison-indexed-text` |
| OData comparison on an indexed column past the threshold | whichever list this web already had | `scale.index.odata-comparison-found-list` |
| Is a tautology inert as a right-hand conjunct | one clause beside it, on a three-row list | `query.caml.guarded-single-clause-inert` |
| Is a tautology inert as a right-hand conjunct | a twelve-clause chain, past the threshold | `query.caml.tautology-conjunct-inert` |
| Does the tautology alone return every row | a three-row list, where "every" is countable by eye | `query.caml.tautology-alone-partitions` |
| Does the tautology alone return every row | a forty-eight-member list built for the chain | `query.caml.tautology-always-true` |
| Does a multi-value lookup carry its source's index | the column existed before the source was indexed | `field.multilookup.source-index-carry` |
| Does a multi-value lookup carry its source's index | the column was created after the source was indexed | `field.multilookup.source-index-carry-at-create` |
| How many lookups can one view project | a 6,000-row fixture, past the item threshold | `scale.join.lookup-column-ceiling` |
| How many lookups can one view project | a four-row list, nowhere near the threshold | `scale.join.control-ceiling-small-list` |
| Does `Indexed: true` stick on a text column | on a generic list, beside a 6,000-row fixture the index is then exercised against | `scale.index.indexed-autoindexed-flags` |
| Does `Indexed: true` stick on a text column | on a document library, the flag alone, with no threshold fixture behind it | `library.index.text-column-indexed` |
| How many lookups can one view project | a one-item list, as the baseline the library is compared against | `scale.join.control-list-lookup-ceiling` |
| How many lookups can one view project | a document library, through the same walk on the same fixture | `scale.join.library-lookup-ceiling` |
| Is a lookup created and bound by `createfieldasxml` | both ends generic lists | `field.lookup.control-primary-lookup-created` |
| Is a lookup created and bound by `createfieldasxml` | the column is held by a document library | `library.lookup.library-to-list-created` |
| Is a lookup created and bound by `createfieldasxml` | the target is a document library | `library.lookup.list-to-library-title-created` |
| Does a view group by folder | `<FieldRef Name="Folder"/>` on a library holding one folder at the root | `library.view.group-by-folder` |
| Does a view group by folder | the parent-folder column, on a library holding a folder three deep | `library.folder.group-by-path-depth` |
| Is a group-by honoured on a single-value column | a library holding a handful of files | `library.view.control-group-by-single-value-column` |
| Is a group-by honoured on a single-value column | the shared fixture, past the list view threshold | `library.large-list.control-group-by-single-value-column` |
| Is a group-by naming an absent column ignored | a library holding a handful of files | `library.view.control-missing-group-column-ungrouped` |
| Is a group-by naming an absent column ignored | the shared fixture, past the list view threshold | `library.large-list.control-missing-group-column-ungrouped` |
| Does a Description MERGE stick on a library column | a text column, as the control for indexing seven columns | `library.large-list.control-description-sticks` |
| Does a Description MERGE stick on a library column | the calculated column itself, whose index refusal it is the control for | `library.large-list.control-calculated-description-sticks` |
| Is an unknown `SP.Field` property refused | sent at a text column | `library.large-list.control-unknown-property-refused` |
| Is an unknown `SP.Field` property refused | sent at the calculated column, where a MERGE may not arrive at all | `library.large-list.control-calculated-unknown-property-refused` |
| Does a Description MERGE stick on a library column | the Choice column, whose index write the group-view probe rests on | `library.large-list.control-choice-description-sticks` |
| Is an unknown `SP.Field` property refused | sent at the Choice column, in the same run that indexes it | `library.large-list.control-choice-unknown-property-refused` |
| Is a query naming a column the library does not hold refused | an OData `$filter`, the surface that reports the threshold as an error | `library.large-list.control-absent-column-refused` |
| Is a query naming a column the library does not hold refused | a `<Where>` through `RenderListDataAsStream`, the surface a `<GroupBy>` lives on | `library.large-list.control-render-where-absent-refused` |
| Does an index let a group-by through past the threshold | `Id`, the one natively indexed column, with no write at all | `library.large-list.group-by-native-index-column` |
| Does an index let a group-by through past the threshold | a Choice column, measured before and after the probe indexes it | `library.large-list.group-by-indexed-column` |
| Does an index let a group-by through past the threshold | the same Choice column, re-sent for minutes rather than for one, with the filter on it interleaved | `library.large-list.group-by-indexed-column-generous-wait` |
| Does an index let a group-by through past the threshold | three columns and a three-level `<GroupBy>`, each index waited out | `library.large-list.multilevel-group-by-indexed` |
| Is a group-by honoured on a single-value column | three columns at once, unindexed, past the list view threshold | `library.large-list.multilevel-group-by-unindexed` |
| Does a Description MERGE stick on a library column | the pre-index fixture's Number column, chosen because the Choice column's Description carries that fixture's one durable piece of evidence | `library.large-list.control-preindex-description-sticks` |
| Is an unknown `SP.Field` property refused | sent at the pre-index fixture's Number column | `library.large-list.control-preindex-unknown-property-refused` |
| Is `Indexed=true` accepted on a library's Choice column | written past the list view threshold, on a library already holding 5,500 files | `library.large-list.index-choice-column` |
| Is `Indexed=true` accepted on a library's Choice column | written BELOW the threshold, on a second library holding 4,900 files, which is the ordering the index guidance names | `library.large-list.fixture-preindex-index-written-under-threshold` |
| Does a library hold the file count its fixture contract names | the shared fixture, 5,500 files indexed after crossing | `library.large-list.fixture-file-count` |
| Does a library hold the file count its fixture contract names | the pre-index fixture, 5,100 files indexed before crossing | `library.large-list.fixture-preindex-file-count` |
| Does an index let a group-by through past the threshold | a Choice column indexed BEFORE its library passed 5,000 files, on a second fixture built for the ordering | `library.large-list.preindex-group-by-indexed-column` |
| Does the filter serve while the group-by on the same column is refused, in one pair of requests | the index written after the library passed 5,000 files | `library.large-list.indexed-filter-serves-while-group-by-refused` |
| Does the filter serve while the group-by on the same column is refused, in one pair of requests | the index written before it | `library.large-list.preindex-filter-serves-while-group-by-refused` |
| Is a single-level `<GroupBy>` honoured over an `Id`-narrowed row set | on the fixture whose columns are indexed by the probe that reads it | `library.large-list.filtered-group-by-past-threshold` |
| Is a single-level `<GroupBy>` honoured over an `Id`-narrowed row set | on the fixture that arrives indexed, whose column names and build differ | `library.large-list.control-preindex-group-by-narrowed-honoured` |
| Is the fixture library present and past the list view threshold | `dbmlsp Probe LargeLib`, indexed and unindexed by whichever probe is reading it | `library.large-list.fixture-library-present` |
| Is the fixture library present and past the list view threshold | `dbmlsp Probe PreIndex`, whose Choice column was indexed at 4,900 files and never cleared | `library.large-list.fixture-preindex-library-present` |
| Does an index let a group-by through past the threshold | the modern library PAGE rendering a grouped view in a browser, where every REST surface refuses one | `library.large-list.ui-group-by-indexed-column-renders` |
| Is a group-by honoured on a single-value column | an unindexed column on the rendered page, beside the indexed one on the same library | `library.large-list.ui-group-by-unindexed-column-renders` |
| Does the default view serve past the list view threshold | `RenderListDataAsStream` returning its first page of rows | `library.large-list.default-view-renders-first-page` |
| Does the default view serve past the list view threshold | the modern library page rendering file rows a person can see | `library.large-list.ui-default-view-renders-past-threshold` |

`native-index-probe.js` and `threshold-index-probe.js` both emitted `CMPIDX` and
`NULIDX`, and their four system-column checks (`NATCRE`/`SYSCRE` and siblings)
ask about the same four columns. Under the bare ids those read as collisions.
Under the grammar the question separates them. The system-column pair splits by
method: `created-property` reads `SP.Field.Indexed`, `created-threshold-filter`
filters past the threshold. The filter pair splits by fixture: `found-list`
names a list the probe did not build, and `SP.Field.Indexed` cannot say whether
that list's index is the platform's or its owner's, so it does not settle the
`native-idx` question the fixture version settles.

## Emitted result shape

One shape everywhere: `{id, question, outcome, evidence, state}`. The
`{observed, detail}` pair is retired.

`state` is one of five, emitted by the probe rather than inferred from the
prose:

| State | Meaning |
| --- | --- |
| `settled` | Answered; machine evidence sufficient |
| `open` | Not yet answered |
| `awaiting-capture` | The machine lane has done what it can; needs a visible capture |
| `void` | A control this check depends on failed |
| `needs-human` | Captured and reviewed, still unresolved |

`outcome` and `evidence` keep the prose. There are 83 distinct outcome heads
across the committed evidence; they are good prose and bad enums, and `state` is
the enum they were being asked to be.

A check may declare `depends_on: [<check-id>, ...]`. If any named check is a
`control-` check whose outcome is a failure, this check's state is `void`.
`native-index-probe.js` is the case that motivates it:
`scale.native-idx.control-index-readable` (was `NATID`), its outcome is
`CONTROL FAILED, METHOD VOID`, and its four dependants stop publishing as
ordinary open questions with the explanation suppressed.
