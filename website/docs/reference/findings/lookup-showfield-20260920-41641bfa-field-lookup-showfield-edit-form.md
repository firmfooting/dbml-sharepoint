---
title: "field.lookup.showfield-edit-form"
surface: field
scope: lookup
question: showfield-edit-form
probe_surface: field
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# field.lookup.showfield-edit-form

- Probe surface: field
- Run: lookup-showfield/20260920-41641bfa
- Question: EYES-ON: what does the edit form show for the lookup after the mutation?

## machine

- Outcome: `MANUAL`
- Evidence: open \<sharepoint-url> Probe ShowFieldSource/EditForm.aspx?ID=1 and read the 'ProbeShowField' field. "dbmlsp-probe-target-title-one" means the form still shows the target's Title; "dbmlsp-probe-alternate-one" means it shows AlternateLabel. Anything else, including a blank cell, a numeric id or an error, is its own answer and is recorded verbatim.

[All findings](../live-findings)
