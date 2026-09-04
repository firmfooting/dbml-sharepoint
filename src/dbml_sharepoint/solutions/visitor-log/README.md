# Visitor log

*Theme: operations & service..*

The front-desk sign-in book, digitised: one list (`VI_Visit`) recording who
is on site, hosted by whom, since when, with the sign-out that paper books
never collect. The deployed default view, **On site now**, *is* the
**evacuation muster list**, which is the real reason this is safety
infrastructure, not admin.

**The value case.** The paper book fails exactly when it matters: at the
assembly point, upside down in the rain, with half the sign-outs missing.
Digitised, "who is in the building?" is the view the list already opens on;
contractors carry an induction-sighted flag; and the visit history answers
the follow-up questions (who was on site that Tuesday?) that paper archives
can't. Deployable in an afternoon; adopted by the first visitor.

**What deploys with it:** four views (*On site now*, *Signed in today*,
*Contractors on site*, *Never signed out*), a three-section form with its
own induction section, save rules that refuse a future sign-in, and six
demo visits behind `--seed` so the muster list has something in it the
first time a warden opens it.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Fit visitor types to your site |
| 2 | `20-configure/` | Prefix; everyone-signs-in model |
| 3 | `30-deploy/` | Administrator: build, paste; set up the front-desk form |
| 4 | `40-adopt/` | Reception habits + the evacuation drill |
| 5 | `50-govern/` | Privacy retention, contractor rules, muster procedure |

**Customisation points:** `VisitorType` (note that **Contractor** and
**Student / placement** are the two members the induction question is
asked of); and whether visitors self-serve on a kiosk/tablet
(the New-item form on a mounted tablet works today, no extra software) or
reception records for them.
