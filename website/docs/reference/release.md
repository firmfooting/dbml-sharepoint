---
title: release.yaml
sidebar_position: 4
---

# release.yaml

The smallest input, and the one that makes runs auditable.

```yaml
release: "2026.07-r3"
date: "2026-07-27"
deployer_version: "dbml-sharepoint/0.1.0"
schema_version: "1.4.0"
notes: |
  Optional free text. Anything an operator or auditor should read
  alongside the bundle.
```

| Key | Required | Meaning |
|---|---|---|
| `release` | yes | The release tag. Bump for any regenerated bundle you hand to an operator |
| `date` | yes | The release date, as a string |
| `deployer_version` | yes | The tool version this bundle was cut with — a pin you record, not one the tool reads back |
| `schema_version` | yes | Bump when the DBML changes shape |
| `flow_package_version` | no | Defaults to `"none"`; for organisations pairing the lists with a Power Automate package |
| `notes` | no | Defaults to `""` |

The key set is closed. A missing required key and an unrecognised key are
both load errors naming the file — including a near-miss like
`schema_verison:`, which would otherwise stamp the bundle with the wrong
schema version and report nothing. Every `release.yaml` under `src/dbml_sharepoint/solutions/`
and `examples/` is a working example of the shape.

`release` is the key, not `release_tag` — `release_tag` is the name the
loaded object carries in Python, and the two are deliberately allowed to
differ so the file reads as a release description rather than as a struct.

## Where the values go

`release`, `schema_version` and `deployer_version` are stamped into every
generated artifact's provenance header — deploy.js.txt, rollback.js.txt, assess.js.txt,
demo-data.js.txt, both manifests, and the reporting outputs. deploy.js.txt also
carries `release` and `schema_version` into its run summary, so a pasted
console transcript records exactly which release produced the site's
current shape. `date` and `deployer_version` additionally appear in the
reporting bundle's provenance table.

## What the release tag does *not* do

Nothing is written to the target site, so nothing about the tag changes
what a deploy does. The tag is provenance in the artifacts and in the
console transcript, and that is its whole job.

In particular, re-running deploy.js.txt with a **new** release tag does not
re-verify anything a re-run of the **same** tag would have skipped. Every
skip decision is made by reading the live site and comparing it against the
declaration in front of it — the tag is never part of that comparison, and
there is no stored copy of a previous run to compare against. Two bundles
with different tags and identical declarations behave identically.

Bump the tag anyway. It is what lets someone reading a console transcript,
a manifest and a reporting dictionary six months later prove they are
looking at the same bundle.
