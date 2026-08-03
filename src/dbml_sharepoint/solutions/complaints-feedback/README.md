# Complaints & feedback

Every complaint, compliment and suggestion from the people you serve, with
the response clock visible. One list: `CF_Feedback`. Acknowledgement and
resolution times are calculated and drawn as bars coloured by the item's
severity; outcomes are recorded, not remembered.

**The value case.** Feedback handled in inboxes produces the two worst
outcomes: complainants who never hear back, and organisations that never
learn. A register gives every item an owner and two visible clocks
(days-to-acknowledge, days-to-close), turns "how are we doing?" into a
monthly view instead of an anecdote, and produces exactly what ombudsmen,
accreditors and boards ask for. Front-line staff record; handlers respond;
trends surface.

**A deliberate privacy posture**: ordinary site members get **no access** —
complaints identify people. Recorders can submit; handlers manage. Widen
deliberately, not by default.

**What deploys with it:** five views — *Open by handler* (the default,
grouped and collapsed), *Triage*, *Unacknowledged*, *Closed last 30 days*
and *The learning shelf* — a five-section form that asks a recorder only
what a recorder can answer, save rules that refuse an item moved past
Received with no acknowledgement date and a closure with no outcome, and
six demo items behind `--seed`.

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Fit types/severity/outcome language to your obligations |
| 2 | `20-configure/` | Prefix; the recorder/handler/no-members model |
| 3 | `30-deploy/` | Administrator: build, paste, verify the access split |
| 4 | `40-adopt/` | Recorders' guide (front line) + handlers' guide |
| 5 | `50-govern/` | Response SLAs, escalation, privacy, learning loop |

**Customisation points:** `FeedbackType`/`Severity`/`Outcome` enums, and
the SLA table in governance (regulated sectors: put your statutory
timeframes in). Note that `Status` and `Outcome` members are named inside
deployed view filters, form rules and the save rule, and that the SLA
table sets the two day-count bars' scales — `30-deploy/deploy.md` lists
both couplings before you build.
