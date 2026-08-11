# Deploying the asset register (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = asset-register`. Run order: **assess** the target site (paste
`build/assess.js.txt`, read-only; the verdict must be COMPATIBLE or an accepted
DEGRADED) → **review** `build/deploy-manifest.md` (must show 0 validation
errors) → **paste** `build/deploy.js.txt` from a Site Owner's console →
**verify** against the checklist below. Template-specific notes follow.

## Before you build

- [ ] `AS_` prefix free on the target site.
- [ ] `Category`/`Status` choices match how you actually classify equipment.
      **`Status` members are named inside every deployed view filter** —
      *Stocktake* is `In service` or `Assigned`, *By holder* is `Assigned`,
      *By location* and *Warranty expiring* exclude `Retired` and
      `Disposed`, and *Retired and disposed* is exactly those two. Rename
      one and a view goes quietly empty. Decide **before first deploy**.
- [ ] Decide the Members-can-edit question (see template README) — change
      the Members assignment to `Read` plus a custodians group *before*
      first deploy if you want the tighter model.
- [ ] The Asset header shows `Asset: <title>` on a saved row and `New
      asset` before the title is typed, updating live. The Location form
      has its own header for the same reason it has a form at all: a bare
      Title box is how a location catalogue ends up with three spellings
      of the same room.

## Optional: the seeded demonstration build

The Location lookup, the warranty colouring and four of the five Asset
views are invisible on an empty pair of lists. To see them working,
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
first, then `demo-data.js.txt`, from the same bundle. It creates four
locations and six assets — one per status, with a warranty falling due
inside the sixty-day window and two that have already lapsed, so the
overdue treatment is visible. Every asset points at a demo location
through the lookup, which is also the cheapest confirmation that the
lookup provisioned correctly.

**Delete the demo rows before active use.** Every demo Title begins with
`[DEMO] `, so they are obvious in every view, they are matched by Title on
re-paste (running it twice never duplicates), and `rollback.js.txt` treats a
list whose rows are *all* demo-marked as demo-only content. Do not seed a
site that already holds real assets.

## After the paste — verification checklist

- [ ] `AS_Location` and `AS_Asset` exist, in that creation order.
- [ ] `AS_Location` has its one declared view, **Locations by name** (the
      default). `AS_Asset` has all five: **Stocktake** (the default), **By
      holder**, **By location**, **Warranty expiring**, **Retired and
      disposed**. If you seeded, none is empty. The generated **All Items**
      recovery view is hidden from the modern view bar on both lists,
      because both have an authored default.
- [ ] **The old recommended-views table's "Stocktake sheet" is the
      default view, named "Stocktake".** It sorts by Location then Asset
      Tag — SharePoint sorts a lookup column by its displayed value, so
      that is the order you will physically walk the building in.
- [ ] **Seed Locations first** — add your buildings/rooms/sites now; the
      Asset form's Location dropdown reads from it. (If you seeded, four
      demo locations are already there; delete them once your real ones
      are in.)
- [ ] Create a test asset: unique `AssetTag` enforced (try a duplicate —
      rejected); Purchase `2026-01-01` + Warranty `2028-01-01` →
      **Warranty Months = 24**, drawn as a bar against a 60-month scale.
- [ ] Set a `Warranty Expiry` in the past on an item that is **In
      service**: the date turns red with a warning icon. Set the same
      item's `Status` to **Disposed**: the red goes away. That guard is
      deliberate — most disposed equipment left service long after its
      warranty lapsed, and a register that shouts about all of it teaches
      people to ignore the colour.
- [ ] The Asset New form shows four sections — **What it is**, **Where it
      is**, **Purchase and warranty**, **System** — each holding the
      fields named in `20-configure/formatting/asset-form-body.json`.
      **System** holds only `Warranty Months`; it is calculated, so it is
      absent from the New form and the section renders as a bare heading
      there. That is cosmetic and expected.
- [ ] The form reacts: set `Status` to **Retired** or **Disposed** and
      **Assigned To** disappears. It keeps whatever was there — SharePoint
      has no mechanism to clear a hidden field — so a disposal that needs
      the holder cleared is done before the status change, not after.
- [ ] Save rules, each with its own message: a **Purchase Date** in the
      future is refused, and so is a negative **Purchase Cost**. The list
      rule refuses an asset that has a **Warranty Expiry** but no
      **Purchase Date** — without both, the month count is blank and the
      warranty term cannot be checked.
- [ ] Assign the test asset to yourself (`Assigned To`), set Status
      `Assigned`, and confirm it appears in **By holder** under your name.
- [ ] Delete the test asset.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Redeploying

Bump `schema_version` in `release.yaml`, rebuild, re-paste. Existing rows
untouched; declared settings reconciled.

## Enterprise reporting access

The deploy creates an empty `"AS Enterprise Readers"` site group holding `Read` on
every list in this family. It stays empty unless the build was run with
`--enterprise-reader <account>`, which enrols exactly that one account
and nothing else. `rollback.js.txt` does not remove it: rollback deletes
lists, not site groups or role assignments, so the group and any account
enrolled in it survive a rollback.

The end-to-end reporting path this grant enables (Power BI or any other
API client) is not yet verified — see the danger block in the mapping
reference's Security section for why.
