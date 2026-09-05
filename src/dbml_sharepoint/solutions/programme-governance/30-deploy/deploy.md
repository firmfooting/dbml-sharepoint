# Deploying programme governance (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = programme-governance`. Run order: **assess** the target site
(paste `build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or
an accepted DEGRADED) -> **review** `build/deploy-manifest.md` (must show 0
validation errors) -> **paste** `build/deploy.js.txt` from a Site Owner's
console -> **verify** against the checklist below. Template-specific notes
follow.

This family carries more that the deployer cannot do than any other in the
library: attachments on ten lists, three group memberships, the site home
page, and the identity phase 2 will run its flows as. Read **Mandatory
manual go-live steps** before you schedule the paste rather than after it.

## The ten lists

| List | Holds | Who writes to it |
| --- | --- | --- |
| `GOV_Workstream` | The programme's decomposition: phase, order, dates, closure | Governance and site owners. Everybody else reads it |
| `GOV_Stakeholder` | The vocabulary: individuals, roles, forums and external bodies | Governance and `GOV Accountability Maintainers`, and it is filled **first** |
| `GOV_BusinessProcess` | Project-adjacent processes worth mapping, and the order to take them in. The maps are drawn elsewhere; this records which ones we know about | Every Site Member, Contribute |
| `GOV_Activity` | One row per thing done, approved or decided, with its single Responsible and single Accountable | Governance and maintainers, through `GOV Contribute No Delete` |
| `GOV_Involvement` | One row per Consulted or Informed stakeholder on an activity | Governance and maintainers, same level |
| `GOV_ServiceRequest` | Every change asked of the provider, worked from draft to closure with its authorisation and the minutes spent | Any Site Member may add one through `GOV Submit Only`; governance authorises, and `GOV Request Handlers` work and close it through `GOV Contribute No Delete` |
| `GOV_Risk` | What might still stop a workstream delivering | Every Site Member, Contribute |
| `GOV_Action` | Work handed to a named person with a date | Every Site Member, Contribute |
| `GOV_Issue` | What has already gone wrong | Every Site Member, Contribute |
| `GOV_Decision` | What was decided and why | Every Site Member adds and edits through `GOV Contribute No Delete`; nobody but governance deletes |

Five permission classes, and two custom permission levels that the deploy
creates. Which class a list is in decides who may write to it, so read the
`list_permissions` block of `20-configure/mapping.yaml` as the statement of
record; the table above is its summary.

## Before you build

- [ ] Each of the ten list titles is either absent on the target site or
      carries this family's provenance marker under its current or a
      previous name; `assess.js.txt` reports every one under
      `rename:<title>`. The same holds for the three family groups
      (`GOV Programme Leads`, `GOV Accountability Maintainers`,
      `GOV Request Handlers`) and the two permission levels
      (`GOV Submit Only`, `GOV Contribute No Delete`): each is either
      absent, or carries the marker under its current name or a previous
      one, and the assessment reports each. A group or level that exists
      without the marker was not created by this family, and the deploy
      refuses it rather than adopting it.
- [ ] **One programme per site.** No list here carries a programme column,
      because the site is the programme. Two programmes sharing a site
      share one risk list, one action list and one accountability register,
      and no view can separate them afterwards.
- [ ] **No list here will reach 5,000 rows.** The limit that could matter
      is the list view threshold on lookup pickers, and it bites only past
      5,000 items in the target list. The `RelatedRisk` picker shows the
      calculated `LiveRiskTitle`, which is blank for a Closed risk, so it
      cannot be indexed and the picker depends on `GOV_Risk`
      staying small.
- [ ] The enums match how the programme actually talks, in particular
      `adopt_request_status` and `adopt_escalation_level`. `Status` drives
      the service-request views, the save rules and the colours, and a state
      missing from the enum is a state nobody can record.
- [ ] If your organisation has its OWN risk matrix, encode it in
      `mapping.yaml` **now**, before first deploy. The comment above
      `calculated_formulas` shows the cell layout; keep the DBML Likelihood
      and Consequence enums in the order the formulas index them.
- [ ] **The confirmation cadence is a decision, and it is easier before
      first deploy.** `ConfirmationDue` is calculated from `LastConfirmed`
      and `Criticality`: Statutory 6 months, High 12, Routine 24. Changing
      it once the register is populated recalculates every existing row.
- [ ] **Know who fills all three family groups before you paste.** Nobody
      outside `GOV Accountability Maintainers` can edit an activity, a
      stakeholder or an involvement, including the people named `Responsible` and
      `Accountable` on their own rows. Nobody outside
      `GOV Programme Leads` can authorise a service request, and nobody
      outside `GOV Request Handlers` or governance can work one. All three
      groups deploy empty and none is reconciled.
- [ ] **The deploy replaces each list's Description** with the table note
      from `10-design/schema.dbml` plus a provenance marker naming the
      family and entity. That write replaces whatever the list holds now,
      including prose an owner typed by hand, and SharePoint preserves no
      copy. The ten exact strings are in `build/deploy-manifest.md` under
      the list-creation phase; read them there rather than after the fact.
      This matters on a redeploy over existing lists, not on a fresh site.
- [ ] Each form header shows the row's title on a saved row and a `New ...`
      prompt before the title is typed. If you add another `[$FieldName]`
      reference, note that a **calculated** column always resolves empty in
      a form header: `ConfirmationDue`, `ResidualRiskRating` and
      `RiskScore` show nothing there, with no error. Their values reach the
      form through their own `column_formatting`, in the body sections.

## Build the bundle

```bash
dbml-sharepoint build \
  --schema 10-design/schema.dbml \
  --mapping 20-configure/mapping.yaml \
  --release 20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --seed \
  --out ./build
```

Drop `--seed` for a production site that will hold real rows from the
start. With it, the bundle carries a fourth script, `demo-data.js.txt`.

Syntax-check every emitted script before anything is pasted:

```bash
for f in build/*.js.txt; do
  echo "$f"
  node --check --input-type=commonjs < "$f"
done
```

Silence under each filename is a pass. `node --check build/deploy.js.txt`
does not work on these files: the scripts ship as `.js.txt` so a browser
and a mail gateway treat them as text, and node refuses an unknown
extension with `ERR_UNKNOWN_FILE_EXTENSION` before it parses anything.
Feeding the file on stdin and naming the dialect is the form CI uses.

Then read `build/deploy-manifest.md`. As shipped it reports 10 lists, 105
non-lookup columns, 6 phase-2 lookup columns, 58 indexed columns, 57 views,
26 formatted columns, and **0 validation errors and 0 validation
warnings**. A number that differs from these means the schema or the
mapping has been edited, which is legitimate; an error count above zero
means do not paste.

## Optional: the seeded demonstration build

The risk matrix, the overdue `ConfirmationDue` cell, the gold wash on a
*Needs review* activity, the escalation colours on a service request and the
conditional date fields are all invisible on empty lists, and this family
is judged in the first two minutes of the first meeting it appears in.

`demo-data.js.txt` creates 58 rows: six workstreams spanning all six
phases, seven stakeholders covering all four kinds and both statuses, eight
activities across every criticality, every review status and all three
activity roles, six involvements (three of them consulting the same stakeholder,
so *Consultation load* has something to reveal), seven service requests
across the request lifecycle, including escalated ones and three with
minutes logged, six risks spanning
all four rating bands, seven actions including one overdue and still open,
six issues across every severity, and five decisions.

**Paste order matters.** Paste `deploy.js.txt` first, then
`demo-data.js.txt`, from the same bundle. The demo rows reference each
other by title across lists, and one `demo-data.js.txt` does the whole
family in the right order; do not split it.

**Every person column resolves to whoever pastes the script.**
Responsible, Accountable, Confirmed By, Assigned To, Owner, Requested By
and Authorised By are all the operator, so *My actions* and *My
accountabilities* demonstrate as one person's list. That is the mechanism
working, with one person in the sample.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO]` followed by a space, so they are obvious in every view, they are
matched by Title on re-paste (running it twice never duplicates), every
phase-2 flow will exclude them by trigger condition, and `rollback.js.txt`
requires per-list confirmation before every delete. Do not seed a site that
already holds real rows.

## First job after the paste: seed the vocabulary

**Fill `GOV_Workstream` and `GOV_Stakeholder` before you tell anybody
the site exists.** Both are empty lookup targets on the paste, and until
they hold rows most of the family cannot be used at all:

- `Workstream` is a required lookup on `GOV_Activity`,
  `GOV_ServiceRequest`, `GOV_Risk`, `GOV_Action`,
  `GOV_Issue` and `GOV_Decision`. Until at least one
  workstream exists, **no row can be saved on any of them**.
- `Involvement.Stakeholder` is required, so the Consulted and Informed
  half of the accountability register cannot be entered until stakeholders
  exist, and `Activity.AccountableForum` is a lookup at the same
  list, so an activity whose accountability runs through a committee has
  nowhere to say so.
- A maintainer who meets an empty picker types the nearest thing they can
  into a free-text column instead, and the vocabulary you were trying to
  standardise never happens.

Order of first fill: the five to eight workstreams, then the stakeholders, then
the activities, then the involvements, and only then the delivery layer.
An involvement needs both its activity and its stakeholder to exist. Enter the
governance forums, the recurring roles, the individuals who hold
accountability in their own right, and the external bodies you are
answerable to, including the provider. Give each stakeholder a `Contact` unless
it is a Forum, and every External stakeholder a `ServiceDeskAddress`. Nothing in
SharePoint enforces either: `Contact` is a person column and person
operands are refused in validation formulas, so it is a quarterly check
read on *Active stakeholders*, which renders both columns so that a blank is
visible.

## After the paste: verification checklist

- [ ] `build/verify.js.txt` pasted in the same console after the deploy,
      and its `[SP-VERIFY] [DONE]` verdict is **VERIFIED**. It writes only
      to the hidden `_dbml-verify` scratch list and exercises every date
      rule, view window and `[today]` default this programme relies on. A
      **MISMATCH** names the cell that does not behave on this site as
      measured: stop and read its FAIL lines before the trial goes further.
      A **NOT-VERIFIED** with date cases skipped means the browser's zone
      differs from the site's; paste from a browser set to the site's zone.
- [ ] All ten lists exist, created in this order: `GOV_Workstream`,
      `GOV_Stakeholder`, `GOV_BusinessProcess`, `GOV_Activity`,
      `GOV_Involvement`, `GOV_Decision`, `GOV_ServiceRequest`,
      `GOV_Risk`, `GOV_Issue`, `GOV_Action`. A list title is the prefix
      and the bare entity name; it is the columns that carry spaced
      display titles.
- [ ] All six deferred lookups resolved. A lookup is deferred to Phase 2.2
      when its target's display column is not the built-in `Title`, and
      both `GOV_Risk` and `GOV_Decision` display a calculated one
      (`LiveRiskTitle`, `LiveDecisionTitle`), so every lookup into either
      is deferred, the `GOV_Decision` self-reference included. The
      manifest's Phase 2.2 table is the list:

| List | Column | Target |
| --- | --- | --- |
| `GOV_Decision` | `SupersedesDecision` | `GOV_Decision` |
| `GOV_ServiceRequest` | `AuthorisingDecision` | `GOV_Decision` |
| `GOV_Risk` | `ToleranceDecision` | `GOV_Decision` |
| `GOV_Issue` | `RelatedRisk` | `GOV_Risk` |
| `GOV_Action` | `RelatedRisk` | `GOV_Risk` |
| `GOV_Action` | `AuthorisingDecision` | `GOV_Decision` |

- [ ] The two pickers show only live rows, which is the property the
      deferral exists to deliver and the one nothing else checks. Create a
      test risk and confirm both `RelatedRisk` pickers offer it by title,
      then close it and confirm it drops out. Create a decision, leave it
      `Proposed`, and confirm none of the four `GOV_Decision` pickers offer
      it; approve it and confirm all four do.
- [ ] All forty-seven declared views appear:
      - **Workstream**: *The programme* (the default).
      - **Stakeholder**: *Active stakeholders* (the default), *By kind*,
        *Retired stakeholders*, *Changed since last review*.
      - **Business Process**: *The mapping queue* (the default), *Unowned*,
        *By workstream*, *Mapped*.
      - **Activity**: *My accountabilities* (the default),
        *Confirmation due*, *Never confirmed*, *Needs review*, *By workstream*,
        *Workstream leads*, *Decisions and approvals*, *Retired*, *Changed
        since last review*.
      - **Involvement**: *By activity* (the default), *By stakeholder*,
        *Consultation load*, *Changed since last review*.
      - **Service Request**: *In progress* (the default), *Authorised, not
        yet picked up*, *My assigned requests*, *Closed*, *Escalated*,
        *Needed soon or overdue*, *My raised items*, *Changed since last
        review*.
      - **Risk**: *Open* (the default), *Review due*, *Closed this
        quarter*.
      - **Action**: *My actions* (the default), *Overdue*, *Open by
        person*, *Done and dropped*.
      - **Issue**: *Open* (the default), *Severe and open*, *By
        owner*, *Needs triage*, *My raised items*, *Resolved and closed*.
      - **Decision**: *Awaiting decision* (the default),
        *Decision log*, *Stalled proposals*, *Changed since last review*.
      The manifest counts 57, which is these forty-seven plus the ten generated
      **All Items** recovery views, hidden from the modern view bar because
      every list has an authored default.
- [ ] **My actions** and **My accountabilities** show *your* rows and
      change per signed-in user. Ask a colleague to open both and confirm
      they see theirs, not yours.
- [ ] List Settings -> Indexed columns matches the 51 the manifest lists.
      `LiveRiskTitle` is **not** among them, and that is correct: it is a
      calculated column and cannot be indexed. `GOV_Risk` and
      `GOV_Decision` are the two lists whose `Title` is not
      indexed either, because their display columns are `LiveRiskTitle`
      and `LiveDecisionTitle`.
- [ ] Matrix spot-checks on a test risk:
      - Rare + Minor -> **Low / 1**
      - Unlikely + Substantial -> **Medium / 11**
      - Very Likely + Business Critical -> **Extreme / 24**
      - Almost Certain + Business Critical -> **Extreme / 25**
      - Clear Likelihood -> `ResidualRiskRating` and `RiskScore` both go
        **blank**. Unrated is visible, not defaulted.
- [ ] `ConfirmationDue` spot-checks on a saved test activity:
      - Statutory, confirmed today -> due in **6 months**.
      - High -> **12 months**. Routine -> **24 months**.
      - Set `ReviewStatus` to **Retired** -> the cell goes **blank**.
      - A due date in the past renders with the severe treatment and a
        warning icon; set that row to Retired and it goes plain.
- [ ] The service request **New** form hides the governance and handler
      fields. `Status`, `AuthorisedBy`, `AuthorisedDate`,
      `AuthorisingDecision`, `AssignedTo`, `MinutesSpent`,
      `EscalationLevel`, `EscalatedDate`, `EscalatedBy` and `EscalatedTo`
      are all absent from it, and the request saves as `Drafted` without
      them. This is half of the internal-authorisation control;
      `GOV Submit Only` is the other half, and neither is the control on
      its own.
- [ ] On an existing service request, `AuthorisedBy`, `AuthorisedDate` and
      `AuthorisingDecision` appear when `Status` is **Authorised**, **In
      progress**, **Waiting on requester** or **Closed**; `MinutesSpent`
      appears from **In progress** onwards; `AssignedTo` and the escalation
      block are on the form unconditionally. Move the status back and the
      fields hide, keeping whatever was entered. SharePoint has no
      mechanism to clear a hidden field.
- [ ] `EscalationRoute` is **absent from a new activity while Activity Kind
      is Task, Criticality is not Statutory and Activity Role is empty**,
      and appears the moment any one of those changes. Those are exactly
      the three branches of the save rule below it. A visibility condition
      narrower than its rule produces a form that refuses to save and will
      not show you why, so check all three by hand.
- [ ] Save rules on the lists, four in total. Each list has one
      `ValidationFormula`, so every branch on a list shares one message:
      - **Activity**, three branches, one message: an Activity Kind
        of **Decision**, a Criticality of **Statutory**, or any **Activity
        Role**, each with `Escalation Route` empty, is refused.
      - **Service Request**, four branches, one message: a status of
        Authorised, In progress, Waiting on requester or Closed with no
        `AuthorisedDate`; Closed with no `MinutesSpent`; an
        `EscalationLevel` with no `EscalatedDate`; an `EscalatedDate` with
        no `EscalationLevel`.
      - **Action**: Status **Done** with no `CompletedDate`.
      - **Issue**: Status **Resolved** or **Closed** with no
        `ResolvedDate`.
- [ ] Save rules on the columns, six in total, each with its own message
      because a column rule reads only its own column: a future
      `LastConfirmed`, `AuthorisedDate`, `EscalatedDate`, `CompletedDate`
      or `ResolvedDate` is refused, and so is a negative `MinutesSpent`.
- [ ] **A service request with a status of Authorised and no
      `AuthorisedBy` still saves, and so does one In progress with no
      `AssignedTo`.** The design tabulates six branches for this list and
      the mapping builds four: both are person columns, and SharePoint
      validation formulas refuse person operands, so the build rejects
      those branches as `condition_operand_type_unsupported`. The date is
      the enforceable half of the authorisation obligation, and both fields
      appear together in exactly the states the rule fires in. "An
      authorisation names a person" and "a request being worked names its
      handler" are fortnightly checks on *Authorised, not yet picked up*
      and *In progress*.
- [ ] A closed risk with an empty `ClosureNote` still saves, for the same
      class of reason: `ClosureNote` is rich text and validation formulas
      refuse multi-line operands. It is a monthly check read on *Closed
      this quarter*.
- [ ] `LastConfirmed` is **absent from the New form** and present on Edit
      and Display. It fills itself with today at creation, which is the
      baseline the whole cadence counts from.
- [ ] `Accountable` accepts exactly one person, and neither `Responsible`
      nor `Accountable` accepts a group or a distribution list. Confirm
      this on the live list rather than trusting the schema: it is the
      structural claim the accountability layer makes.
- [ ] Row washes: an activity set to **Needs review** washes its row in *My
      accountabilities*, an **Extreme** risk washes its row in the risk
      *Open* view, and a **Critical** issue washes its row in the issue
      *Open* view. Nothing else does, on any list. One row-level signal per
      list is the whole budget.
- [ ] An action filed against a **Closed** workstream still saves, and
      shows the closed phase beside it through the `WorkstreamPhase`
      projection. A lookup picker cannot be filtered, so this is made
      visible rather than prevented, and it is a fortnightly check.
- [ ] The forms carry every column in a named section: **Workstream** has
      *Name the workstream*, *Sequence and dates*, *Phase and closure*;
      **Stakeholder** has *Name the stakeholder*, *How to reach them*, *Status
      and notes*; **Activity** has *Describe the activity*,
      *Classify it*, *Assign it*, *Keep it current* and, last, *System*;
      **Involvement** has *State the input*, *How they are
      involved*; **Service Request** has *Describe the request*, *Who
      needs it and when*, *Internal authorisation*, *Handling*,
      *Escalation*; **Risk** has *Describe the risk*, *Assess the
      risk*, *Response and owner*, *Review and closure* and, last,
      *System*; **Action** has *The action*, *Owner and date*,
      *Progress*; **Issue** has *Describe the issue*, *Severity and
      owner*, *Progress*, *Resolution and closure*; **Decision**
      has *The decision*, *Why*.
- [ ] Both custom permission levels exist under **Site settings -> Site
      permissions -> Permission levels**, and both behave. That test needs
      a second account and is the section below.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete this
      list"; a display-name rename is still possible. It is drift, reverted
      and reported at the next re-paste.
- [ ] Delete the test rows, then work through **Mandatory manual go-live
      steps**. The deploy is not finished until those four are done.

## Verifying the two custom permission levels

Do this with a **second account**, before anybody is told the site is
live. Neither level can be verified from an owner's console, because a site
owner bypasses every access control on the site.

`GOV Submit Only` is `change-register`'s measured eight permissions,
unchanged. `GOV Contribute No Delete` is that set plus `EditListItems`
and `OpenItems`, and **it is not itself a measured precedent**: it is
composed from one. A composed level that saves, reads back byte-identical
and passes every deploy phase can still behave differently from what its
name claims, and nothing in the build or the deploy can see the difference.
Verify it on the live site before you trust it with the accountability
register.

**With a plain Site Member account, in neither family group:**

- [ ] `GOV_ServiceRequest`: the account can create a request, and the
      New form hides the governance and handler fields.
- [ ] `GOV_ServiceRequest`: the account cannot edit a request afterwards,
      including one it created itself, and cannot delete one.
- [ ] `GOV_Decision`: the account can create a decision, and can
      open and edit an existing one and save it.
- [ ] `GOV_Decision`: the account is not offered delete on an
      item, and an attempt to delete one fails.
- [ ] `GOV_Decision`: the account can read an item's version
      history, and cannot delete a version or the history.
- [ ] `GOV_Workstream`, `GOV_Stakeholder`, `GOV_Activity` and
      `GOV_Involvement` are read-only to it.
- [ ] `GOV_Risk`, `GOV_Action` and `GOV_Issue`
      are ordinary Contribute, delete included. These three are the working
      surface and that is deliberate.

**Then add the same account to `GOV Accountability Maintainers` and
repeat on the accountability layer:**

- [ ] It can now open, edit and save an activity, a stakeholder and an
      involvement.
- [ ] It is still not offered delete on any of the three, and an attempt
      fails.
- [ ] It can still read version history on all three, and still cannot
      prune it. Version history is this family's audit for self-service
      confirmation, and an audit somebody can prune is not one.

Record what you observed, dated, in the family's governance notes. A live
run that teaches something belongs in writing; a level that turns out to
behave differently from this list is a finding about the library, not a
local quirk to work around.

## Mandatory manual go-live steps

Five things the deployer cannot do. None of them is optional and none of
them is reasserted by a redeploy.

### 0. Set the site's regional time zone, and rebuild for the save rules

**Site settings > Regional settings > Time zone** must be the zone the
users work in: for this programme, *(UTC+10:00) Canberra, Melbourne,
Sydney*. It is the zone every date and time is stored and shown in, and
the day the twelve view windows on `today` are read against.

It does not fix the save rules, and this is measured rather than
assumed. On 2026-09-02, with the trial site already in UTC+10 and the
server clock correct, completing an action dated today was still refused
as "completed in the future": the clock behind `TODAY()` and `NOW()` in a
validation formula runs 16 to 20 hours behind this site whatever the
zone says. The generator now compares the six "cannot be in the future"
rules with the instant of the save itself, on the list rule, which the
same measurement showed to be exact on create and on update. So the pack
must be built with a version that carries that change, and the six
rules move from their columns onto each list's rule, with messages
joined. The twelve view windows and the two `[today]` defaults on
`RaisedDate` were measured to follow the site's zone and the true clock,
so they need nothing.

- [ ] The site time zone is *(UTC+10:00) Canberra, Melbourne, Sydney*.
- [ ] The pack was built after the save-instant change, and an action
      dated today saves at 10:00 in the morning.

### 1. Disable attachments on all ten lists

There is no `attachments` key in `mapping.yaml`. The deployer neither sets
nor reconciles the setting, so this is a manual gate, and it is the **only
privacy control a redeploy does not reassert**. If somebody re-enables
attachments later, nothing detects it and nothing repairs it.

On each of the ten lists:

1. Open **List settings -> Advanced settings**.
2. Set **Attachments to list items** to **Disabled**.

- [ ] Attachments are disabled and absent from the New and Display
      experiences on all ten lists.

For a family carrying a healthcare boundary this is the gap that matters:
an attachment is the one place identifiable content can arrive that no
column rule, no permission level and no redeploy will see. Re-check it
after any change to list settings, not only at go-live.

### 2. Populate the three family groups

Group membership is neither declared nor reconciled by the deployer, so
all three groups deploy empty and stay however you leave them.
`require_empty_at_deploy` is deliberately not set on any of them: with it,
the next deployment would reject a correctly populated group.

- [ ] `GOV Programme Leads` holds the programme owner, the governance
      lead and executive support. It is the only principal that authorises
      a service request, so an empty group means no request can ever be
      authorised.
- [ ] `GOV Accountability Maintainers` holds everyone currently named
      `Responsible` or `Accountable` on an activity, plus governance. It is
      deliberately wide: SharePoint cannot express "edit only your own row"
      against an arbitrary person column, so the mechanism is a wide group
      with no delete and no version pruning, audited by reading history.
      An empty group means nobody can confirm an accountability row.
- [ ] `GOV Request Handlers` holds the provider staff who work service
      requests. The mapping grants them `GOV Contribute No Delete` on
      `GOV_ServiceRequest` and nothing else, so each needs an account in
      this tenant and whatever site access every other member has. An
      empty group means no request can be picked up, progressed or closed,
      and *Authorised, not yet picked up* fills and stays full.

Keeping the second group in step with the `Responsible` and `Accountable`
population is a quarterly check, for the same reason: nothing reconciles it.

### 3. Build and verify the site home page and navigation

`dbml-sharepoint` provisions lists, views, forms and permissions. It has no
site-home or navigation declaration, and making *My actions* a list's
default view does not make that list the site's landing page.

- [ ] The site home page carries six links, each labelled with the question
      rather than the list name, in this order: *What do I owe?*
      (`GOV_Action`), *What am I accountable for?*
      (`GOV_Activity`), *What are we waiting on?*
      (`GOV_ServiceRequest`), *What is broken?* (`GOV_Issue`),
      *What might break?* (`GOV_Risk`), *What is this programme,
      on one screen?* (`GOV_Workstream`). The first is first because it
      is the only one most people need.
- [ ] Site navigation carries the same six entries in the same order.
- [ ] Nothing on the home page is audience-trimmed. Trimming would hide the
      register from the people whose rows it holds.
- [ ] **Verification.** A second account holding only Site Member access
      opens the site root and reaches *My actions* in one click, without
      being told where to look. Run this again after any site-level change.

### 4. The identity phase 2 will run its flows as

Phase 1 deploys no flows and grants no automation identity anything, so
there is nothing to add yet. The step is here because the way this goes
wrong is invisible until days after somebody has done it.

Every list uses `break_inheritance: true` and `reconcile: exact`. The ACL
phase enumerates every role assignment, skips only `Limited Access`, and
removes anything not in the declared set. So:

- [ ] No automation identity, service account or connection owner has been
      granted access to any of the ten lists by hand. Such a grant is
      deleted by the next redeploy, and the flow then fails with a 403 on a
      site nobody touched.
- [ ] No individual list **item** has been shared with anyone. An item
      share creates a unique item scope, which under `exact` is not merely
      revoked: it **aborts every subsequent deploy of that site** until an
      operator resolves it by hand.

When phase 2 starts, the identity goes in a **declared** group and the
family is redeployed, rather than being granted access directly. The
library group is requested as issue #331; if it has not landed, the
fallback is a family-local group holding a narrow custom level on
`GOV_Issue` only. Either way the membership itself is not
reconciled, so putting the identity in the group is a post-deploy step to
re-verify on every release.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Rows are untouched; views, forms,
formatting, column visibility, save rules and permission grants are
reconciled back to the declaration, and a view somebody widened or
re-filtered by hand returns to the declared shape with the run reporting
that it did so.

Four things a redeploy will not do for you:

- **It will not restore the attachment setting.** See gate 1 above. Check
  all ten lists after every redeploy.
- **It will not populate a group.** An emptied
  `GOV Accountability Maintainers` stays empty and the accountability
  layer silently becomes read-only to everybody, and an emptied
  `GOV Request Handlers` means nobody can work a request.
- **It will not preserve a hand-granted permission.** That is the point of
  `reconcile: exact`, and it is also how a phase-2 flow dies.
- **It will not warn you before recalculating a formula.** A redeploy
  applies formula changes to the live columns and SharePoint then
  recalculates every existing row. That is desirable for a typo fix and
  consequential for a matrix revision or a cadence change: shortening
  Routine from 24 months to 12 makes a large part of the register fall due
  the moment the paste finishes. Export the affected list first.

A renamed column is a new column to the deployer, because Power Automate
binds by internal name: the old one becomes undeclared drift and the new
one is empty, while a flow keeps running and reads nothing. Change what
people see through `display_names.overrides`, which leaves the internal
name alone. The columns the phase-2 flows will bind are declared in
`watched_lists`, and the build fails with `watched_column_not_rendered` if
one of them stops being rendered.

A renamed entity is adopted in place when the mapping says where it came
from. `renamed_from` on an entity lists its previous names; when no list
carries the current title, the preflight looks for a list under each
previous title carrying the exact provenance marker for that previous
name, retitles it, rewrites the marker in its description, and reads both
back before any list is created. Rows, views, lookups and permissions all
bind to the list id, so they survive; the URL keeps the slug the list was
created with. A previous title whose description does not carry the marker,
or one found beside the current title, blocks the assessment and the
preflight rather than being adopted.

The 2.0.0 release is that migration for the whole family. The live site
holds the pre-1.1.0 pack under bare titles (`ProgramParty`,
`ProgramActivity`, `TenantRequest` and so on), with rows in every list but
`TenantRequest`, and its groups and levels under the ADOPT stem
(`ADOPT Program Governance`, `ADOPT Accountability Maintainers`,
`ADOPT Submit Only`, `ADOPT Contribute No Delete`). 2.0.0 gives every list
its bare entity name under the `GOV_` prefix and every group and level the
`GOV` stem, with `renamed_from` on each and `previous_prefixes` naming both
stems the site holds, so one redeploy renames all of them in place. Five
steps, in this order:

1. **Paste `assess.js.txt` and read the rename findings.** One per list
   under `rename:<title>`, and one per group and per level under their
   equivalents. Every previous name must show as adopted under its new one
   and none as blocked. A blocked finding names an object whose
   description lacks the marker for that previous name, or one that exists
   beside its new name; restore a marker only if this tool created the
   object, and never stamp a foreign one.
2. **Paste `deploy.js.txt`, then `verify.js.txt`.** The deploy renames the
   ten lists, the two groups and the two levels in place, creates
   `GOV Request Handlers`, creates the new columns (`StakeholderKind`,
   `Stakeholder`, `AssignedTo`, `MinutesSpent`, `RelatedServiceRequest` and
   the rest), migrates the views by their previous titles, and reconciles
   everything else. Rows, group members and level assignments are
   untouched.
3. **Re-key the two stakeholder columns on the form.** On each
   `GOV_Stakeholder` row copy **Party Kind** into **Stakeholder Kind**, and
   on each `GOV_Involvement` row set **Stakeholder** from the old **Party**
   value. The old and the new column sit on the same edit form until step
   4 removes the old one. **Stakeholder** is required, so an involvement
   row cannot be saved again until it is set, and *By stakeholder* and
   *Consultation load* show a blank group until the re-key is done.
4. **Delete the superseded columns with `columns.js.txt`**, generated per
   list with `dbml-sharepoint columns-script <the list's URL>`:
   `RelatedTenantRequest` on `GOV_Action`, `PartyKind` on `GOV_Stakeholder`,
   `Party` on `GOV_Involvement`, `DecisionRule` on `GOV_Activity` and
   `IvantiReference` on `GOV_ServiceRequest`, plus anything else the
   script's table shows that the schema no longer declares. Type each
   internal name and let the script unseal it, delete it and read the field
   back.
5. **The three go-live steps** above: attachments off on all ten lists,
   the three family groups populated (`GOV Programme Leads` and
   `GOV Accountability Maintainers` keep the members they had under their
   ADOPT names), and the home page checked.

## Rollback boundary

`rollback.js.txt` is for empty or demo deployments only. It deletes lists
by title, after typing the site leaf path to confirm and then confirming
each list individually, and it clears `prevent_list_deletion` per list as
it goes. It does not remove the site groups, the role assignments or the
two custom permission levels, and it will not delete a list held by a
retention policy.

Real rows here are organisational records: a service request is the
internal authorisation for a change made to a live tenant, and an
accountability row
is evidence of who answered for something. Export them and follow your
records schedule before any decommission.

## The release checklist

Run this for the first deploy and again for every redeploy. Most of it is
the release-checklist half of the governance ledger, gathered where the
person doing the paste will see it.

- [ ] `schema_version` bumped in `20-configure/release.yaml` for any DBML
      or mapping change.
- [ ] Bundle rebuilt, and every emitted script passes `node --check` on
      stdin.
- [ ] `deploy-manifest.md` shows 0 validation errors, and any changed count
      is a change somebody meant.
- [ ] Assess run against the target site, verdict COMPATIBLE or an accepted
      DEGRADED.
- [ ] Deploy pasted from a Site Owner's console, and the run's summary
      object reports `errors: []`.
- [ ] Verification checklist above worked through.
- [ ] Both custom permission levels re-verified with a second account.
- [ ] Attachments disabled on all ten lists, re-checked after the paste
      rather than assumed from last time.
- [ ] All three family groups populated, and
      `GOV Accountability Maintainers` still matches the current
      `Responsible` and `Accountable` population.
- [ ] Site home page and navigation present, and the one-click test rerun.
- [ ] No hand-granted list permission and no shared item anywhere on the
      site.
- [ ] Any new `not null` column reviewed against the phase-2 flows.
      `watched_lists` cannot see a column no flow names, so a required
      column added after a flow was built will fail its writes.
- [ ] Anything a live run taught you written down, dated, in the family's
      governance notes.

## Enterprise reporting access

The deploy declares the `dbml Enterprise Readers` site group, shared with
every other family deployed to the site, and grants it `Read` on every list
in this family. The group starts empty only if no family has deployed to
the site yet; it gains a member when any family's build is run with
`--enterprise-reader <account>`, which enrols exactly that one account and
nothing else. `rollback.js.txt` does not remove it: rollback deletes lists,
not site groups or role assignments, so the group and any account enrolled
in it survive a rollback.

If the group already holds anyone other than that account, the deploy
**aborts before enrolling** and removes nobody. Before you clear anyone
out, check who it is: the group is shared by every family on this site, so
the unexpected member is most likely **another family's reporting
account**, and removing it silently breaks that family's reporting. Agree
one reader account for the site and rebuild with that address, or rebuild
without the flag. Only clear the group in Site permissions > Groups once
you know nothing else needs the account.

On one Microsoft 365 group-connected Team Site (measured 2026-08-11) the
enrolled account ends up with the built-in `Read` on each list and
`Use Remote Interfaces` intact at web scope. Publishing sites, where
lockdown mode is on by default, and the reporting client's own list
enumeration are still unverified, so the end-to-end path (Power BI or any
other API client) is not yet proven. See the danger block in the mapping
reference's Security section.

The mapping turns on `reporting.users_table`, so the pack's `_Users.pq`
reads the site's user information list (`/_api/web/siteuserinfolist`) as
well as the ten lists. That list was measured readable by a site admin on
2026-09-02. Whether the enrolled reader account can read it is not yet
measured: a 403 on refreshing `_Users` while the list queries refresh is
that gap. Record what fixes it here, dated.
