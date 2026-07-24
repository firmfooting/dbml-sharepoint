---
title: release.yaml
sidebar_position: 4
---

# release.yaml

The smallest input, and the one that makes runs auditable.

```yaml
release_tag: "2026.07-r3"
schema_version: "1.4.0"
```

Both values are stamped into every generated artifact's provenance
header — deploy.js, rollback.js, assess.js, demo-data.js, both
manifests, and the reporting outputs. deploy.js also carries them into
its run summary, so a pasted console transcript records exactly which
release produced the site's current shape.

Bump `schema_version` when the DBML changes shape; bump `release_tag`
for any regenerated bundle you hand to an operator. Reruns of the same
release skip verified work; a new release re-verifies everything.
