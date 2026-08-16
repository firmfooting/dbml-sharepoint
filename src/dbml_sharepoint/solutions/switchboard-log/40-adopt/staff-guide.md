# Switchboard log: operators' guide

*Three books, three habits. Everything is logged as it happens: the
switchboard record is only trusted because it is contemporaneous.*

## Emergency codes: log it live, complete it after

During a code your job is the code: announce, page, connect. The log
fits into the gaps, and the form is built for exactly that:

1. The moment the announcement is made (or immediately after):
   **SB_CodeEvent** -> New: code type, location, **Announced At = now**.
   Two fields and save. *All Clear At* and *Event Notes* are not on the
   New form, because you do not have them yet.
2. At stand-down: open the row, add **All Clear At** (duration calculates
   itself), who initiated if known, and **Event Notes**: what switchboard
   did (pages sent, services called, instructions received). Operational
   facts only; clinical details belong in clinical systems, never here.
3. **Drills are logged identically** with **Drill** ticked: the drill
   record is what proves the drill happened, and the **Drills** view is
   grouped by code type so the committee can see which codes have never
   been drilled.

**Until you add the all-clear, that column reads "Running" in red in every
view, and the row sits in the Still running view.** That is intentional:
it is either a live code, or a code you never closed off. Both need
somebody to look.

## Messages: read back, then relay-then-record

1. Taking the call, **SB_MessageLog** -> New: caller, callback number,
   who it's for (role first), the message. **Read it back to the caller**
   before saving; the read-back is the accuracy control.
2. Set **Urgency** honestly: *Emergency* interrupts whatever you're doing;
   *Urgent* is relayed within the hour; *Routine* waits for a sensible
   hour. An **Emergency** message that is still pending washes its whole
   row pink on the live board.
3. Relay it, then record it: set Status **Relayed** and the two relay
   fields appear: **Relayed To** (the person who actually answered) and
   **Relayed At**. **The list will not let you save Relayed without both**,
   which is the point: "left voicemail" is not relayed, and a message
   marked relayed with no name is a 2 a.m. call with no trail.
   Minutes-to-relay calculates itself and draws a bar coloured by urgency.
4. Couldn't reach them? The message stays **Pending relay** and you keep
   trying per the escalation in governance: **Pending relay** is the
   live board every operator watches, and the handover checks it.

It sorts oldest first rather than by urgency. SharePoint sorts a choice
column alphabetically, which would have put *Routine* above *Urgent*, so
urgency is carried by the colour instead: read the pill, and read the pink
rows first.

## Keys: no movement without a row

- Issuing, **SB_KeyMovement** -> New: the key, **who** (name AND
  role/company; sight ID for anyone you don't recognise), check the key's
  **Restrictions** first. Issued At = now, Status **Out**. *Returned At*
  is not on the New form.
- Returning: open the movement, set Status **Returned** and **Returned
  At** appears. The list refuses a Returned movement with no time.
- **Keys out now** at shift handover: every Out key is either expected to
  be out, or it's tonight's follow-up. **Out since before today** is the
  narrower chase list: anything issued before midnight and still out.
- **By key** groups every movement ever under its key. That is where you
  answer "when did this key last come back?", and it is what the quarterly
  audit reads.

## Shift handover (5 minutes)

Walk the incoming operator through: **Pending relay** (anything live, pink
rows first), **Keys out now**, **Still running** (any code without an
all-clear), and any code events this shift. The views are the handover
sheet, nothing verbal-only.
