# Credentialing register — guide

## For everyone (read access)

The register answers one operational question: **what is this person
credentialed to do here?** Open **CR_Practitioner** — it lands on *By
discipline*, grouped and collapsed — find the person, and read the
**Scope of practice** section of their row. If an activity isn't within
the recorded scope, the answer is no until the credentialing process says
otherwise — the register is the record of decisions, not a place to
negotiate them.

If your own row is wrong or out of date, tell a Credentialing Coordinator —
don't wait for the review cycle.

## For credentialing coordinators

### Entering a decision

Rows follow decisions, never precede them. When the credentialing
committee (or delegate) decides:

1. Update the practitioner's **Scope Summary** to the approved wording —
   including conditions and exclusions verbatim; paraphrased conditions are
   how scope creep starts. The form header says exactly this, every time
   the form opens, because it is the one thing that has to survive
   transcription.
2. Set **Scope Approved Date** and the next **Scope Review Date** per the
   cycle in governance; reference the committee meeting in Notes. The form
   refuses an approval date in the future, and refuses to save a
   **Current** practitioner with no approval date at all — if the scope
   has not been decided yet, the status is **Under review**.

### Maintaining credentials

One `CR_Credential` row per credential, with the **sighted evidence
linked** (`EvidenceUrl` into your records system). No evidence link, no
Current status — "they showed me" is not a register entry.

Nothing refuses that save; it cannot (see the governance doc for why). The
control is the *Missing evidence* view instead: every Current credential
with no link, all in one place. Working it to empty is the same act as
enforcing it, done weekly rather than per-save.

### The two sweeps (monthly, 20 minutes)

1. **Registrations expiring** (90 days): notify practitioner + manager;
   on renewal, sight the new registration, update expiry, link evidence.
2. **Expiring credentials** (90 days): same rhythm. Anything past expiry →
   Status **Expired** immediately, and escalate per governance — an
   expired registration is a stop-work conversation, not a reminder email.
   An Expired credential's whole row washes red in the practitioner's own
   credentialing file (*By practitioner*), which is the one place the
   register guarantees someone will look.
3. **Scope reviews due** (60 days): the committee's list. Ceased
   practitioners are excluded; Lapsed and Under review are not, because
   those are the people a review is most needed for.

### New starters and leavers

New credentialed starter: full row + credentials before first clinical
day (pairs with the onboarding-tracker template — make it a task there).
Leaver: Status **Ceased**; the history stays.
