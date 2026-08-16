# Deploying the RACI matrix (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = raci-matrix`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an
accepted DEGRADED) -> **review** `build/deploy-manifest.md` (must show 0
validation errors) -> **paste** `build/deploy.js.txt` from a Site Owner's
console -> **verify** against the checklist below. Template-specific notes
follow.

## The three lists

| List | Holds | Who writes to it |
| --- | --- | --- |
| `RACI_Party` | The vocabulary: individuals, roles, governance forums and external bodies | Maintainers, and it is filled **first** |
| `RACI_Activity` | One row per thing done, approved or decided, with its single Responsible and single Accountable | Maintainers |
| `RACI_Involvement` | One row per Consulted or Informed party on an activity, stating the input that party gives | Maintainers |

`Party` is the shared vocabulary the other two select from:
`Activity.AccountableForum` is a lookup at it, and `Involvement.Party` is
a lookup at it and is **mandatory**. Everything about the run order below
follows from that.

## Before you build

- [ ] `RACI_` prefix free on the target site.
- [ ] `Domain` enum matches the areas your organisation actually divides
      work into. It is what the register is grouped and reviewed by, so
      fit it now. Renaming a choice later strands the rows already on the
      old value.
- [ ] **The confirmation cadence is a decision, and it is easier before
      first deploy.** `ConfirmationDue` is calculated from `LastConfirmed`
      and `Criticality`: Statutory 6 months, High 12, Routine 24. The
      formula is one line in `20-configure/mapping.yaml`. Changing it
      after the register is populated makes SharePoint recalculate
      `ConfirmationDue` on **every existing row**. Read the change-control
      section of `50-govern/governance.md` first.
- [ ] **Know who fills `RACI Matrix Maintainers` before you paste.**
      Nobody outside that group can edit anything here, including the
      people named in `Responsible` and `Accountable` on their own rows.
      See the security section below for why that is deliberate.
- [ ] The three form headers show `Activity: <title>`, `Party: <title>`
      and `Involvement: <title>` on a saved row, and `New activity`, `New
      party` and `New involvement` before the title is typed, updating
      live as it is typed. If you add another `[$FieldName]` reference,
      note that a **calculated** column always resolves empty in a form
      header. `ConfirmationDue` will show nothing there, with no error.
      Its value reaches the form through its own `column_formatting`, in
      the **System** section.

## The deploy replaces each list's Description

Every list this tool provisions gets its SharePoint **Description** set to
the table's note from `10-design/schema.dbml` plus a provenance marker
naming the family and entity it came from. That write **replaces whatever
the list currently holds**, including a description an owner typed by
hand, and the old value is not preserved anywhere in SharePoint. The
previous text is printed in the run transcript on the line reporting the
change, so copy anything you need out of it before pasting. The exact
three strings that will be written are in `build/deploy-manifest.md`, in
the list-creation phase. Read them there rather than after the fact.

This matters more on a redeploy over an adopted list than on a fresh
provision, where there was nothing to lose.

## Optional: the seeded demonstration build

The overdue `ConfirmationDue` cell, the gold row wash on a *Needs review*
activity, the consultation-load grouping and all eleven declared views are
invisible on empty lists. To see them working, rebuild with `--seed`:

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

That bundle contains an extra file, `demo-data.js.txt`. Paste
`deploy.js.txt` first, then `demo-data.js.txt`, from the same bundle. It
creates eighteen rows: six parties covering all four kinds, two of them
active forums and one a disbanded forum kept as Inactive; six activities
(an overdue Statutory task marked *Needs review*, a Decision, an
Approval, two Routine tasks and one Retired row) and six involvements,
three of them consulting the same external auditor so the *Consultation
load* view has something to reveal.

One thing the demo deliberately does not do: **every person column
resolves to whoever pastes the script.** Responsible, Accountable,
Confirmed By and a party's Contact are all the operator, so *My
accountabilities* demonstrates as one person's list. That is the
mechanism, not a defect. The filter is real, there is simply one person
in the sample.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO]` followed by a space, so they are obvious in every view, they are
matched by Title on
re-paste (running it twice never duplicates), and `rollback.js.txt` treats
a list whose rows are *all* demo-marked as demo-only content. Do not seed
a site that already holds real rows.

## First job after the paste: seed `RACI_Party`

**Fill the party vocabulary before you tell anybody the register exists.**
This is not housekeeping to get to later; it is the step that makes the
other two lists usable at all:

- `Involvement.Party` is required. Until at least one party exists,
  **no involvement can be saved**, so the Consulted and Informed half of
  the matrix cannot be entered.
- `Activity.AccountableForum` is a lookup at the same list, so an activity
  whose accountability runs through a committee has nowhere to say so.
- A maintainer who meets an empty picker types the nearest thing they can
  into a free-text column instead, and the vocabulary you were trying to
  standardise never happens.

Enter your governance forums, the roles that recur across the register,
the individuals who hold accountability in their own right, and the
external bodies you are answerable to. Give each one a `Contact` unless it
is a Forum. For a Forum the contact is its chair or secretariat, which is
often the more useful thing to record anyway. Nothing in SharePoint
enforces that a party has a contact; it is a governance check, and
`50-govern/governance.md` says why it cannot be anything else.

Once the vocabulary is there, load the activities, and only then the
involvements. An involvement needs both its activity and its party to
exist.

## After the paste: verification checklist

- [ ] `RACI_Activity`, `RACI_Party` and `RACI_Involvement` all exist.
- [ ] All five **Activity** views appear: **Current** (the default),
      **My accountabilities**, **Confirmation due**, **Decisions and
      approvals**, **Retired**.
- [ ] All three **Party** views appear: **Active parties** (the default),
      **By kind**, **Retired parties**.
- [ ] All three **Involvement** views appear: **By activity** (the
      default, grouped by activity), **By party**, **Consultation load**.
      If you seeded, none of the eleven is empty. The generated **All
      Items** recovery view is hidden from the modern view bar on all
      three lists, because each has an authored default.
- [ ] List Settings -> Indexed columns shows `ReviewStatus`, `Criticality`,
      `Accountable` and `Domain` on Activity; `PartyKind` and `Status` on
      Party; `Activity`, `Party` and `Involvement` on Involvement. The
      build manifest lists the same nine under **indexed columns**.
- [ ] The Activity form shows **Describe the activity**, **Classify it**,
      **Assign it**, **Keep it current** and, last, **System** holding
      `ConfirmationDue`. The Party form shows **Name the party** and
      **Status and notes**. The Involvement form shows **State the input**
      and **How they are involved**. Every column sits in one of them.
- [ ] **`Accountable` accepts exactly one person.** Try to add a second;
      the picker will not take it. This is the whole structural claim the
      template makes, so confirm it on the live list rather than trusting
      the schema.
- [ ] **`Responsible` and `Accountable` cannot be given a team.** They are
      person columns; a SharePoint group or a distribution list is not a
      selectable value.
- [ ] `LastConfirmed` is **absent from the New form** and present on Edit
      and Display. It fills itself with today's date at creation. That is
      the baseline the whole cadence counts from, and showing it at
      creation only invites somebody to back-date it.
- [ ] `EscalationRoute` is **absent on a New form while Activity Kind is
      Task and Criticality is not Statutory**, and appears the moment
      either of those changes: switch the kind to Approval or Decision,
      or the criticality to Statutory. Those are exactly the two cases the
      save rule refuses without it. Switch back and it disappears again,
      keeping whatever was typed. SharePoint offers no mechanism to clear
      a hidden field, so the value survives the field being hidden.
- [ ] `ConfirmationDue` spot-checks, on a saved test activity:
      - Statutory, confirmed today -> due in **6 months**.
      - High -> **12 months**. Routine -> **24 months**.
      - Set `ReviewStatus` to **Retired** -> the cell goes **blank**. A
        retired activity is not waiting on anybody.
      - A due date in the past renders with the severe treatment and a
        warning icon; set that row to Retired and it goes plain.
- [ ] Set an activity's `ReviewStatus` to **Needs review** and open
      **Current**: the whole row washes gold. It is the only row-level
      signal in this template, reserved for the one state nothing else
      shouts about.
- [ ] Activity carries **two** cross-column save rules in one validation
      formula, sharing a single message because SharePoint gives a list
      only one. Try both: set `Activity Kind` to **Decision** with
      `Escalation Route` empty, and set `Criticality` to **Statutory**
      with it empty. Both are refused with the same message naming both
      cases. That is the platform limit, not a defect. In both cases the
      Escalation Route field is on screen when the refusal fires: a
      rejection naming a field the author cannot see is what the
      visibility rule exists to prevent, and the visibility condition
      covers both branches of the save rule for exactly that reason.
- [ ] **A Statutory Task shows the Escalation Route**, even though its
      kind is Task. Set `Criticality` to **Statutory** on a Task and the
      field appears; set it back to Routine and it disappears again,
      keeping whatever was typed. This is the case worth checking by hand,
      because a visibility condition narrower than its save rule produces
      a form that refuses to save and will not show you why.
- [ ] `LastConfirmed` refuses a date in the future, with its own message
      rather than the shared one. It reads only its own column, so it
      keeps a message that can be specific.
- [ ] An `Involvement` cannot be saved without an `Activity` and a
      `Party`; its `Title` is required and the form header asks for the
      *input*, not the person.
- [ ] As an ordinary Member: all three lists read-only. As **RACI Matrix
      Maintainers**: Contribute.
- [ ] Populate **RACI Matrix Maintainers**; delete the test rows.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible. It is drift,
      reverted and reported at the next re-paste.

## Who belongs in which group

The deploy declares three site groups: `RACI Matrix Maintainers`,
specific to this family, and `dbml List Administrators` and
`dbml Enterprise Readers`, shared with every other family deployed to
the site. The split is the shared fleet model, and the reason it is
right here is specific: **a register whose subjects can rewrite their
own accountability is not a register.**

| Group | Holds | Who belongs in it |
| --- | --- | --- |
| `RACI Matrix Maintainers` | Contribute on all three lists | The small group who maintain the register (governance, quality or executive support). Not "everybody named in a row" |
| `dbml List Administrators` | Full Control site-wide: every register on the site, not just these three | Nobody, by default. The deploy enrols the running operator for the duration of its own run and removes them afterwards, so schema changes and redeploys are deliberate acts |
| `dbml Enterprise Readers` | Read site-wide: every register on the site, not just these three | Nobody, by default. Read-only accounts for aggregated cross-site reporting; membership is operator-owned |

Everyone else, the site's associated members and owners, gets **Read**.
That is the intended posture: the matrix is written centrally and read by
everybody, because its value is that any member of staff can look up who
is accountable for something without asking permission first.

**Being named in `Responsible`, `Accountable`, `ConfirmedBy` or a party's
`Contact` grants nothing.** Those are person columns, not permissions.
A person who is Accountable for forty rows and not in RACI Matrix
Maintainers cannot re-confirm a single one of them. Read the ownership
section of `50-govern/governance.md` before you decide how wide the
maintainers group should be; the choice has consequences for who can
actually complete a quarterly review.

Every list uses `reconcile: exact`: permission grants nobody declared are
removed on deploy and on every redeploy.

## Redeploying: formula change warning

Bump `schema_version`, rebuild, re-paste. Rows are untouched; views,
forms, formatting, column visibility and the save rules are reconciled
back to the declaration, and a view somebody widened or re-filtered by
hand returns to the declared shape with the run reporting that it did so.

The exception is `ConfirmationDue`. A redeploy applies a formula change to
the live column, and SharePoint then **recalculates every existing row**.
That is desirable for a typo fix and consequential for a cadence change:
shortening Routine from 24 months to 12 makes a large part of the register
fall due the moment the paste finishes. Follow the change-control
procedure in `50-govern/governance.md` before touching that line, and
export the register first.

## Enterprise reporting access

The deploy declares the `dbml Enterprise Readers` site group, shared with every
other family deployed to the site, and grants it `Read` on every list in this
family. The group starts empty only if no family has deployed to the site yet;
it gains a member when any family's build is run with `--enterprise-reader
<account>`, which enrols exactly that one account and nothing else.
`rollback.js.txt` does not remove it: rollback deletes lists, not site groups
or role assignments, so the group and any account enrolled in it survive a
rollback.

If the group already holds anyone other than that account, the deploy
**aborts before enrolling** and removes nobody. Before you clear anyone out,
check who it is: the group is shared by every family on this site, so the
unexpected member is most likely **another family's reporting account**, and
removing it silently breaks that family's reporting. Agree one reader account
for the site and rebuild with that address, or rebuild without the flag. Only
clear the group in Site permissions > Groups once you know nothing else needs
the account.

On one Microsoft 365 group-connected Team Site (measured 2026-08-11) the
enrolled account ends up with the built-in `Read` on each list and
`Use Remote Interfaces` intact at web scope. Publishing sites, where
lockdown mode is on by default, and the reporting client's own list
enumeration are still unverified, so the end-to-end path (Power BI or any
other API client) is not yet proven. See the danger block in the mapping
reference's Security section.
