---
title: "view.filter-editor.plain-clause-rows"
surface: view
scope: filter-editor
question: plain-clause-rows
probe_surface: scale
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# view.filter-editor.plain-clause-rows

- Probe surface: scale
- Run: threshold-index/20260827-272-guard
- Question: Filter editor rows for THREE PLAIN clauses (control)

## machine

- Recorded as: `EDTPLN`
- Outcome: `MANUAL (unobserved)`
- Evidence: \[6000 item(s)] OPEN \<sharepoint-url> Probe Threshold/Threshold EDTPLN.aspx, then Settings > Edit current view, and report ONE of: the NUMBER of filter rows the editor shows, or "refused" (it would not open the filter at all). 3 clause(s) here render 3 \<FieldRef>, which is 3 editor row(s) by the count \_views.py uses. The filter is \<Where>\<And>\<And>\<Eq>\<FieldRef Name="Bucket"/>\<Value Type="Text">A\</Value>\</Eq>\<Eq>\<FieldRef Name="Bucket"/>\<Value Type="Text">B\</Value>\</Eq>\</And>\<Eq>\<FieldRef Name="Bucket"/>\<Value Type="Text">C\</Value>\</Eq>\</And>\</Where>

[All findings](../live-findings)
