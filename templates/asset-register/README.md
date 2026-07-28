# Asset register

Who has what, where it is, and what state it's in. Two lists: `AS_Location`
(a small reference list of places) and `AS_Asset` (the register itself, with
a lookup to Location, a unique asset tag, assignment and lifecycle status).

**The value case.** Untracked equipment is money that walks: laptops that
leave with leavers, licences on machines nobody can find, warranty claims
missed because nobody knows the purchase date. A register answers the four
audit questions — what do we own, where is it, who holds it, what's it
worth — from one filtered list instead of a spreadsheet safari.

**What deploys with it:** six views across the two lists — *Stocktake*
(the Asset default, sorted in the order you walk the building), *By
holder*, *By location*, *Warranty expiring*, *Retired and disposed*, and
the Location catalogue — warranty dates that turn red once lapsed and stay
quiet once an item is disposed, a form that drops the holder field when an
item leaves service, save rules that refuse a future purchase date and a
warranty with no purchase date to measure it from, and four demo locations
with six demo assets behind `--seed`.

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Adjust categories/statuses; drop columns you won't keep current |
| 2 | `20-configure/` | Prefix, security review |
| 3 | `30-deploy/` | Administrator: build, paste, verify; seed Locations first |
| 4 | `40-adopt/` | Staff guide for whoever issues and receives equipment |
| 5 | `50-govern/` | Stocktake cadence, disposal rules, ownership |

**Customisation points:** `Category` and `Status` enums — note that every
`Status` member is named inside a deployed view filter, so read the
"Before you build" block in `30-deploy/DEPLOY.md` before renaming one; and
whether ordinary Members may edit (default here: yes — assets are
maintained by many hands; tighten to a custodians group if that's not your
culture).
