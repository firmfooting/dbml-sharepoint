# Future work

Design material kept for reference rather than shipped. Nothing in this
folder is built, deployed, or validated; it documents decisions made
while designing the family and proposals held for when a trigger fires.

## Approval tracking

`approval-tracking.md` is the design proposal that produced the
retrospective endorsement-route record shipped on `Decision`
(`Decision.EndorsementRoute`) and the finished `Agree` involvement role.
It argues against building a live per-item approval tracker, names the
trigger count for deferring that decision properly, and reserves the
`{prefix}SignOff` list name for the day the trigger fires. Read it
before anyone proposes a live approvals board: the staleness argument
in its second section is the reason the family records routes
retrospectively.
