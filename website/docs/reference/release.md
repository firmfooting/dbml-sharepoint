---
title: release.yaml
sidebar_position: 4
---

# release.yaml

The smallest input, and the one that makes runs auditable.

```yaml
release: "2026.07-r3"
date: "2026-07-27"
schema_version: "1.4.0"
notes: |
  Optional free text. Anything an operator or auditor should read
  alongside the bundle.
```

| Key | Required | Meaning |
| --- | --- | --- |
| `release` | yes | The release tag. Bump for any regenerated bundle you hand to an operator |
| `date` | yes | The release date, as a string |
| `schema_version` | yes | Bump when the DBML changes shape |
| `flow_package_version` | no | Defaults to `"none"`; for organisations pairing the lists with a Power Automate package |
| `notes` | no | Defaults to `""` |
| `deployer_version` | no | Ignored. The build warns with `release_deployer_version_ignored`; remove the key |

The key set is closed. A missing required key and an unrecognised key are
both load errors naming the file, including a near-miss like
`schema_verison:`, which would otherwise stamp the bundle with the wrong
schema version and report nothing. Every `release.yaml` under `src/dbml_sharepoint/solutions/`
and `examples/` is a working example of the shape.

Every value is text, so quote it. YAML reads an unquoted `2.10` as the
number 2.1, which would stamp a different version than the one written, so
an unquoted number is a load error. An unquoted date is the one exception:
it is read back as ISO text. The file is read as YAML 1.2, as
[the mapping](./mapping.md#how-the-file-is-read) is, so an unquoted `010` is
the number 10 and a load error, and an unquoted `yes` is the text "yes".
An unquoted `1e3`, which YAML 1.1 read as text, is now the number 1000.0,
so it is a load error too.

A key written with no value reads as absent. A blank `notes:` or
`flow_package_version:` takes its default, and a blank required key is a
load error, the same as a missing one.

`release` is the key, not `release_tag`. `release_tag` is the name the
loaded object carries in Python, and the two are deliberately allowed to
differ so the file reads as a release description rather than as a struct.

## Where the values go

`release` and `schema_version` are stamped into every
generated artifact's provenance header: deploy.js.txt, rollback.js.txt, assess.js.txt,
demo-data.js.txt, both manifests, and the reporting outputs. deploy.js.txt also
carries `release` and `schema_version` into its run summary, so a pasted
console transcript records exactly which release produced the site's
current shape. `date` additionally appears in the reporting bundle's
provenance table.

The deployer those headers, the deploy manifest and the deployment log record is
not read from this file. It is the name and version of the installed
dbml-sharepoint package, read from its metadata when the bundle is built.
`deployer_version` used to be written here by hand and had drifted from the
version that actually built the bundle, so it is now ignored.

## What the release tag does *not* do

Nothing is written to the target site, so nothing about the tag changes
what a deploy does. The tag is provenance in the artifacts and in the
console transcript, and that is its whole job.

In particular, re-running deploy.js.txt with a **new** release tag does not
re-verify anything a re-run of the **same** tag would have skipped. Every
skip decision is made by reading the live site and comparing it against the
declaration in front of it. The tag is never part of that comparison, and
there is no stored copy of a previous run to compare against. Two bundles
with different tags and identical declarations behave identically.

Bump the tag anyway. It is what lets someone reading a console transcript,
a manifest and a reporting dictionary six months later prove they are
looking at the same bundle.
