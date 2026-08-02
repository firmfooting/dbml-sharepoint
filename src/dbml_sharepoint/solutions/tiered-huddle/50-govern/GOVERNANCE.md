# Tiered huddle boards — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Tier 1 chair (per team) | `Chair` on `TH_Tier1Board` | A row every working day; escalating what the team cannot fix |
| Tier 2 chair (per department or service) | `Chair` on `TH_Tier2Board` | The same, plus acting on Tier 1 escalations and delegating what belongs below |
| Tier 3 chair (site or executive) | `Chair` on `TH_Tier3Board` | The same, plus the site view and the Tier 4 relationship |
| Stream lead (per reporting stream) | — | That stream reporting every day it is meant to; explaining a run of blanks |
| Every escalation owner | `Owner` | Status truthfulness and delivery |
| Site Owners | — | Group membership, deploys, the stream lifecycle |

## The cadence that makes this work

1. **Every huddle produces a row, including the ones that did not happen.**
   The *Not held* view is reviewed weekly by the tier above. Cadence is the
   first thing to decay and the easiest thing to see.
2. **Every tier opens by reading the tier below's board.** Two minutes. It is
   the difference between a board and wallpaper.
3. **Blanks are chased, not ignored.** A stream with three blanks in a
   fortnight goes on the agenda of the tier that owns it. The blank is the
   whole reason the boards are wide and sparse rather than a free-text
   summary.
4. **Reds normally carry an escalation.** A Red with nothing on
   `TH_Escalation` is either not really Red or is being absorbed silently.

## Escalation response times

Set by `Priority`, measured from `RaisedDate`, and owned by the tier named in
`TargetTier`. Adjust these to your organisation before you publish this
document — they are a starting position, not a standard.

| Priority | Target tier acknowledges | Target date agreed by |
|---|---|---|
| Critical | Same huddle | Same day |
| High | Next huddle | 2 working days |
| Medium | 2 working days | 5 working days |
| Low | 5 working days | 10 working days |

*Acknowledges* means the escalation has an owner at the target tier and a
`DueDate`. The **Overdue** view is read aloud at the target tier's huddle;
three consecutive appearances go to the tier above as a new escalation about
the escalation.

*Returned to tier* is a legitimate outcome and must carry a `Resolution`
explaining why. Silently closing something a tier could not fix is the
failure mode this list exists to prevent.

Nothing here moves an escalation between tiers automatically. `Direction`,
`RaisedAtTier` and `TargetTier` record the journey, and a re-raised item is a
new row that names the old one in `Notes` — the deployer provisions
structure, not process automation. If you want the movement automated, that
is a Power Automate flow over the deployed lists.

## Stream lifecycle — why it is a governed act

Adding or retiring a reporting stream changes what the organisation says it
watches. It is a board decision, recorded like any other, and then a
deployment (the mechanics are in `30-deploy/DEPLOY.md`: the schema, the field
sets, the column formatting, and the board's form body under
`20-configure/formatting/`).

**Retiring never deletes.** A retired stream keeps its columns and its
history: the columns leave every view and the new-item form, their titles
gain " (retired)", and every past value stays readable and stays in the
reporting bundle. Deleting the column would throw away the record of what the
organisation used to watch — which is exactly the question an auditor asks.

**The declaration stays in `schema.dbml`.** Deleting it leaves a live column
the schema no longer declares, which the `_UserAddedColumns.pq` drift audit
reports on every refresh forever, eroding the "any row means investigate"
contract that makes that audit worth running.

Review the stream set **annually**, and after any structural change to the
organisation. Streams that have been "Not applicable" for a quarter are
candidates for retirement; a stream nobody can name an owner for already is.

## Hand-off to and from `meeting-actions`

The two templates interconnect by **process hand-off, not list lookups**.
Nothing links; a lookup can target only one list and would couple five lists
together for no gain.

**Escalation to action.** When an escalation stops being a daily-huddle item
and becomes tracked work — it needs a project, a budget line, or a committee
decision — the receiving forum raises it as an `MA_ActionItem` against the
`MA_Meeting` that accepted it. The escalation stays open until that forum
confirms receipt, then moves to *Resolved* (or *Returned to tier* if the
forum declined it) with the `Resolution` naming the meeting and date. One
sentence, so the trail is followable by a human without a join.

**Action to board.** When a meeting produces an action that needs daily
visibility — a recovery plan, a temporary control, a change everyone must
follow — the owner raises it as a *Delegated down* escalation on
`TH_Escalation` against the tier that must act, and the relevant stream note
carries it on the board until it is done. The `MA_ActionItem` stays the
system of record for delivery; the board carries the daily visibility.

## Data-quality rules

1. One row per board per working day. `BoardDate` is unique, so duplicates
   are impossible by construction.
2. A non-Green status carries a note. A Green does not need one.
3. `OverallStatus` is the chair's call and may legitimately disagree with the
   stream columns — a disagreement is a conversation, not a defect.
4. Every escalation has one named person as `Owner`. Never a team, never a
   role with no incumbent.
5. Resolutions say what was done, not that something was "actioned".

## Retention

Board rows are small and are the organisation's operational memory: keep
them. Versioning is capped at 50 major versions per board row (a daily record
edited several times a day burns versions fast, and old versions of a huddle
board are worthless) and 100 on `TH_Escalation`, where the edit trail is the
audit trail.

Export before decommissioning. Never run `rollback.js.txt` against a site holding
real rows — it is for a failed first provision on an empty site, and for
clearing demo data.
