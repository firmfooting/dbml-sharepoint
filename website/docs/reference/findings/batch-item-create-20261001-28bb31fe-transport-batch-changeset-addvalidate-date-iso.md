---
title: "transport.batch.changeset-addvalidate-date-iso"
surface: transport
scope: batch
question: changeset-addvalidate-date-iso
probe_surface: transport
state: open
lanes: machine
---

<!-- markdownlint-disable MD013 -->

# transport.batch.changeset-addvalidate-date-iso

- Probe surface: transport
- Run: batch-item-create/20261001-28bb31fe
- Question: what an AddValidateUpdateItemUsingPath part writing ProbeWhen as ISO 8601 text in formValues answered

## machine

- Outcome: `NOT ESTABLISHED`
- Evidence: a field was refused: HTTP 200 OK; fields Title HasException=false ErrorMessage=null FieldValue="dbmlsp addvalidate iso date"; ProbeWhen HasException=true ErrorMessage="You must specify a valid date within the range of 1/1/1900 and 12/31/8900." FieldValue="2026-01-15T09:30:00Z"; Id HasException=false ErrorMessage=null FieldValue="0"; landed no

[All findings](../live-findings)
