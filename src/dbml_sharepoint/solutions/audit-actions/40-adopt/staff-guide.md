# Audit actions: staff guide

## Action owners (the people named in `Owner`)

You own an agreed management action: the thing your organisation formally
told an auditor it would do. The register is where that promise is visible.

- **Know your rows**: open **Open by owner**, the default view, and find
  your name in the group list. That is everything still open with your name
  on it, soonest committed date first. It is already built; you don't need
  to make it.
- **Progress**: send a dated update to an Audit Coordinator whenever
  something moves (they append it to Notes; single-handed upkeep keeps the
  trail clean). Monthly at minimum for High/Critical items.
- **Done ≠ closed.** Closure needs evidence: the policy as published, the
  reconfigured setting's screenshot, the training records, whatever proves
  the action happened. Send the evidence link with your "done".
- **Can't make the date?** Ask for a formal extension *before* it passes
  (see governance for who can grant one). A revised date agreed in advance
  is management; a silently blown one is a finding waiting to happen. Once
  a **Revised due** date is recorded, that becomes the committed date: the
  *Overdue* view stops counting your row against the original, and
  **Days late** measures from the revised one.

## The views

### AU_Audit

| View | What it shows |
| --- | --- |
| **Recent reports** | The default. Every review, most recent report first. |
| **By type** | The same, grouped by internal / external / accreditation / regulator / self-assessment. |

### AU_Recommendation

| View | What it shows |
| --- | --- |
| **Open by owner** | The default. Everything still open, grouped by who owns it. |
| **Overdue** | Open rows past their *committed* date: the revised one where there is one, the original where there isn't. |
| **Awaiting evidence** | Actions reported done whose evidence has not been verified. The coordinators' reading queue. |
| **Committee pack** | Everything not closed, grouped by audit. This is the paper. |
| **Closed, last 90 days** | Recent closures with **Days late** and the evidence link. A *rolling* ninety days, not "this quarter". |

None of these is something you build, and none should be renamed. A
redeploy puts the declared name back.

## Audit coordinators

1. **New report lands**: create the Audit row, then one Recommendation per
   recommendation, worded as the report words it, with the *agreed*
   management action, owner and committed date from the formal response.
2. **Chase rhythm**: work the *Overdue* view weekly; append owner updates
   to Notes, dated, newest first.
3. **Closing**: work the *Awaiting evidence* view. Verify the evidence
   actually demonstrates the action (read it; a link to a folder is not
   evidence), attach **Evidence URL**, set **Closed date** and Status
   **Closed**. The list refuses to save a Closed row without a **Closed
   date**, and **Days late** computes itself from it against the committed
   one. **The Evidence URL is not enforced**: SharePoint cannot hold a
   save rule against a link column, so a Closed row with no evidence
   saves. That one is on you and on the coordinator checking behind you;
   the *Closed, last 90 days* view shows the column so an empty one is
   visible to the committee.
4. **Risk accepted** is a legitimate ending, but only with the sign-off
   the governance rules require, recorded in Notes. Nothing checks that
   sign-off: Notes is rich text and no save rule can read it. Risk
   accepted rows render grey rather than green, because they are an
   honest ending in which the action does not happen.
5. **Committee time**: the *Committee pack* view IS the paper. Stop
   rebuilding spreadsheets. It is grouped by audit and sorted by committed
   date; the severity ranking is carried by the **Finding rating**
   colours rather than by the sort. See `30-deploy/deploy.md` for why
   SharePoint cannot sort a rating column in rating order.
