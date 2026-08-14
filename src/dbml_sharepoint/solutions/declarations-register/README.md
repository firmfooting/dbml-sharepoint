# Declarations register

The two compliance registers almost every organisation is asked to produce:
**conflicts of interest** (`DR_Interest`) and **gifts, benefits &
hospitality** (`DR_GiftBenefit`). Two deliberately standalone lists — no
links between them — deployed together because they share one culture:
declare early, record faithfully, review on a cadence.

**The value case.** Both registers are cheap to run and ruinously expensive
to lack: the moment a conflict or a gift becomes a story, the first
question is "was it declared?" and the second is "show me the register".
Staff declare in two minutes (submit-only — declarations are evidential);
a compliance coordinator manages assessment and review; the annual
attestation becomes a filter, not a project.

**Nine views deploy with the lists**, including *My interests*, which shows
each person their own declarations and nobody else's — that is the annual
attestation, done. The assessment fields are off the New form entirely, so
"the declarer never assesses their own declaration" is structural rather
than cultural. Build with `--seed` and ten demo rows show every colour,
every view and a deliberately repeated offeror before anyone declares
anything real.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Fit interest types and gift categories to your code of conduct |
| 2 | `20-configure/` | Prefix; the declare-only staff model |
| 3 | `30-deploy/` | Administrator: build, paste, verify the two registers |
| 4 | `40-adopt/` | The declare-early guide for all staff |
| 5 | `50-govern/` | Thresholds, assessment, management plans, publication posture |

**Customisation points:** the gift value thresholds and the COI management
actions are policy — set them in `50-govern/governance.md` and keep the
enums aligned with your code of conduct.
