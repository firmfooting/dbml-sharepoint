# Credentialing register

*Theme: people & relationships — built for credentialed workforces
(healthcare, but equally trades, legal, education)*

Who is credentialed to do what, on whose decision, until when. Two lists:
`CR_Practitioner` (each credentialed person, their registration and their
approved **scope of practice**) and `CR_Credential` (each registration,
qualification, certification or privilege, with expiry and evidence).

**The value case.** In a health service this register is not optional
paperwork — evidencing current registration and defined scope of clinical
practice is core clinical governance (NSQHS Standard 1 territory), and the
question accreditors and coroners ask is precise: *how did the organisation
know this person was credentialed for this activity on this date?* The
register makes the answer a filter: scope decisions with dates and review
cycles, credentials with expiries and evidence links, and an *expiring
soon* view that ends the annual registration-renewal scramble.

**Deploys with:** nine views (practitioners by discipline, registrations
expiring, scope reviews due, under review or lapsed, and ceased; then
credentials grouped into a per-practitioner file, expiring, missing
evidence, and expired), sectioned forms on both lists, a registration pair
that only appears for registered disciplines, three deadline dates that
turn red past due, a row wash on an expired credential inside the
credentialing file, four save rules, and eleven demo rows.

**Boundary:** this register **indexes** credentialing decisions and
evidence; primary source documents (AHPRA extracts, certificates) live in
your records system, linked. It holds staff professional data — read the
privacy posture in `50-govern/governance.md` before widening the site.

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Fit disciplines/credential types to your workforce |
| 2 | `20-configure/` | Prefix; coordinators-maintain, staff-read model |
| 3 | `30-deploy/` | Administrator: build, paste, verify; load the workforce |
| 4 | `40-adopt/` | Coordinators' guide; what managers may rely on |
| 5 | `50-govern/` | Scope decision authority, review cycles, privacy |

**Customisation points:** `Discipline` and `CredentialType` enums; whether
scope summaries are visible to all staff (default yes — knowing who may do
what is the register's operational point) or restricted.
