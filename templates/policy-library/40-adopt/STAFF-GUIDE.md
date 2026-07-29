# Policy library — staff guide

## Finding the current policy (everyone)

Open **PL_PolicyRegister** — it opens on **By area**, grouped and collapsed
by policy domain, so expand yours and the policies in force are the rows
underneath. Follow the policy's **Document URL**. That link always points
at the current published version. If you've been emailed a policy document,
treat it as a photocopy — the register is the truth.

Superseded and withdrawn policies are filtered out of that view on purpose.
If you need one — to read an approval made under the old policy, say — the
**Retired** view has them, most recently approved first.

You should only ever see **published** versions in the library — so if you
can see it, it's in force. That relies on one library setting an
administrator applies at deploy (*Draft Item Security*, in
`30-deploy/DEPLOY.md`); if you ever open a document numbered 0.1 or 2.3,
it is a draft that is **not** in force, and the setting has been missed.
Tell the policy owner.

## Authoring (PL Policy Authors)

### Drafting a new policy

1. Add the policy to the **register** first — Status **Draft**, an Owner,
   and a placeholder ReviewDate. Unregistered documents don't exist. The
   form knows this: at Draft, **Approved date** and **Document URL** are
   not on it at all, because there is nothing yet to approve or link.
2. Upload the draft to **PL_PolicyDocuments**. It becomes version **0.1**.
   Iterate; each save is 0.2, 0.3 … Ordinary staff do not see it *provided
   Draft Item Security is set to "Only users who can edit"* — confirm that
   once for the library rather than assuming it.
3. Set the document's PolicyArea and DocStatus as it moves Draft →
   In review → Approved.

### Publishing

1. When approved (record the approval body in the register's Notes), set
   the register row to **Approved** and fill **Approved date** — the form
   reveals it, and the list refuses to save without it, because the review
   interval is measured from it. An Approved row renders **amber**, not
   green: the decision is made and staff still cannot read the policy.
2. Library → the file → **Publish** → it becomes **1.0** and appears for
   all staff.
3. Update the register row: Status **Published**, **ReviewDate** (next
   review), and the **Document URL**, which the form reveals at that
   status. Nothing checks the link — it is a hyperlink column and no save
   rule can read one — so a published row with an empty Document URL saves
   quite happily and helps nobody.

**Work the *In development* view.** It holds every Draft, In review and
Approved policy, and the amber Approved ones at the top are the ones with
an action outstanding: approved, unpublished, invisible to staff.

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
