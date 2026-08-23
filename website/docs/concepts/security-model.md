---
title: Security model
sidebar_position: 4
---

# Security model

This page is for a tenant or security reviewer deciding whether
browser-console deployment is acceptable. It describes identity, credentials
and network reach. The separate [safety model](safety-model.md) describes how
the deployer limits operational damage once a run is authorised.

## Identity and credentials

Generated scripts do not ask for, read or store passwords, access tokens,
client secrets or certificates. They create no app registration and request
no consent grant. The browser still sends its existing SharePoint session
cookies on the same-origin requests, as it does for the SharePoint page itself.

The script runs inside an already signed-in SharePoint page. It reads
`_spPageContextInfo` to identify the current web and operator, and makes
same-origin requests using that browser session. SharePoint authenticates the
current user and authorises each operation at the web, list, folder or item
level; the script does not gain a second identity or a route around those
checks. Microsoft describes that role-based authorisation model in
[Authentication, authorization, and security in SharePoint](https://learn.microsoft.com/sharepoint/dev/general-development/authentication-authorization-and-security-in-sharepoint#authentication-and-authorization).

For writes, the script obtains a short-lived form digest from
`/_api/contextinfo` and sends it as `X-RequestDigest`. A digest is not a
credential or an elevation mechanism: SharePoint requires it on non-OAuth
write requests in addition to the signed-in session. See Microsoft's
[SharePoint REST write guidance](https://learn.microsoft.com/sharepoint/dev/sp-add-ins/complete-basic-operations-using-sharepoint-rest-endpoints#writing-data-by-using-the-rest-interface).

## Network surface

Every request URL is built by one shared helper. From
`src/dbml_sharepoint/templates/_site_guard.js.j2`, with the abort branch
elided:

```js
const expectedOrigin = new URL(SITE_URL).origin;
const expectedPath = new URL(SITE_URL).pathname.replace(/\/$/, '');
const actualOrigin = window.location.origin;
const actualPath = (_spPageContextInfo.webServerRelativeUrl || '').replace(/\/$/, '');
if (actualOrigin !== expectedOrigin || actualPath !== expectedPath) {
  /* logs a site mismatch and aborts before any request */
}
const WEB = actualPath;  // '' for the tenant root, '/sites/foo' for a site collection, etc.
const apiUrl = (suffix) => `${WEB}/_api/${suffix}`;
```

Note the order: the origin and web path are compared with the build's declared
target, and a mismatch aborts, *before* `WEB` is bound or any request is made.
`WEB` is then a server-relative path, so every `apiUrl()` call is a relative
URL the browser can only send to the origin of the SharePoint page already
open.

The current templates use these endpoint families:

| Endpoint family | Purpose |
| --- | --- |
| `/_api/contextinfo` | Obtain a request digest and SharePoint build metadata |
| `/_api/web` and `/_api/web/...` | Read and reconcile lists, fields, content types, views, items, indexes, permissions, role definitions, groups, current user, regional settings, list templates and web properties |
| `/_api/site` and `/_api/site/...` | Read lock, usage, hub and sensitivity-label information during assessment |
| `/_api/search/query` | Read-only assessment of search availability |
| `/_api/SP.CompliancePolicy.SPPolicyStoreProxy.GetAvailableTagsForSite(...)` | Read-only assessment of retention labels offered to the current site |
| `/_api/SP_TenantSettings_Current` | Read-only assessment of the tenant app-catalog setting |
| `/_api/ProcessQuery` | Read-only capability probe, and CSOM group-owner assignment where the REST surface cannot express that write |

A reviewer grepping the generated scripts for `http://` or `https://` will
find exactly two classes of hit, neither of them a request:

- `http://schemas.microsoft.com/sharepoint/clientquery/2009` in the CSOM
  request body (an XML namespace, not a network destination).
- documentation links in comments, such as the retention-policy reference in
  `rollback.js.txt`. They are never fetched; nothing reads a comment.

Every hit that is not one of those two is worth stopping on.

There are no calls to Microsoft Graph, PnP services, package registries,
telemetry or analytics endpoints. There are no third-party hosts and no
dynamic script imports, `eval`, remote modules or code downloads. This
inventory was derived from `src/dbml_sharepoint/templates/` on 2026-07-30
and re-derived, independently, on 2026-08-11 (same seven families, no
drift); `test/test_template_lint.py`'s endpoint-inventory tests pin this
going forward. The source of truth remains the generated script being
reviewed for a particular release.

## Why this is different from an unsolicited console paste

The execution mechanism is the same browser capability that phishing
guidance warns about; provenance and review are what change the risk:

- You generate the script locally from source you can inspect and inputs you
  authored.
- The generated header names the source schema, target site, release and
  generation time.
- `deploy-manifest.md` lists the intended objects and writes before execution.
- `assess.js.txt` runs first. Its business probes are read-only; its only POSTs
  obtain a digest or execute a read-only CSOM query.
- `deploy.js.txt` is deterministic output, with no runtime code download or
  telemetry path that can substitute different logic after review.

Do not paste a script received through email, chat or an unreviewed download.
Generate it from the approved repository revision and compare the generated
provenance with the manifest under review.

## Undocumented surfaces

The project does not claim that every SharePoint operation is documented.
For example, view-width reconciliation uses guarded `SetViewXml` behaviour.
The [safety model's undocumented-surfaces policy](safety-model.md#undocumented-surfaces)
explains the live verification and read-splice-diff-write-readback guard
required before such a surface is used.

## What rollback is allowed to do

`rollback.js.txt` is the most destructive artifact the build emits, so its
authority is worth stating rather than summarising. It targets only the lists
this schema declares at this site, and reaching a delete requires the operator
to type the site's leaf path at a first prompt. Within that scope it will:

- **Recycle list items**, never permanently delete them: every row it removes
  is restorable from the site recycle bin.
- **Delete a list** only after the operator types `DELETE NON-EMPTY` at a
  second prompt that is re-asked for every provenance-confirmed target. The
  phrase authorises that list and any items present; an earlier zero count,
  Title value or demo prefix creates no exception.
- **Clear a list's deletion block.** When a target list has
  `AllowDeletion = false`, rollback MERGEs it to `true`, verifies the change
  took effect, deletes the list, and re-locks it if the delete fails. A
  protection the site owner set is therefore overridden, per list, once
  deletion is authorised.
- **Delete lists by title.** A pre-existing list whose title collides with a
  prefixed deploy list is indistinguishable to rollback and would be deleted.
  The script logs this warning before the first prompt; confirm target lists
  are deploy-owned before confirming.

The list itself is removed with a REST `DELETE`, not `recycle()`. Treat list
recoverability as a tenant recycle-bin question rather than something this
project asserts.

## Reviewer checklist

1. Review the repository revision and build inputs; generate the artifacts on
   a controlled machine.
2. Confirm the target and release in every generated header match
   `deploy-manifest.md`.
3. Read the manifest's validation findings, object inventory, permissions and
   rollback scope. Require zero validation errors.
4. Search the generated JavaScript for `fetch(`, `http://`, `https://`,
   `eval`, `import(` and `script`. Confirm requests stay under the target
   web's `/_api/` path; distinguish the CSOM XML namespace from a URL call.
5. Run only `assess.js.txt` first and retain its console transcript. Resolve
   `BLOCKED` and review every `DEGRADED` finding before authorising deploy.
6. Review the [fail-closed behaviours](safety-model.md#fail-closed-everywhere)
   and confirm existing objects with incompatible shapes abort before writes.
7. Review [what rollback is allowed to do](#what-rollback-is-allowed-to-do)
   against your own tolerance. Confirm it is restricted to the lists this
   schema declares, that it recycles items rather than permanently deleting
   them, and decide explicitly whether overriding a list's
   `AllowDeletion = false` protection is acceptable in your tenant.

## Governance may still say no

Some organisations prohibit all console-pasted scripts, including
locally-generated and fully reviewed ones. That is a legitimate governance
decision. This page exists to make the decision informed; it does not turn a
prohibited execution model into an approved one.
