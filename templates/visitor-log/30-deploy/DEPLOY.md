# Deploying the visitor log (administrator)

Shared procedure: [`templates/README.md`](../../README.md) with
`<name> = visitor-log`. Template-specific notes below.

## Before you build

- [ ] `VI_` prefix free on the target site.
- [ ] Kiosk decision made: reception records, or a mounted tablet showing
      the New-item form for self-service (both work with nothing extra).
- [ ] The paper book has a cutover date.

## After the paste — verification checklist

- [ ] `VI_Visit` exists; `SignedInAt` required.
- [ ] Sign a test visitor in; the *On site now* view (below) shows them;
      sign them out; the view empties.
- [ ] Any Member can create and edit rows (hosts sign their own guests
      in/out).
- [ ] Front desk bookmark / kiosk form set up; assembly-point wardens know
      how to open *On site now* on a phone.
- [ ] Delete the test row.
- [ ] Even as an owner: changing a deployed column's type, choices or
      settings is refused (sealed) and List settings offers no "Delete
      this list"; a display-name rename is still possible — it is
      drift, reverted and reported at the next re-paste.

## Recommended views

| View | Filter / sort |
|---|---|
| **On site now** | SignedOutAt is empty — THE view; this is the muster list |
| Today | SignedInAt = today |
| Contractors on site | On site now + VisitorType = Contractor |
| Never signed out | SignedOutAt empty and SignedInAt before today — the daily tidy-up |

## Redeploying

Bump `schema_version`, rebuild, re-paste.
