# Deploying service requests (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = service-requests`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) -> **review** `build/deploy-manifest.md` (must show 0 validation
errors) -> **paste** `build/deploy.js.txt` from a Site Owner's console ->
**verify** against the checklist below. Template-specific notes follow.

## Before you build

- [ ] `SR_` prefix free on the target site.
- [ ] `Category` values map 1:1 to teams that will actually work a queue.
      A category nobody owns is a black hole with a name.
- [ ] **Two categories are named in the deployed views.** *Facilities
      queue* filters on `Facilities / maintenance` and *IT queue* on
      `IT / equipment`. Rename either member and its view goes empty with
      no error. Either keep the two strings, or edit the two `where`
      clauses in `mapping.yaml` in the same change. Every other category
      is served by *Open by category*, which groups rather than filters
      and so needs no editing when you add one.
- [ ] **Renaming a `Priority` member can reorder every queue.** The queues
      sort `Priority` descending, and that puts Urgent above Normal above
      Low only because SharePoint sorts a Choice column as text and
      "Urgent" > "Normal" > "Low" alphabetically. A member renamed to
      "Critical" sorts below "Low". If you change the priority
      vocabulary, check the ordering on a seeded site before go-live.
- [ ] Each category's team knows the queue habit is coming (see 40-adopt).
- [ ] The header shows `Request: <title>` on a saved request and `New
      request` before the title is typed, updating live.

## Optional: the seeded demonstration build

Six queues over an empty list demonstrate nothing. To see the queues, the
priority pills, the status colours and the turnaround bars working,
rebuild with `--seed`:

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

That bundle contains an extra file, `demo-data.js.txt`. Paste `deploy.js.txt`
first, then `demo-data.js.txt`, from the same bundle. It creates six requests:
one per status and one per priority, with a facilities request and an IT
request so both named queues fill, a request waiting with its reason
stated, and two closed-out rows inside the ninety-day turnaround window.
Every one is requested by the operator who pastes it, so *My requests*
also has content.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO]`, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js.txt` requires
per-list confirmation before every delete. Do not seed a
site that already holds real requests.

## After the paste: verification checklist

- [ ] `SR_Request` exists; custom level **SR Submit Only** exists.
- [ ] All six declared views appear: **Open by category** (the default),
      **Facilities queue**, **IT queue**, **Waiting**, **My requests**,
      **Turnaround**. If you seeded, none of them is empty. The generated
      **All Items** recovery view is hidden from the modern view bar
      because this template has an authored default.
- [ ] **What replaced the old recommended-views table**, since two rows of
      it could not be built as written:
      - The literal `*(one per category)* ...` row is **not** shipped as one
        view per category. A static view cannot be generated per enum
        member, and hand-building five of them means rebuilding them every
        time the catalogue changes. It ships as **Open by category** (one
        view grouped on `Category`, collapsed) plus the two per-team
        queues this template names by hand. Add a category and the grouped
        view picks it up with no work.
      - **Turnaround report** asked for completions "in month" with a
        summary of `DaysToComplete`. CAML has no calendar-month predicate,
        so the shipped **Turnaround** view is a rolling **ninety days**;
        the first business day of a month is where the two differ and
        somebody reconciling a monthly pack will notice. The summary IS
        there: the view totals `DaysToComplete` as a **mean**, so each
        collapsed category shows its average turnaround and the window
        shows an overall one. A mean rather than a sum, because adding up
        day-counts answers nothing. "How long does this team take" is the
        question the report exists for.
- [ ] `Requested 2026-07-01` + `Completed 2026-07-04` ->
      **Days To Complete = 3**, drawn as a bar against a 30-day scale and
      coloured from that request's **Priority**, not from its own value.
- [ ] The New form shows five sections: **Describe the request**,
      **Triage**, **Resolution**, **Ownership**, **System**, each holding
      the fields named in
      `20-configure/formatting/request-form-body.json`. **System** holds
      only `Days To Complete`; it is calculated, so it is absent from the
      New form and the section renders as a bare heading there. That is
      cosmetic and expected.
- [ ] The form reacts as you fill it in. On a New form **Assigned To**,
      **Completed Date** and **Resolution** are all absent. A requester
      is never asked who will fix their screen or when it was done. On an
      existing request, set `Status` to **Waiting - parts or approval** and
      **Resolution** appears; set it to **Completed** or **Declined** and
      **Completed Date** appears too. Move it back to **In progress** and
      both hide again, keeping whatever was typed.
- [ ] Save rules, each with its own message: a **Requested Date** or
      **Completed Date** in the future is refused. The list rule refuses a
      request set to **Completed** or **Declined** with either the date or
      the Resolution empty. Try all three combinations.
- [ ] As an ordinary Member: submit works, editing afterwards doesn't.
- [ ] As a Service Teams member: pick up the test request (Assigned To,
      Status), complete it.
- [ ] Populate **SR Service Teams**; delete the test row.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible. It is
      drift, reverted and reported at the next re-paste.

## Redeploying

Bump `schema_version`, rebuild, re-paste.

## Enterprise reporting access

The deploy declares the `dbml Enterprise Readers` site group, shared with every
other family deployed to the site, and grants it `Read` on every list in this
family. The group starts empty only if no family has deployed to the site yet;
it gains a member when any family's build is run with `--enterprise-reader
<account>`, which enrols exactly that one account and nothing else.
`rollback.js.txt` does not remove it: rollback deletes lists, not site groups
or role assignments, so the group and any account enrolled in it survive a
rollback.

A later build that omits the flag does not put the group back to empty:
enrolment only runs when `--enterprise-reader` is given, so an account enrolled
by an earlier build, of this family or any other sharing the site, keeps its
membership and its `Read` grant on every list it was declared against. Removing
it is manual: clear it in Site permissions > Groups.

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
