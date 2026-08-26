# RAID log

One project's risks, actions, issues and decisions on four lists that are
read together in the project meeting. Four lists: `RAID_ProjectRisk`,
`RAID_ProjectAction`, `RAID_ProjectIssue`, `RAID_ProjectDecision`.

**The value case.** Every project already keeps a RAID log, and almost
always as a spreadsheet with four tabs that one person owns and everybody
else asks for. This is the same four tabs, shared, with one owner per row,
dates that colour themselves when they slip, and a risk rating that is
calculated rather than typed. The point of RAID is that the four are read
*together*: an action exists to reduce a risk, an issue is a risk that
happened, and a decision is why the project chose to live with either.

**Four lists, and what each one is for:**

| List | Holds | The question it answers |
| --- | --- | --- |
| `ProjectRisk` | Uncertain events, rated on a 5x5 matrix | What could still stop this project delivering |
| `ProjectAction` | Work handed to a named person with a date | Who is doing what, and by when |
| `ProjectIssue` | Things that have already gone wrong | What is hurting the project right now |
| `ProjectDecision` | Decisions and why they were made | Why we did it that way |

The lists carry a `Project` prefix on their internal names because the
unprefixed names have to stay unique across the shipped library, and two
other templates already hold `Risk` and `Decision`. The deployed display
titles read *Project Risk*, *Project Action*, *Project Issue* and
*Project Decision*.

**Two optional lookups, and nothing else joins.** `ProjectAction` and
`ProjectIssue` each carry a `RelatedRisk` lookup to `ProjectRisk`, and both
are nullable on purpose: most actions are ordinary project work and most
issues arrived out of nowhere. The picker only offers **live** risks: it
shows a calculated `LiveRiskTitle` that is blank once a risk is Closed.
Decisions link to nothing. There is no project list and no meeting list,
because a project site already knows which project it is.

**The risk matrix is the risk-register matrix.** Pick **Likelihood** and
**Consequence** and SharePoint calculates **ResidualRiskRating**
(Low/Medium/High/Extreme) and a 1-25 **RiskScore**. There is nowhere to
type a rating that disagrees with the matrix, because the rating is never
typed. What is *not* carried over is the `MatrixVersion` guard: a project
log is created with the project and archived with it, so it never outlives
a revision of the matrix. Read the matrix section of
`50-govern/governance.md` before editing a cell.

**Eleven declared views**, deployed with the paste:

| List | Views |
| --- | --- |
| `ProjectRisk` | *Open* (the default), *Review due*, *Closed* |
| `ProjectAction` | *Open by person* (the default, grouped by owner), *My actions*, *Overdue*, *Done and dropped* |
| `ProjectIssue` | *Open* (the default), *By owner* (grouped), *Resolved and closed* |
| `ProjectDecision` | *Decision log* (the default) |

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Fit the severity and response choices to how your project talks |
| 2 | `20-configure/` | Prefix; **the matrix lives here**, edit with care |
| 3 | `30-deploy/` | Administrator: build, paste, verify the matrix calculates |
| 4 | `40-adopt/` | Project team guide: the meeting that makes it work |
| 5 | `50-govern/` | The two-hand discipline, and when a risk graduates upward |

**Customisation points:** the `raid_issue_severity` and
`raid_risk_response` enums; the matrix cells in `mapping.yaml`; and the
four form straplines under `20-configure/formatting/`, which are what a
project member reads before typing anything. The headers carry no links: a
placeholder URL is a dead link on every form until somebody replaces it, so
point at your project's own method from the column descriptions instead.

**Demo data.** Build with `--seed` and the bundle gains a
`demo-data.js.txt` that pastes six risks, six actions, five issues and four
decisions, all `[DEMO]`-titled, spanning every status and every rating band
so no declared view is empty on a first look. See `30-deploy/deploy.md`.
