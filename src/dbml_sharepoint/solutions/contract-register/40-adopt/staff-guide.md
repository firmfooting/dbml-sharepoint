# Contract register: staff guide

*For contract managers. Everyone else can look, not touch.*

## What this is

One list (**Contracts**) holding every contract we're party to: who it's
with, what it's worth, when it ends, and who owns it. If a contract isn't in
the register, the organisation effectively doesn't know it has it.

## The five views

The list opens on **Live contracts**: everything not yet exited, soonest
expiry first. Four other views are already built for you:

| View | What it shows |
| --- | --- |
| **Live contracts** | The default. Every contract still running. |
| **Expiring 90 days** | Anything ending inside the next ninety days. This is a *rolling* ninety days, not "this quarter". |
| **Auto-renewals** | Every contract that renews itself. Check the notice period against the end date. |
| **By counterparty** | The same live contracts, grouped and collapsed by who they're with. Click a name to open it. |
| **Exited** | Finished contracts, most recently ended first. |

You don't need to build any of these, and you shouldn't rename them: a
redeploy puts the declared name back.

## Adding a contract (2 minutes)

1. Open the **CT_Contract** list → **New**.
2. **The contract**: **Title** is the name people actually use ("Office
   cleaning: Sparkle Ltd"), plus **Counterparty**, **Contract Ref** if you
   use one, **Contract Type** and a two-sentence **Summary**.
3. **Term and value**: **Start / End dates** (the term length calculates
   itself), then **Renewal type**. That one matters most: choose
   **Auto-renews** and the form will not let you save without **Notice
   period days**, because that number is the only thing that prevents a
   surprise renewal. Choose *Fixed term — no renewal* and the notice field
   disappears entirely. There is nothing to give notice of.
4. **Ownership**: **Owner** (the accountable person, not necessarily you),
   **Status**, and **Document URL**: a link to the signed contract where it
   actually lives. The register points at documents; it doesn't store them.
5. **System** holds **Term (months)**, which the register works out for
   itself. It is empty on the New form and fills in once you save.

## Keeping it honest

- When a contract enters renewal talks → set Status **In renewal**. It
  turns amber: someone is holding a decision.
- When it ends → **Exited** (don't delete; history is the point). The end
  date stops showing red the moment you do. That colour is for live
  contracts only.
- Changed dates on renewal? Update Start/End. The term recalculates.
- The **Term (months)** column can't be edited. It's derived. If it looks
  wrong, the dates are wrong.
- The register will refuse a negative **Notice period days** or a negative
  **Annual value**, and it will tell you which one and why.

## What NOT to do

- Don't paste contract text into Summary: two sentences and a link.
- Don't record drafts you're merely negotiating unless Status = **Draft**.
- Don't delete rows. Exited contracts stay; every change is versioned.
