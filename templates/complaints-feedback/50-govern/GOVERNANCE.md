# Complaints & feedback — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Process owner | *(e.g. quality/consumer-experience manager)* | SLAs, trend reporting, privacy, this document |
| Handlers | CF Feedback Handlers | Acknowledgement, investigation, response, learning |
| Recorders | CF Feedback Recorders | Faithful capture at the point of receipt |

## Sector note — healthcare (and other regulated sectors)

Check your statutory complaints scheme before adopting this register as
the system of record: some sectors mandate a platform or prescribe
categories and timeframes (health-complaints commissioners, aged-care
schemes). Where mandated, use this register only for what the mandate
does not cover, and record referrals as the escalation section describes.
No patient-identifiable clinical detail enters this list — complaint
substance at process level, clinical content in clinical systems. See
[templates/HEALTHCARE.md](../../HEALTHCARE.md).

## Severity definitions & response SLAs (put statutory timeframes here)

| Severity | Meaning | Acknowledge within | Close within |
|---|---|---|---|
| Critical | Alleged serious harm, systemic failure, media/regulator interest | 1 business day | per your scheme |
| Serious | Significant individual impact or repeated issue | 2 business days | 20 business days |
| Standard | Everything else | 5 business days | 30 business days |

The calculated day-counts make SLA performance sortable facts; the monthly
report view is the process owner's evidence base.

## Escalation

- Critical items: process owner notified same day; executive briefed.
- Anything alleging staff misconduct leaves this register for the HR
  process — record "Referred externally" with a pointer, not the detail.
- Complainants who remain dissatisfied: record the referral to your
  external body (ombudsman/commissioner) in the row.

## Privacy (load-bearing)

1. Site membership = recorders + handlers + owners only; **ordinary
   members have no access by design** — widening it is a governance
   decision recorded here.
2. Detail carries the substance, initials/roles for third parties, and no
   health/financial identifiers beyond what the item needs.
3. Subject-access: complainants may request their records; the process
   owner handles with your privacy officer.
4. Retention per your scheme's rules; this register is usually the system
   of record — treat exports accordingly.

## The learning loop (the actual point)

- **Monthly**: process owner reviews closures — outcomes, day-counts vs
  SLA, and every `Learning` field; recurring themes become change requests
  or risk entries (pair naturally with the change-register and
  risk-register templates).
- **Quarterly**: trend report to the executive: volumes, SLAs, themes,
  changes made. Feedback nobody learns from is administration, not quality.

## Lifecycle

Never run `rollback.js` against real rows; export before decommission,
then dispose per retention rules.
