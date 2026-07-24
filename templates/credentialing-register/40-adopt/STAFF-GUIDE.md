# Credentialing register — guide

## For everyone (read access)

The register answers one operational question: **what is this person
credentialed to do here?** Open the practitioner, read their
`ScopeSummary`. If an activity isn't within the recorded scope, the answer
is no until the credentialing process says otherwise — the register is the
record of decisions, not a place to negotiate them.

If your own row is wrong or out of date, tell a Credentialing Coordinator —
don't wait for the review cycle.

## For credentialing coordinators

### Entering a decision

Rows follow decisions, never precede them. When the credentialing
committee (or delegate) decides:

1. Update the practitioner's **ScopeSummary** to the approved wording —
   including conditions and exclusions verbatim; paraphrased conditions are
   how scope creep starts.
2. Set **ScopeApprovedDate** and the next **ScopeReviewDate** per the cycle
   in governance; reference the committee meeting in Notes.

### Maintaining credentials

One `CR_Credential` row per credential, with the **sighted evidence
linked** (`EvidenceUrl` into your records system). No evidence link, no
Current status — "they showed me" is not a register entry.

### The two sweeps (monthly, 20 minutes)

1. **Registrations expiring** (90 days): notify practitioner + manager;
   on renewal, sight the new registration, update expiry, link evidence.
2. **Expiring credentials** (90 days): same rhythm. Anything past expiry →
   Status **Expired** immediately, and escalate per governance — an
   expired registration is a stop-work conversation, not a reminder email.

### New starters and leavers

New credentialed starter: full row + credentials before first clinical
day (pairs with the onboarding-tracker template — make it a task there).
Leaver: Status **Ceased**; the history stays.
