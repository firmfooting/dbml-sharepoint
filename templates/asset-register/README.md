# Asset register

Who has what, where it is, and what state it's in. Two lists: `AS_Location`
(a small reference list of places) and `AS_Asset` (the register itself, with
a lookup to Location, a unique asset tag, assignment and lifecycle status).

**The value case.** Untracked equipment is money that walks: laptops that
leave with leavers, licences on machines nobody can find, warranty claims
missed because nobody knows the purchase date. A register answers the four
audit questions — what do we own, where is it, who holds it, what's it
worth — from one filtered list instead of a spreadsheet safari.

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Adjust categories/statuses; drop columns you won't keep current |
| 2 | `20-configure/` | Prefix, security review |
| 3 | `30-deploy/` | Administrator: build, paste, verify; seed Locations first |
| 4 | `40-adopt/` | Staff guide for whoever issues and receives equipment |
| 5 | `50-govern/` | Stocktake cadence, disposal rules, ownership |

**Customisation points:** `Category` and `Status` enums; whether ordinary
Members may edit (default here: yes — assets are maintained by many hands;
tighten to a custodians group if that's not your culture).
