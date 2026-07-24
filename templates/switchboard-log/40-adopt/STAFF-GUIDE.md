# Switchboard log — operators' guide

*Three books, three habits. Everything is logged as it happens — the
switchboard record is only trusted because it is contemporaneous.*

## Emergency codes: log it live, complete it after

During a code your job is the code — announce, page, connect. The log
fits into the gaps:

1. The moment the announcement is made (or immediately after):
   **SB_CodeEvent** → New — code type, location, **AnnouncedAt = now**.
   Two fields and save; the rest waits.
2. At stand-down: add **AllClearAt** (duration calculates itself), who
   initiated if known, and **EventNotes**: what switchboard did — pages
   sent, services called, instructions received. Operational facts only;
   clinical details belong in clinical systems, never here.
3. **Drills are logged identically** with IsDrill ticked — the drill
   record is what proves the drill happened.

## Messages: read back, then relay-then-record

1. Taking the call: **SB_MessageLog** → New — caller, callback number,
   who it's for (role first), the message. **Read it back to the caller**
   before saving; the read-back is the accuracy control.
2. Set **Urgency** honestly: *Emergency* interrupts whatever you're doing;
   *Urgent* is relayed within the hour; *Routine* waits for a sensible
   hour.
3. Relay it, then record it: **RelayedTo** (the person who actually
   answered — "left voicemail" is not relayed), **RelayedAt**. The
   minutes-to-relay calculates itself.
4. Couldn't reach them? The message stays **Pending relay** and you keep
   trying per the escalation in governance — the *Pending relay* view is
   the live board every operator watches, and the handover checks it.

## Keys: no movement without a row

- Issuing: **SB_KeyMovement** → New — the key, **who** (name AND
  role/company; sight ID for anyone you don't recognise), check the key's
  **Restrictions** first. IssuedAt = now, Status **Out**.
- Returning: open the movement, **ReturnedAt**, Status **Returned**.
- The *Keys out now* view at shift handover: every Out key is either
  expected to be out, or it's tonight's follow-up.

## Shift handover (5 minutes)

Walk the incoming operator through: *Pending relay* (anything live),
*Keys out now*, and any code events this shift. The views are the handover
sheet — nothing verbal-only.
