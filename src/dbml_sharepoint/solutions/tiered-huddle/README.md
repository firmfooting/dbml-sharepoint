# Tiered huddle boards

The daily operating system, as four lists: `TH_Tier1Board` (team),
`TH_Tier2Board` (department or service), `TH_Tier3Board` (site or
executive), and `TH_Escalation` for everything that cannot be resolved at
the tier that raised it.

**The value case.** Most organisations already huddle. Almost none can
answer "which streams reported last fortnight, and which quietly stopped?"
One row per day per tier, one status column per reporting stream, and the
*Last 14 days* view **is** the wall chart — live, attributed, and readable
from a phone. A blank cell is not a pass: it is a visible record that a
stream did not report, which is the control the paper board never gave you.

The escalation list is the other half. An item raised at a team huddle and
sent up is a row with an owner, a due date and a route — not a promise made
in a corridor. Items travel both ways: up when a tier cannot fix something,
down when the work belongs closer to the front line, and back again as
*Returned to tier*.

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Rename the reporting streams to yours; delete a board list if you run two tiers |
| 2 | `20-configure/` | Prefix; the field sets and formatting that follow your stream names |
| 3 | `30-deploy/` | Administrator: build, paste, verify; learn the stream lifecycle |
| 4 | `40-adopt/` | Chairs: the 90-second daily routine |
| 5 | `50-govern/` | Tier ownership, escalation response times, stream lifecycle |

**Customisation points — do these before the first deploy:**

- **The stream sets.** The three lists ship with six, eight and ten streams.
  They are placeholders for your operating model, not a recommendation. A
  stream is four small edits: a `<Stream>Status` / `<Stream>Note` pair in
  `schema.dbml`, entries in the matching `field_sets` lists, a
  `column_formatting` entry, and a pair of names in that board's form body
  under `20-configure/formatting/`. All four are worked through in
  `30-deploy/deploy.md`.
- **The shipped retirement example.** Tier 3 carries an
  `EnvironmentStatus` / `EnvironmentNote` pair marked retired in
  `retired_columns:`, as a worked example of folding one stream into
  another. If you have never deployed this template there is no history to
  preserve, so delete the pair from `schema.dbml` and the `retired_columns:`
  block from `mapping.yaml` before your first paste. **After** a deploy,
  deleting a column declaration is the one thing never to do — see
  `30-deploy/deploy.md`.
- **Number of tiers.** Running two? Delete the third board list from
  `schema.dbml`, from `mapping.yaml`, and its form body from
  `20-configure/formatting/`, before you deploy. The `tier` enum keeps four
  members so escalation to an existing governance committee works without a
  schema change.
- **`OverallStatus` is set by the chair, not calculated.** That is
  deliberate: it lets a chair call a day Amber for something that belongs to
  no stream, and it keeps the column indexable, which a calculated column
  can never be. The cost is that it can disagree with the stream columns —
  treat a disagreement as a conversation, not a data-quality defect.

**What this template does not do.** There are no "days since" counter
columns: SharePoint calculated columns cannot reference today's date, so a
live day count is impossible in the list and a hand-typed one rots the first
time someone forgets. Derive it in the reporting layer from the board
history, which is what the generated reporting bundle is for. There is no
cross-tier rollup view either — a view spans one list; a rollup is a report.
