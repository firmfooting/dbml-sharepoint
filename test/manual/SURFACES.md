# Probe surfaces

The subject axis of the probe suite: what a probe is *about*. It sits beside the
mechanics axis already in `probe-catalog.json` (`harness`, `authority`, `writes`,
`cleanup`, `prerequisites`, scenario `pattern`), which says how a probe runs.
This file says what it asks.

This file is the sole authority for the surface list, the scope registries and
the check-id grammar. `dbml-sharepoint` validates its probes against it and
`dbml-sharepoint-test-agent` validates its evidence against it. Adding a scope
is a one-line edit here plus the probe change in the same commit. Adding a
surface should be rare: if a probe fits none of the eleven, that is a finding
about the map, and it is worth discussing before it is worth encoding.

**A note on the word.** `surface` here means a subject area. It does not mean
`surface_identity`, which is the per-file integrity attestation in a capture
manifest downstream, nor "evidence surface", which is one of screenshot /
accessibility snapshot / visible content. Those are always spelled in full.

## The check-id grammar

```text
<surface>.<scope>.<question>

check-id := surface "." scope "." question
surface  := one of the eleven tokens below
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

- **`surface`**: one of the eleven below. Fixed vocabulary.
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

Structural validity is not enough. `surface` must be one of the eleven and
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

## The eleven surfaces

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
`list` (the list object the columns belong to)

Probes: `multi-value-probe.js`, `projected-lookup-probe.js`,
`date-storage-probe.js`

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

Scopes: `role-def`, `role-binding`, `group`, `principal`, `item-acl`,
`list-acl`, `lookup-acl`, `effective-perms`

Probes: `enterprise-reader-probe.js`, `reader-bindings-probe.js`,
`lookup-acl-probe.js`, `siteuserinfolist-probe.js`

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
`field`, `search`

Probes: `document-library-probe.js`, `file-operations-probe.js`,
`library-columns-probe.js`, `folder-probe.js`, `library-content-type-probe.js`,
`library-column-interactions-probe.js`, `library-form-probe.js`,
`library-view-probe.js`, `library-formula-probe.js`, `library-access-probe.js`,
`library-query-probe.js`, `library-field-probe.js`,
`library-view-search-probe.js`

`search` holds one probe. That is the map doing its job, not a flaw to tidy away
by merging it into something larger: a surface holding one probe is the statement
that the surface is almost entirely unprobed. `library` was in that position
until `file-operations-probe.js`, `library-columns-probe.js`, `folder-probe.js`,
and `library-content-type-probe.js`, the four probes taking it out.

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

Some probes cross a *scope* boundary within their own surface rather than a
surface boundary, and are listed for the same reason:

| Probe | Checks | File under |
| --- | --- | --- |
| `list-description-probe.js` | the `group-description-512-ceiling` header finding | `text.group-desc.ceiling-512` |
| `formatter-xml-probe.js` | `width-attribute` (was `D_WIDTH`) | `text.col-fmt.width-attribute` |
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
