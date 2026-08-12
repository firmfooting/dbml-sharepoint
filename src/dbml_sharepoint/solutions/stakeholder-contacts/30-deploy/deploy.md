# Deploying stakeholder contacts (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = stakeholder-contacts`. Run order: **assess** the target site
(paste `build/assess.js.txt`, read-only) → **review**
`build/deploy-manifest.md` (must show 0 validation errors) → **paste**
`build/deploy.js.txt` from a Site Owner's console → **verify** against the
checklist below. Template-specific notes follow.

## Before you build

- [ ] `SC_` prefix free on the target site.
- [ ] `OrgType`/`InteractionType` enums fit your stakeholder landscape.
      `OrgType` drives the grouping of the *By type* view, so an
      organisation kind missing from the enum has no group.
- [ ] **Privacy check**: site membership is scoped to the relationship-
      holding teams; the privacy rules in `50-govern/governance.md` have an
      owner. **Read that page before you seed anything** — see below.
- [ ] Each header shows `Organisation: <name>` / `Contact: <name>` /
      `Interaction: <title>` on a saved row and `New organisation` / `New
      contact` / `New interaction` before the title is typed, updating
      live.

## Optional: the seeded demonstration build

The grouped views and the active/moved-on chip are invisible on empty
lists. To see them working, rebuild with `--seed`:

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
first, then `demo-data.js.txt`, from the same bundle. It creates four
organisations (one deliberately with no owner), four contacts (one who has
moved on) and five interactions (one older than the *Recent activity*
window).

**The demo does not invent people, and that is deliberate.** This
register's privacy rules are load-bearing rather than boilerplate. Every
demo Title names a **role at an organisation** rather than a person, every
person column resolves to the operator, and the only contact details are
RFC 2606 reserved `example.com` / `example.org` addresses and an
undialable number. A seeded register full of plausible names and phone
numbers would teach the opposite of what `50-govern/governance.md` asks
for, on the first screen anyone sees. **Website is blank** on every demo
organisation: a SharePoint URL column takes a structured value over REST
rather than a bare string, and this repository does not seed a write it
has not read back from a live list.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, they are matched by Title on re-paste (running it twice never
duplicates), and `rollback.js.txt` treats a list whose rows are *all*
demo-marked as demo-only content. Do not seed a site that already holds
real contacts.

## After the paste — verification checklist

- [ ] `SC_Organisation`, `SC_Contact`, `SC_Interaction` exist, created in
      that order (the lookup chain requires it).
- [ ] **Organisation**: **By owner** (the default, grouped and collapsed)
      and **By type**.
- [ ] **Contact**: **Active by organisation** (the default, grouped and
      collapsed) and **Moved on**.
- [ ] **Interaction**: **Recent activity** (the default) and **By
      contact** (grouped and collapsed). If you seeded, none of the six is
      empty. The generated **All Items** recovery view is hidden from the
      modern view bar on all three lists, because each has an authored
      default.
- [ ] **The Active column renders as a chip.** On a contact who is active
      it reads *Active* on the token table's blue; on one who has moved on
      it reads *Moved on* on grey. This is the one item on this list worth
      looking at twice: SharePoint treats a Yes/No column as a **boolean**
      rather than the words "Yes" and "No", so the formatter tests
      truthiness. That is Microsoft's own documented idiom, but it is
      documented rather than read back off a live list here — if both
      states render the same colour, that is where to look, and
      `20-configure/formatting/contact-active.json` is a two-line fix.
- [ ] The Organisation form shows **The organisation** and **Ownership**.
      The Contact form shows **The person**, **How to reach them** and
      **Standing and notes**. The Interaction form shows **What
      happened**, **What was said** and **Our record**. Every column sits
      in one of them.
- [ ] Log an interaction dated tomorrow. Refused, with a message saying
      this list is a record rather than a calendar. That is the **only**
      save rule on this template — see below.
- [ ] Create a test organisation → a test contact in it (Organisation
      lookup offers it) → a test interaction with them (Contact lookup
      offers them).
- [ ] `Contact.IsActive` defaults to **Yes**.
- [ ] Any Member can create all three.
- [ ] Delete the test rows (interaction → contact → organisation).
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

### Three notes on what ships, and what could not

- **"By contact — the handover view"** was published as a view *filtered
  to one contact*. A static view cannot filter to one parent record; the
  choices were one view per contact, rotting from the day it was made, or
  one grouped view that never does. What ships is **By contact**, grouped
  by the Contact lookup and collapsed. Opening a contact's group before a
  meeting *is* reading the thread, and it is deliberately unfiltered
  because the whole history is what makes that worth doing.

- **"Recent activity" is a rolling ninety days**, not a calendar period.
  The published row had no filter at all, which on a register anyone has
  actually used means every interaction ever. CAML has no calendar
  predicate — `today±N` is what exists — so the view is titled *Recent*
  rather than named for a period, and cannot lie about which. Nothing is
  lost: *By contact* carries no filter.

- **There is no "Unowned organisations" view, and there cannot be.**
  `50-govern/governance.md`'s quarterly check wants every organisation to
  have a live owner, and the obvious filter — *Owner is empty* — is not
  expressible. A person column needs a `property` accessor to be compared
  at all (there is no defensible default between a name, an email and an
  id) and CAML refuses every accessor it might be given; the current-user
  sentinel resolves that for equality only, and there is no equivalent for
  a null test. **The blank group at the end of *By owner* is the answer**
  — it is exactly the unowned list, it is where the quarterly check reads
  it, and the seeded build ships an unowned organisation so you can see it
  before you need it.

### The rules this register does not enforce

One save rule ships: an interaction cannot be dated in the future. That is
all, and the emptiness is a finding rather than an oversight. This
register's real rules are about *what may be recorded* — business-contact
facts only, no opinions, no personal details, no sensitive attributes —
and no formula can read the difference between a professional note and a
personal one. They stay governance checks, and `50-govern/governance.md`
now says so in as many words. The form headers carry the instruction to
the one place it can act: the moment someone is typing.

## Redeploying

Bump `schema_version`, rebuild, re-paste. Rows untouched; views, forms,
formatting and the save rule reconciled to the declaration.

## Enterprise reporting access

The deploy creates an empty `"SC Enterprise Readers"` site group holding `Read` on
every list in this family. It stays empty unless the build was run with
`--enterprise-reader <account>`, which enrols exactly that one account
and nothing else. `rollback.js.txt` does not remove it: rollback deletes
lists, not site groups or role assignments, so the group and any account
enrolled in it survive a rollback.

A later build that omits the flag does not put the group back to empty:
enrolment only runs when `--enterprise-reader` is given, so an account
enrolled by an earlier build keeps its membership and its `Read` grant on
every list. Removing it is manual — clear it in Site permissions > Groups.

If the group already holds anyone other than that account, the deploy
**aborts before enrolling** and removes nobody — clear it in Site
permissions > Groups and paste again, or rebuild without the flag.

On one Microsoft 365 group-connected Team Site (measured 2026-08-11) the
enrolled account ends up with the built-in `Read` on each list and
`Use Remote Interfaces` intact at web scope. Publishing sites — where
lockdown mode is on by default — and the reporting client's own list
enumeration are still unverified, so the end-to-end path (Power BI or any
other API client) is not yet proven. See the danger block in the mapping
reference's Security section.
