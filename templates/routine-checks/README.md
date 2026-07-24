# Routine checks

*Theme: operations & service — and the purest digitisation win in the
library (crossover with process digitisation & improvement)*

The wall-taped paper checklists, digitised: vaccine-fridge temperatures,
cleaning rounds, emergency-trolley checks, environmental audits. Two lists:
`RC_CheckPoint` (the catalogue of things checked, with frequency and
acceptable range) and `RC_CheckEntry` (every check performed, with the
reading and an in-range/out-of-range result).

**The value case.** Paper check sheets have three famous failure modes:
they get filled in retrospectively at audit time, out-of-range readings get
written down without anyone acting, and the sheet for last March is in a
skip. Digitised, every entry is timestamped and attributed, out-of-range
results demand an action note, and the history is complete forever. For a
health service, the vaccine fridge alone justifies the deploy — cold-chain
breach evidence is a compliance requirement with real dollar consequences.

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Fit check types and result language to your rounds |
| 2 | `20-configure/` | Prefix; everyone-records model |
| 3 | `30-deploy/` | Administrator: build, paste; load the checkpoint catalogue |
| 4 | `40-adopt/` | The check habit — including what to do when it's out of range |
| 5 | `50-govern/` | Missed-check monitoring, escalation, the retrospective-entry rule |

**Customisation points:** `CheckType` and frequency vocabulary; the
out-of-range escalation per checkpoint type lives in governance.
