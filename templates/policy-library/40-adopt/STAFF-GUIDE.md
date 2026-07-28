# Policy library — staff guide

## Finding the current policy (everyone)

Open **PL_PolicyRegister**, find the policy, follow its **Document URL**.
That link always points at the current published version. If you've been
emailed a policy document, treat it as a photocopy — the register is the
truth.

You should only ever see **published** versions in the library — so if you
can see it, it's in force. That relies on one library setting an
administrator applies at deploy (*Draft Item Security*, in
`30-deploy/DEPLOY.md`); if you ever open a document numbered 0.1 or 2.3,
it is a draft that is **not** in force, and the setting has been missed.
Tell the policy owner.

## Authoring (PL Policy Authors)

### Drafting a new policy

1. Add the policy to the **register** first — Status **Draft**, an Owner,
   and a placeholder ReviewDate. Unregistered documents don't exist.
2. Upload the draft to **PL_PolicyDocuments**. It becomes version **0.1**.
   Iterate; each save is 0.2, 0.3 … Ordinary staff do not see it *provided
   Draft Item Security is set to "Only users who can edit"* — confirm that
   once for the library rather than assuming it.
3. Set the document's PolicyArea and DocStatus as it moves Draft →
   In review → Approved.

### Publishing

1. When approved (record the approval body in the register's Notes):
   library → the file → **Publish** → it becomes **1.0** and appears for
   all staff.
2. Update the register row: Status **Published**, **ApprovedDate**,
   **ReviewDate** (next review), and the **Document URL**.

### Revising

Edit the published file → SharePoint starts a new draft (2.1 lineage under
the hood: 1.1, 1.2 → publish → 2.0). Readers keep seeing 1.0 until you
publish. On publish, update ApprovedDate/ReviewDate in the register. Mark
the old approach in Notes if the change is material.

## What NOT to do

- Don't email policy attachments — send the register link.
- Don't publish without updating the register row; an unregistered
  publication is a process failure.
- Don't delete superseded documents — version history *is* the audit trail.
