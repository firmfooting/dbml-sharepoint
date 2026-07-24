# Risk register

A working organisational risk register with a **self-rating 5×5 matrix**:
pick Likelihood and Consequence, and SharePoint calculates the rating
(Low/Medium/High/Extreme) and a 1–25 score — a rating inconsistent with the
matrix becomes impossible to enter. One list: `RR_Risk`.

**The value case.** Most risk registers die in spreadsheets: one owner, one
laptop, ratings hand-typed and quietly inconsistent. This one is shared,
versioned, filterable (*Extreme/High first*, *reviews overdue*), and the
matrix is enforced by formula, not by hoping. It fits any function —
strategic, operational, financial, compliance, safety — which is what makes
it a whole-of-business quick win.

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Fit categories to your risk taxonomy |
| 2 | `20-configure/` | Prefix; **the matrix lives here** — edit with care |
| 3 | `30-deploy/` | Administrator: build, paste, verify the matrix calculates |
| 4 | `40-adopt/` | Risk owners' guide: describing and rating risks well |
| 5 | `50-govern/` | Review cadences by rating, escalation, matrix change control |

**Customisation points:** `Category` enum; the matrix cells in
`mapping.yaml` (read the change-control warning in `50-govern/GOVERNANCE.md`
first — changing the formula re-rates every existing row).
