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

### `columns.js.j2`

dbml-sharepoint COLUMNS script for one list.

Target site: List: (resolved by URL; its title is read back at run time, because a renamed list keeps its original slug) Deployer:     v Generated at:

Lists the custom columns, asks for one by internal name, and deletes that column after four guards: built-in and hidden fields never appear on the menu; every item is read to see whether the column holds a value, and the values found are printed so they can be re-keyed into a replacement column; an empty column needs its internal name typed again after that scan, and one that holds values, or whose values could not be read, needs DELETE NON-EMPTY typed; a sealed column is unsealed and read back before the delete, and the column is read back after it and must answer 404. A readback that disagrees stops the run. The table is printed again after each delete, and a blank answer finishes.

Deleting a column removes its values from every item, and neither the column nor the values go to the recycle bin (Microsoft Learn, SharePoint data deletion). The item scan is what keeps that from being a surprise.

Paste the whole file into the browser console on the site above, from a classic page such as .../_layouts/15/settings.aspx.

### `demo.js.j2`

dbml-sharepoint DEMO DATA script (built with --seed).

Paste AFTER deploy.js.txt has finished with errors: []. Creates the declared demo/sample rows. Every Title starts with '[DEMO] ' (visible in every view and form), and each row's text identifies it as demonstration data to delete before active use. Re-pasting is safe: rows that already exist (matched by Title) are skipped, never duplicated. rollback.js.txt confirms every list before delete; the Title prefix is a visible notice, not deletion authority.

### `deploy.js.j2`

dbml-sharepoint deployment script.

Paste into the SharePoint browser console and press Enter. Wait for the [SP-DEPLOY] [DONE] log line.

### `extract.js.j2`

dbml-sharepoint SCHEMA EXTRACTION script (READ-ONLY).

Target site: Deployer:     v Generated at: Lists: (resolved by URL; each title is read back at run time, because a renamed list keeps its original slug)

Reads each list's field definitions, content types and views, and offers the result as a JSON download. Makes NO changes: every request is a GET, and this script carries no write helpers at all.

Then, on the machine you generated this from, in the folder you saved the download into:

dbml-sharepoint extract

That creates a folder named after the download and writes a DRAFT schema.dbml, mapping.yaml and release.yaml into it, plus an EXTRACTION-NOTES.md listing everything the read could not recover. Pass --out to write somewhere else.

### `manifest.md.j2`

The operator-facing deploy manifest: supported mode, step-by-step run instructions, validation findings (must be zero errors), and the full deployment inventory - list creation order, deferred lookups, indexes, views, formatting, permissions - with phase numbers taken from the phases manifest.

### `protection.js.j2`

dbml-sharepoint PROTECTION script for one list.

Target site: List: (resolved by URL; its title is read back at run time, because a renamed list keeps its original slug) Deployer:     v Generated at:

Reads the list's deletion lock and the Sealed flag on each custom column, prints them, then takes one word at a time until you leave the prompt blank: lock or unlock sets AllowDeletion; seal or unseal sets Sealed on every custom column not already in that state. Each write is read back, and a readback that disagrees stops the run with the list as it stands.

A column the deployer provisioned is sealed on purpose: a sealed column rejects schema edits in the UI and silently discards REST writes. Unseal for the edit you are about to make, and seal again afterwards.

Paste the whole file into the browser console on the site above, from a classic page such as .../_layouts/15/settings.aspx.

### `rollback.js.j2`

dbml-sharepoint ROLLBACK script.

DELETES every list declared by this schema at this site. Refuses EVERY list unless the user types DELETE NON-EMPTY for that list and any items present. Deletion-blocked lists (AllowDeletion = false) are unlocked per list after confirmation and re-locked if their delete fails.

### `verify.js.j2`

dbml-sharepoint CLOCK VERIFICATION script (WRITES TO ONE SCRATCH LIST).

Exercises every clock cell this pack uses (a `today` or `now` rule, a `today` view window, a `[today]` default) on a hidden scratch list named ``, and prints a VERIFIED / MISMATCH / NOT-VERIFIED verdict. It creates that list if absent, reuses it when its Description carries the tool's marker, and never touches any other list. Paste after deploy.js.txt, on the same site.

## Shared partials

### `_assess_body.js.j2`

Included by: `assess.js.j2`, `deploy.js.j2`

The host names the pack data differently: assess.js.j2 passes `targets`, deploy.js.j2 `assess_targets_data`. One name here, so a probe that branches on the pack cannot render in one host and fail in the other.

### `_digest_cached.js.j2`

Included by: `assess.js.j2`, `columns.js.j2`, `demo.js.j2`, `deploy.js.j2`, `protection.js.j2`, `rollback.js.j2`, `verify.js.j2`

Shared cached request digest. Expects apiUrl, fetchWithRetry and spError to be defined. The digest is valid for FormDigestTimeoutSeconds (~30 min); callers fetch per use for lifetime safety and the cache refreshes 60s before expiry, the same safety as per-call contextinfo POSTs at ~one POST per run.

### `_formula_canonical.js.j2`

Included by: `deploy/_field_reconcile.js.j2`, `verify.js.j2`

Shared formula canonicalisation: how a stored Formula or ValidationFormula is compared with what was written. Expects nothing; defines xmlDecode and canonicalFormula. Included by deploy/_field_reconcile.js.j2 and by the verify script, so both read a formula back the same way.

### `_get_list_by_path.js.j2`

Included by: `_maintain_list.js.j2`, `extract.js.j2`

Resolve one list by its server-relative URL rather than by its title. Expects `apiUrl` and `odataName`, both emitted by `_site_guard.js.j2`. WHY NOT getbytitle. A list renamed in place keeps the slug it was created with, which is this project's own documented behaviour and the point of `renamed_from`. So on any site that has been through a rename, the segment the address bar shows is NOT the list's title, and every script that resolves by that segment 404s on its first read. Seen live 2026-09-03 (issue #385): lists answering at /Lists/ProgramRisk/ titled GOV_Risk. `web/GetList` takes the server-relative URL instead, which is the string the operator actually copied. Microsoft Learn, "Working with lists and list items with REST", documents the alias-parameter form used here. The deploy, rollback, verify and assess scripts keep getbytitle and are right to: the mapping DECLARES those titles and the deploy renames lists to match. Only the operator-pasted scripts infer a name from a URL.

### `_guid.js.j2`

Included by: `_maintain_list.js.j2`, `extract.js.j2`

A GUID SharePoint returned, checked before it is spliced into a URL. Every id here comes back from the API and is then interpolated into a path like `web/lists(guid'<id>')`, so the shape is asserted rather than trusted: an id that is not a GUID means the read did not return what was asked for, and the failure should say so at the read rather than as a malformed URL two calls later. `deploy/_helpers.js.j2` carries the same function for the deploy bundle. The two are deliberately not shared yet: folding them together edits the emitted deploy and moves `test/fixtures/expected/simple-deploy.js`, which is a golden review of its own and does not belong in a maintenance fix.

### `_http.js.j2`

Included by: `assess.js.j2`, `columns.js.j2`, `demo.js.j2`, `deploy.js.j2`, `extract.js.j2`, `protection.js.j2`, `rollback.js.j2`, `verify.js.j2`

Shared SharePoint HTTP transport + request diagnostics. Expects `log` to be defined. Every script's REST traffic rides fetchWithRetry: SharePoint Online throttles bursts (HTTP 429) and sheds load (503), and a teardown or demo seed deserves the same Retry-After handling as a deployment. READ-SAFE by construction. Write helpers live in _http_write.js.j2 so the read-only assess script never carries them. THROTTLING ANSWERS THESE SCRIPTS THE BROWSER WAY, NOT THE API WAY. Microsoft Learn, "Avoid getting throttled or blocked in SharePoint Online": "For requests that a user performs directly in the browser, SharePoint Online redirects you to the throttling information page, and the requests fail. For requests that an application makes ... SharePoint Online returns HTTP status code 429 ... or 503". These scripts are pasted into a console and carry the operator's own cookies, so they get the redirect, not the status code.

### `_http_batch.js.j2`

Included by: `demo.js.j2`, `deploy.js.j2`, `rollback.js.j2`

Shared OData $batch transport: BatchWriter for ChangeSet writes and BatchReader for top-level query parts. Included only by scripts that make writes (deploy, rollback, demo); the read-only assess script includes the transport partial alone, keeping its no-write property auditable from its text. Expects `spHeaders` from _http_write.js.j2, so a ChangeSet part carries exactly the headers a single write does, plus `isThrottled`, `spError` and `dbg` from _http.js.j2. A part's verb goes in its request line rather than in an X-HTTP-Method header, so a caller passes the method and headers of the single write it replaces and the part still comes out in the documented shape. getDigest, fetchWithRetry, apiUrl and log arrive as CONSTRUCTOR ARGUMENTS rather than off the enclosing scope, so this stays a transport primitive with nothing to reimplement. MEASURED on a live tenant by test/manual/throttle-batch-probe.js (#404), recorded 2026-09-04: 20, 100, 200, 500 and 750-operation batches all landed clean, and a 1000-operation batch came back HTTP 200 with 637 parts at 201 and 363 at 500. A clean 750 beside a partial 1000 says the ceiling is body SIZE and not operation count, which is why this budgets bytes. The probe's control read the item count back and confirmed the ChangeSet parts were accepted, so the encoding below is the proven spelling rather than a plausible one, digest on both the outer request and every part included. The PART ENCODING was measured separately, recorded 2026-09-04, after a live governance deploy landed every POST part and refused every MERGE part with HTTP 400. Nine candidate spellings were sent one per $batch against a scratch list and each verdict read back off the object rather than off the part status. Two things decide acceptance, and the earlier reading of that 400 had them the wrong way round: 1. The VERB MUST BE IN THE REQUEST LINE. X-HTTP-Method does not tunnel inside a part. SharePoint reads the part as the verb it was given, so a tunnelled MERGE arrives as a POST to the entity and its body keys are read as method arguments: "The parameter Description does not exist in method GetById". `POST` + X-HTTP-Method: MERGE was refused under both nometadata and verbose parts. 2. THE BODY ANNOTATION MUST MATCH THE PART'S CONTENT TYPE. `__metadata` is the verbose transport annotation, so a part declaring odata=nometadata is refused with "The property '__metadata' does not exist on type 'SP.FieldText'". `MERGE <url>` with verbose part headers and a __metadata body was accepted (HTTP 204, read back applied), as was a bodyless function POST under verbose part headers. odata=verbose is therefore NOT what a part is refused for; the earlier finding to that effect was drawn from a shape that also carried the tunnelled header, which is what SharePoint was actually refusing. Parts carry spHeaders for that reason.

### `_http_write.js.j2`

Included by: `columns.js.j2`, `demo.js.j2`, `deploy.js.j2`, `protection.js.j2`, `rollback.js.j2`, `verify.js.j2`

Shared SP WRITE-request headers. Included only by scripts that make writes (deploy, rollback, demo). The read-only assess script includes the transport partial alone, keeping its no-write property auditable from its text.

### `_maintain_list.js.j2`

Included by: `columns.js.j2`, `protection.js.j2`

Shared list resolution for the two maintenance scripts (protection.js, columns.js). Expects log, LIST_PATH, LIST_SLUG, summary, apiUrl, odataName, fetchWithRetry, spError, spHeaders and getDigest to be defined. Emits the ManageLists preflight, the by-URL list read that names what does exist on a miss, the guid-addressed list and field paths, the custom column filter, and the MERGE helpers every write goes through. RESOLVED BY URL, NOT BY TITLE; `_get_list_by_path.js.j2` carries the reason. LIST_TITLE is read back from the list here, so every message below names what the list is called now rather than what its folder is called.

### `_provenance.js.j2`

Included by: `assess.js.j2`, `demo.js.j2`, `deploy.js.j2`, `rollback.js.j2`, `verify.js.j2`

Shared provenance header fields, rendered INSIDE each script's leading block comment. Expects: source_dbml, site_url, release, generated_at; optional: source_mtime, site_role. comment_safe  guards every raw interpolation against a crafted `*/`.

### `_site_guard.js.j2`

Included by: `assess.js.j2`, `columns.js.j2`, `demo.js.j2`, `deploy.js.j2`, `extract.js.j2`, `protection.js.j2`, `rollback.js.j2`, `verify.js.j2`

Shared web-context resolution for every pasteable script. Expects a `log` function and SITE_URL const to be defined already; emits the site-match guard, WEB, apiUrl, odataName, and the operator-identity line.

### `_verify_body.js.j2`

Included by: `verify.js.j2`

The whole verification, taking its collaborators as an argument so the standalone script and a test harness can share it. Expects `targets` (generators/verifygen.py: list_title, marker, columns, rows, checks, rule) and the transport, digest and canonicalFormula collaborators.

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

Phase body: create or reconcile owned lists in dependency order with their non-lookup columns and every same-site lookup whose target already exists. Wave 1 runs sequentially to capture lookup-target GUIDs; wave 2 runs in per-list lanes. Existing lists are reconciled only when exact provenance and immutable shape both match (fail closed).

### `deploy/_lookups.js.j2`

*Phase 2.2 (STRUCTURE): deferred lookups*

Phase body: add the deferred lookup columns (self-references and members of reference cycles) now that every target list exists.

### `deploy/_maintenance_unseal.js.j2`

*Phase 1.7 (PREPARE): maintenance unseal*

Sealed columns reject UI schema edits even for site admins; the ONLY legitimate maintenance path is this script. Unseal declared fields so the run's write phases work unchanged; Phase 4.1 re-seals and verifies after every field write is done.

### `deploy/_operator_enrolment.js.j2`

*Phase 1.5 (PREPARE): operator self-enrolment*

Some mappings route all list administration through an empty-by-default admin group (Owners hold only Contribute on the lists). Later phases (field reconciliation, indexes, ACL work) then need the operator to hold that group's grants, so the script enrols the operator for the duration of the run and removes them at the end. An operator who was ALREADY a member is left untouched. Only principals who can already manage the group (its Site-Owners owner) can benefit; this adds no new authority.

### `deploy/_preflight.js.j2`

*Phase 1.2 (PREPARE): read-only preflight*

A matching display name is not proof that an existing list or field was created from this schema. Before Phase 1.3 performs its first write, every existing list must carry this declaration's exact provenance marker and every immutable shape must agree. Mutable settings are reconciled only after both checks pass.

### `deploy/_reader_enrolment.js.j2`

*Phase 1.6 (PREPARE): enterprise reader enrolment*

Phase body: enrol the ONE account named by `build --enterprise-reader` into the mapping's `enroll_enterprise_reader` group, which holds Read. Emitted only when that flag was given, so an ordinary build carries no enrolment code at all. Unlike the operator's run-scoped enrolment, this membership is PERMANENT once the run reaches the end. If a later phase aborts, deploy.js.j2's finally removes the account this phase just enrolled -- a rollback of this run's own write, not a general reconciler for membership some earlier run may have left behind. Every resolution is refused unless it is a single user (PrincipalType strictly 1), does not match one of the three tenant-wide-claim needles at step 3, and matches the address the build asked for; the group must hold nobody but that account already (step 7); and the membership is then read back before the run is allowed to call it done. Those needles are NOT full coverage of the tenant-wide claims: they cover two of the four Learn names. Read the dated KNOWN LIMIT at step 3 before treating this as a closed door -- it records which two, why the other two are deliberately not guessed, and which of the guards here the residual risk actually rests on.

### `deploy/_renames.js.j2`

*Phase 1.3 (PREPARE): list renames*

Phase body: retitle every list the preflight found under a previous title carrying that title's own marker. Each rename is re-checked at write time, written by list id, and read back; a readback that disagrees aborts. Nothing is created here.

### `deploy/_seal.js.j2`

*Phase 4.1 (PROTECTION): seal declared columns*

Re-seal after every field write (1/2/3/3b/3d): sealed columns block UI schema edits and deletion even for site admins, the strongest defense when team owners are unavoidably site collection admins. Friction, not enforcement: an admin can unseal via API, which is deliberate work, not an accident.

### `deploy/_security_principals.js.j2`

*Phase 1.4 (PREPARE): permission levels and site groups*

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

