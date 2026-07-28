# Deploying the visitor log (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = visitor-log`. Template-specific notes below.

## Before you build

- [ ] `VI_` prefix free on the target site.
- [ ] Kiosk decision made: reception records, or a mounted tablet showing
      the New-item form for self-service (both work with nothing extra).
- [ ] The paper book has a cutover date.

## Create the views — do this before anyone relies on the list

**The deploy creates only the unfiltered All Items recovery view.**
`mapping.yaml` declares no process views, so after the paste `VI_Visit` has
every column available but none of the working filters below. Build these
by hand in List settings → Views (or add them to
`mapping.yaml` under `views:` and redeploy, which is reproducible and what
you want if you run more than one site).

| View | Filter / sort |
|---|---|
| **On site now** | `SignedOutAt` is empty — THE view; this is the muster list |
| Today | `SignedInAt` = today |
| Contractors on site | On site now + `VisitorType` = Contractor |
| Never signed out | `SignedOutAt` empty and `SignedInAt` before today — the daily tidy-up |

**On site now does not exist until you make it.** Everything this template
says about evacuation — in this file, in `README.md`, in
`40-adopt/STAFF-GUIDE.md` and in `50-govern/GOVERNANCE.md` — depends on
that view. A muster procedure rehearsed against a view nobody created fails
at the assembly point, which is the one moment it exists for. Create it,
verify it below, and only then run the drill.

## After the paste — verification checklist

- [ ] `VI_Visit` exists; `SignedInAt` required.
- [ ] The four views above exist, with the filters above.
- [ ] Sign a test visitor in; *On site now* shows them; sign them out; the
      view empties.
- [ ] Any Member can create and edit rows (hosts sign their own guests
      in/out).
- [ ] Front desk bookmark / kiosk form set up; assembly-point wardens have
      opened *On site now* on their own phone, signed in, at least once.
- [ ] Delete the test row.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Redeploying

Bump `schema_version`, rebuild, re-paste.
