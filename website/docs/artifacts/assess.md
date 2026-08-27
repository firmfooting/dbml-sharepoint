---
title: assess.js.txt
sidebar_position: 3
---

# assess.js.txt

A **read-only** site assessment, emitted with every build alongside
`assess-manifest.md`. Paste it in the target site's console *before* a
first deploy to learn whether this pack fits this site.

## Read-only guarantee

Every call is a GET except the `contextinfo` digest fetch and one
read-only CSOM `ProcessQuery`. The guarantee is structural, not just
promised: the shared HTTP *write* helpers are packaged in a separate
template partial that assess.js.txt does not include, so the absence of
write machinery is auditable from the script text itself.

## Three tiers

1. **Always-run enumerations**: site identity and template, lock state,
   platform build, effective permission bits (ManageLists,
   ManagePermissions, NoScript), creatable list templates, regional and
   language settings, group connection, storage, hub status, retention
   labels, app catalog and SPFx footprint, search.
2. **Pack-driven attempt-probes**: per-declared-list collision probes;
   property-surface probes (sealing, `AllowDeletion`, column and form
   formatter surfaces) against an existing declared list where one
   exists; intelligent-versioning trim mode; CSOM availability when the
   pack declares groups; sensitivity label and Preservation Hold Library
   signals.
3. **Not assessable**: a printed honesty block listing what cannot be
   determined from the operator's site context (tenant policies,
   licence-gated behaviour), so absence of a finding is never mistaken
   for a pass.

## The verdict

Findings roll up per requirement key to a single line:

- `COMPATIBLE`: no blocking or degrading findings.
- `DEGRADED`: `deploy.js.txt` refuses this site until the operator
  reviews each `WARN` finding and sets `ACKNOWLEDGE_DEGRADED = true` near
  the top of the script. A requirement reported `NOT-ASSESSABLE` degrades
  the verdict too, because nobody could check it. This includes a
  list whose [provenance marker](reporting.md#the-provenance-marker) could not
  be read, named in the finding. A Description that was read and does not carry
  the exact marker blocks deploy: the list may be foreign, and ordinary deploy
  will not stamp it. An unreadable Description degrades instead, because the
  assessment cannot honestly decide whether the marker is present; deploy's
  fresh preflight read makes that decision.
- `BLOCKED`: a named requirement fails (for example, missing permission
  bits or a locked site); resolve before deploying.

`assess-manifest.md` documents what will be probed and how to read the
result, so the verdict can be shared with a site owner who never sees
the console.
