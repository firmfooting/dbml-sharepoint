---
title: Templates
sidebar_position: 3
---

# Template reference

Every generated script is rendered from these Jinja2 templates. Each template opens with a contract comment stating what it does and what it expects, reproduced here verbatim (extracted, not transcribed). Underscore-prefixed templates are shared partials or phase bodies included by the entry-point scripts.

## Entry-point scripts

### `assess-manifest.md.j2`

Companion manifest for assess.js.txt: how to run the read-only assessment, what each tier probes (always-run enumerations, pack-driven attempt-probes, the printed not-assessable honesty block), and how to read the COMPATIBLE / DEGRADED / BLOCKED verdict.

### `assess.js.j2`

dbml-sharepoint SITE ASSESSMENT script (READ-ONLY).

Probes the site's capabilities against this pack's requirements and prints a COMPATIBLE / DEGRADED / BLOCKED verdict. Makes NO changes: every call is a GET except the contextinfo digest fetch and one read-only CSOM ProcessQuery.

### `demo.js.j2`

dbml-sharepoint DEMO DATA script (built with --seed).

Paste AFTER deploy.js.txt has finished with errors: []. Creates the declared demo/sample rows. Every Title starts with '[DEMO] ' (visible in every view and form), and each row's text identifies it as demonstration data to delete before active use. Re-pasting is safe: rows that already exist (matched by Title) are skipped, never duplicated. rollback.js.txt confirms every list before delete; the Title prefix is a visible notice, not deletion authority.

### `deploy.js.j2`

dbml-sharepoint deployment script.

Paste into the SharePoint browser console and press Enter. Wait for the [SP-DEPLOY] [DONE] log line.

### `manifest.md.j2`

The operator-facing deploy manifest: supported mode, step-by-step run instructions, validation findings (must be zero errors), and the full deployment inventory - list creation order, deferred lookups, indexes, views, formatting, permissions - with phase numbers taken from the phases manifest.

### `rollback.js.j2`

dbml-sharepoint ROLLBACK script.

DELETES every list declared by this schema at this site. Refuses EVERY list unless the user types DELETE NON-EMPTY for that list and any items present. Deletion-blocked lists (AllowDeletion = false) are unlocked per list after confirmation and re-locked if their delete fails.

## Shared partials

### `_assess_body.js.j2`

Included by: `assess.js.j2`, `deploy.js.j2`

The whole assessment, taking its collaborators as an argument so the standalone script and the deploy can share it without a second copy.

### `_digest_cached.js.j2`

Included by: `assess.js.j2`, `demo.js.j2`, `deploy.js.j2`, `rollback.js.j2`

Shared cached request digest. Expects apiUrl, fetchWithRetry and spError to be defined. The digest is valid for FormDigestTimeoutSeconds (~30 min); callers fetch per use for lifetime safety and the cache refreshes 60s before expiry, the same safety as per-call contextinfo POSTs at ~one POST per run.

### `_http.js.j2`

Included by: `assess.js.j2`, `demo.js.j2`, `deploy.js.j2`, `rollback.js.j2`

Shared SharePoint HTTP transport + request diagnostics. Expects `log` to be defined. Every script's REST traffic rides fetchWithRetry: SharePoint Online throttles bursts (HTTP 429) and sheds load (503), and a teardown or demo seed deserves the same Retry-After handling as a deployment. READ-SAFE by construction. Write helpers live in _http_write.js.j2 so the read-only assess script never carries them.

### `_http_write.js.j2`

Included by: `demo.js.j2`, `deploy.js.j2`, `rollback.js.j2`

Shared SP WRITE-request headers. Included only by scripts that make writes (deploy, rollback, demo). The read-only assess script includes the transport partial alone, keeping its no-write property auditable from its text.

### `_provenance.js.j2`

Included by: `assess.js.j2`, `demo.js.j2`, `deploy.js.j2`, `rollback.js.j2`

Shared provenance header fields, rendered INSIDE each script's leading block comment. Expects: source_dbml, site_url, release, generated_at; optional: source_mtime, site_role. comment_safe  guards every raw interpolation against a crafted `*/`.

### `_site_guard.js.j2`

Included by: `assess.js.j2`, `demo.js.j2`, `deploy.js.j2`, `rollback.js.j2`

Shared web-context resolution for every pasteable script. Expects a `log` function and SITE_URL const to be defined already; emits the site-match guard, WEB, apiUrl, odataName, and the operator-identity line.

## deploy.js phase bodies

### `deploy/_acls.js.j2`

*Phase 4.2 (PROTECTION): role inheritance and assignments*

Phase body: break role inheritance and reconcile declared role assignments per list. 'configured' mode asserts the declared grants; 'exact' additionally removes undeclared direct grants (an allowlist). Principals resolve by name: site groups and the web's associated Owner/Member/Visitor groups; levels by role-definition name.

### `deploy/_assess_gate.js.j2`

*Phase 1.1 (PREPARE): site assessment*

Runs the site assessment and refuses a verdict the operator has not accepted.

### `deploy/_field_defaults.js.j2`

*Phase 2.4 (STRUCTURE): field defaults*

Defaults are included in create-field bodies, but existing columns are skipped in Phase 2.1. Re-applying the declared value makes upgrades idempotent and lets a provisioned constant replace after-create flows.

### `deploy/_field_reconcile.js.j2`

Included by: `deploy.js.j2`

Shared field machinery for the structure phases: immutable-shape verification (type kind, lookup target, formula) before an existing field is adopted, and narrow MERGE reconciliation of mutable settings (title, description, required, choices, defaults) with readback verification. Fail closed: shape mismatch aborts the field, never mutates it.

### `deploy/_forms.js.j2`

*Phase 3.2 (PRESENTATION): form formatting*

Declared list-form layouts (header/body/footer JSON) live on the list's default item content type as ClientFormCustomFormatter, a JSON string whose *JSONFormatter keys hold part OBJECTS (the pane-native encoding; the Format pane displays string-encoded parts escaped). Lists without a declaration are never touched.

### `deploy/_helpers.js.j2`

Included by: `deploy.js.j2`

Bounded per-lane parallelism. SharePoint stores fields and views in the list schema, and concurrent schema writes to the SAME list race into save conflicts, but different lists are fully independent. So the unit of parallelism is the list: items are grouped into lanes by key, items within a lane run strictly sequentially, lanes run concurrently up to `limit`. Workers keep their own per-item try/catch, so error attribution and summary.errors are unchanged.

### `deploy/_indexes.js.j2`

*Phase 2.3 (STRUCTURE): indexed columns*

Phase body: assert Indexed=true on every declared indexed column, verified by readback. SharePoint builds the index asynchronously; the flag is the deployer's contract.

### `deploy/_lists.js.j2`

*Phase 2.1 (STRUCTURE): list creation*

Phase body: create or adopt lists in dependency order with their non-lookup columns and every same-site lookup whose target already exists. Wave 1 runs sequentially to capture lookup-target GUIDs; wave 2 runs in per-list lanes. Existing lists/fields are adopted only when their immutable shape provably matches (fail closed).

### `deploy/_lookups.js.j2`

*Phase 2.2 (STRUCTURE): deferred lookups*

Phase body: add the deferred lookup columns (self-references and members of reference cycles) now that every target list exists.

### `deploy/_maintenance_unseal.js.j2`

*Phase 1.6 (PREPARE): maintenance unseal*

Sealed columns reject UI schema edits even for site admins; the ONLY legitimate maintenance path is this script. Unseal declared fields so the run's write phases work unchanged; Phase 4.1 re-seals and verifies after every field write is done.

### `deploy/_operator_enrolment.js.j2`

*Phase 1.4 (PREPARE): operator self-enrolment*

Some mappings route all list administration through an empty-by-default admin group (Owners hold only Contribute on the lists). Later phases (field reconciliation, indexes, ACL work) then need the operator to hold that group's grants, so the script enrols the operator for the duration of the run and removes them at the end. An operator who was ALREADY a member is left untouched. Only principals who can already manage the group (its Site-Owners owner) can benefit; this adds no new authority.

### `deploy/_preflight.js.j2`

*Phase 1.2 (PREPARE): read-only preflight*

A matching display name is not proof that an existing list or field was created from this schema. Validate every immutable identity before Phase 1.3 performs its first write. Mutable declared settings are reconciled and read back in Phase 2.1, but a wrong template/type/internal-name/lookup target always requires an explicit migration.

### `deploy/_reader_enrolment.js.j2`

*Phase 1.5 (PREPARE): enterprise reader enrolment*

Phase body: enrol the ONE account named by `build --enterprise-reader` into the mapping's `enroll_enterprise_reader` group, which holds Read. Emitted only when that flag was given, so an ordinary build carries no enrolment code at all. Unlike the operator's run-scoped enrolment, this membership is PERMANENT once the run reaches the end. If a later phase aborts, deploy.js.j2's finally removes the account this phase just enrolled -- a rollback of this run's own write, not a general reconciler for membership some earlier run may have left behind. Every resolution is refused unless it is a single user (PrincipalType strictly 1), does not match one of the three tenant-wide-claim needles at step 3, and matches the address the build asked for; the group must hold nobody but that account already (step 7); and the membership is then read back before the run is allowed to call it done. Those needles are NOT full coverage of the tenant-wide claims: they cover two of the four Learn names. Read the dated KNOWN LIMIT at step 3 before treating this as a closed door -- it records which two, why the other two are deliberately not guessed, and which of the guards here the residual risk actually rests on.

### `deploy/_seal.js.j2`

*Phase 4.1 (PROTECTION): seal declared columns*

Re-seal after every field write (1/2/3/3b/3d): sealed columns block UI schema edits and deletion even for site admins, the strongest defense when team owners are unavoidably site collection admins. Friction, not enforcement: an admin can unseal via API, which is deliberate work, not an accident.

### `deploy/_security_principals.js.j2`

*Phase 1.3 (PREPARE): permission levels and site groups*

Phase body: create/reconcile custom permission levels (base-permission bitmasks) and site groups (settings reconciled; owner corrected via a CSOM ProcessQuery where the REST surface cannot).

### `deploy/_seeds.js.j2`

*Phase 5.1 (DATA): seed items*

Phase body: extension-provided seed rows for singleton lists. Idempotent: existing rows are matched and verified value-by-value (exactSeedValueEqual), missing rows created, drift reported.

### `deploy/_shape_probes.js.j2`

Included by: `deploy.js.j2`

Shared read-only shape probes: readListShape / readFieldShape with per-list caching and invalidateFieldShapes(listName?) so concurrent lanes never thrash each other's caches. Absence answers (404 and the documented absent-field 400) return null rather than throwing.

### `deploy/_views.js.j2`

*Phase 3.1 (PRESENTATION): views*

Fields created through the REST field collection join no view, so a fresh list shows a Title-only default view. Every list gets a generated, unfiltered All Items recovery view containing its complete rendered schema; when an authored default exists the recovery view is hidden from the modern view bar. Authored views are managed alongside it. Other views are user content and are never touched (unlike exact-mode ACLs).

