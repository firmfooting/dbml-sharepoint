---
title: "EDTNEG"
---

<!-- markdownlint-disable MD013 -->

# EDTNEG (machine)

- Package: threshold-index-guard
- Question: Filter editor rows for THREE NEGATED clauses
- Outcome: `MANUAL (unobserved)`
- Evidence: \[6000 item(s)] OPEN \<sharepoint-url> Probe Threshold/Threshold EDTNEG.aspx, then Settings > Edit current view, and report ONE of: the NUMBER of filter rows the editor shows, or "refused" (it would not open the filter at all). 3 clause(s) here render 6 \<FieldRef>, which is 6 editor row(s) by the count \_views.py uses. The filter is \<Where>\<And>\<And>\<Or>\<IsNull>\<FieldRef Name="Bucket"/>\</IsNull>\<Neq>\<FieldRef Name="Bucket"/>\<Value Type="Text">A\</Value>\</Neq>\</Or>\<Or>\<IsNull>\<FieldRef Name="Bucket"/>\</IsNull>\<Neq>\<FieldRef Name="Bucket"/>\<Value Type="Text">B\</Value>\</Neq>\</Or>\</And>\<Or>\<IsNull>\<FieldRef Name="Bucket"/>\</IsNull>\<Neq>\<FieldRef Name="Bucket"/>\<Value Type="Text">C\</Value>\</Neq>\</Or>\</And>\</Where>

[All findings](../live-findings)
