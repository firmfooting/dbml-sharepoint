# Contract register

A single source of truth for every contract the organisation holds: who it's
with, what it's worth, who owns it, when it starts, ends, and must be
renewed or exited. Deploys as one list: `CT_Contract`.

**The value case.** Most organisations discover contract sprawl the
expensive way — an auto-renewal nobody wanted, an expiry nobody watched, a
supplier nobody remembers engaging. A register turns that into five views
that **deploy with the list**: *Live contracts*, *Expiring 90 days*,
*Auto-renewals*, *By counterparty* and *Exited*. `TermMonths` is calculated
automatically from the start and end dates, and an auto-renewing contract
cannot be saved without a notice period — the one number that prevents a
renewal nobody chose. Build with `--seed` and five demo rows show every
view and every colour working before you type a thing.

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Trim/rename columns and choice values to your vocabulary |
| 2 | `20-configure/` | Set your prefix if `CT_` collides; review the security model |
| 3 | `30-deploy/` | Administrator: build, paste, verify |
| 4 | `40-adopt/` | Circulate the staff guide to contract managers |
| 5 | `50-govern/` | Agree owners, review cadence and data-quality rules |

**Customisation points:** `ContractType` and `Status` choices; value
thresholds and approval delegations are policy, not schema — see
`50-govern/governance.md`.
