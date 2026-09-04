/**
 * MULTI-VALUE LOOKUP PROBE.
 *
 * Creates two owned lists and asks whether a multi-value lookup can be
 * provisioned at all, whether it can be indexed, whether the multiplicity can
 * be changed after the fact, and what an item write and read look like. None
 * of that is known today. #409 asks four questions and this probe is the
 * machine half of all four.
 *
 * Ids follow the grammar in `test/manual/SURFACES.md`,
 * `<surface>.<scope>.<question>`. `multilookup` was reserved as a scope under
 * the `field` surface when the grammar landed and nothing has filed under it
 * until now, so there are no mnemonics to carry across:
 *
 *   field.multilookup.fixture-lists-created
 *   field.multilookup.control-single-value-lookup-created
 *   field.multilookup.create-readback-type              (#409 question 1)
 *   field.multilookup.control-single-value-indexed
 *   field.multilookup.indexed-property                  (#409 question 2)
 *   field.multilookup.allow-multiple-values-mutability  (#409 question 3)
 *   field.multilookup.item-write-shape                  (#409 question 4)
 *   field.multilookup.item-read-shape                   (#409 question 4)
 *
 * Every question is about the multi-value lookup column type, so nothing files
 * under another surface. The two controls ask single-VALUE lookup questions,
 * and they exist only to make the multi-value answers readable, so they take
 * the `multilookup` scope of the questions they guard. That follows
 * `field.multichoice.control-single-value-indexed`, which is a single-value
 * Choice question filed under `multichoice` for the same reason.
 *
 * #409's remaining question, whether a multi-value lookup costs one join or
 * more against the ceiling of 12 in `analysis/joins.py`, is not here. It is
 * answered by counting what the deployer emits, not by asking a tenant.
 *
 * WHAT THIS PROBE MUST NOT ASSERT. SharePoint has no distinct multi-value
 * lookup entity type: the column is an `SP.FieldLookup` carrying
 * `AllowMultipleValues`. What it then reports as `TypeAsString` and
 * `FieldTypeKind` is the question, so no row here compares either against an
 * expected value. Each records what came back. Asserting the value the
 * question is asking for is the failure AGENTS.md names, and it would make
 * this probe kill itself the moment it started working.
 *
 * THE ONE VALUE THAT IS ASSERTED is `AllowMultipleValues` on read-back, and
 * only when deciding which create path won. A field that was accepted and is
 * not multi-value would answer the index and item questions about a
 * single-value column while the transcript said otherwise, which is worse
 * than no answer. So a candidate only wins if the flag reads back true, and
 * a field that fails that test is deleted before the next candidate runs.
 *
 * RELATED. `library-column-interactions-probe.js` registers
 * `library.column.multi-lookup-column-on-library`, which asks whether a
 * multi-value lookup works on a document LIBRARY, and supplies the
 * `createfieldasxml` spelling reused as a create candidate below. It has no
 * recorded run. Under the "two subjects, two methods, two ids" rule in
 * SURFACES.md a library and a list are different subjects, so neither row
 * settles the other.
 */
(async () => {
  // ---- Operator settings -------------------------------------------------
  const CONFIRMED = false;
  const ALLOW_WRITES = false;
  const PROBE_RETRY_TRANSIENT = true;
  const PROBE_RETRY_ATTEMPTS = 5;
  // CLEANUP governs both ends: it recycles a fixture left by a previous run
  // before this one starts, and recycles this run's fixture at the end. With
  // it off, a second run finds its own lists still standing and stops rather
  // than reporting "already present" as though it had measured something.
  const CLEANUP = false;
  const TARGET_LIST = 'zzz dbmlsp multilookup target';
  const PROBE_LIST = 'zzz dbmlsp multilookup probe';
  // ------------------------------------------------------------------------

  // The three columns on the probe list. All three point at the same target
  // list through the same display field, so a difference in behaviour between
  // them can only be the multiplicity.
  //
  //   SINGLE  the control. Created by the deployer's own AddField path, and
  //           the subject of the index control.
  //   FLIP    created single-valued and then widened, and narrowed again.
  //           Kept apart from SINGLE so the index control is never asked
  //           about a column this probe has mutated.
  //   MULTI   the column under test.
  const SINGLE = 'Party';
  const FLIP = 'PartyFlip';
  const MULTI = 'Parties';
  // Three rows so that "the two that were asked for" is distinguishable from
  // "every row in the target list". Only the first two are ever written.
  const TARGET_ROWS = ['Alpha', 'Bravo', 'Charlie'];

  // Shared result registry v1. Register findings before any network work.
  //
  // STATE carries the coarse answer alongside the prose, from the five-value
  // vocabulary in test/manual/SURFACES.md: settled, open, awaiting-capture,
  // void, needs-human. An explicit state passed to record() always wins; the
  // classifier is the default for the rows nobody has ruled on yet.
  // ABORTED is open: it means the fixture never built, so the question was
  // never asked and the run has nothing to settle it with.
  const OPEN_HEADS = ['NOT ESTABLISHED', 'SHORT', 'ABORTED'];
  const AWAITING_CAPTURE_HEADS = ['MANUAL', 'NOT REACHED'];
  const stateFor = (observed) => {
    if (AWAITING_CAPTURE_HEADS.some((p) => observed.startsWith(p))) return 'awaiting-capture';
    if (OPEN_HEADS.some((p) => observed.startsWith(p))) return 'open';
    return 'settled';
  };
  const results = [];
  const expect = (id, question) => {
    results.push({
      id,
      question,
      observed: 'NOT ESTABLISHED',
      detail: 'the run did not reach this question',
      state: 'open',
    });
  };
  const record = (id, question, observed, detail, state) => {
    const next = {
      question, observed, detail: detail || '', state: state || stateFor(observed),
    };
    const row = results.find((candidate) => candidate.id === id);
    if (row) {
      Object.assign(row, next);
    } else {
      results.push({ id, ...next });
    }
    log('INFO', `${id}: ${observed}${detail ? `: ${detail}` : ''}`);
  };
  expect('field.multilookup.fixture-lists-created', 'the fixture actually built: two lists, three target rows, the control columns');
  expect('field.multilookup.control-single-value-lookup-created', 'CONTROL: a plain single-value Lookup into the target is created by the deployer\'s own AddField path');
  expect('field.multilookup.create-readback-type', 'which create path takes AllowMultipleValues:true, and what the field reads back as');
  expect('field.multilookup.control-single-value-indexed', 'CONTROL: Indexed:true on the SINGLE-value Lookup, which this repository already provisions');
  expect('field.multilookup.indexed-property', 'Indexed:true on a multi-value Lookup: accepted? and what does it read back as?');
  expect('field.multilookup.allow-multiple-values-mutability', 'AllowMultipleValues on an EXISTING lookup: can it be turned on, and can it be turned off again?');
  expect('field.multilookup.item-write-shape', 'which item WRITE shapes SharePoint accepts for a multi-value lookup');
  expect('field.multilookup.item-read-shape', 'what a multi-value lookup value READS BACK as');

  // Shared probe core v2: context guard, bounded transport and REST helpers.
  const log = (level, msg) => console.log(`[SP-PROBE] [${level}] ${msg}`);
  if (typeof _spPageContextInfo === 'undefined') {
    log('ERROR', '_spPageContextInfo is not available on this page; cannot resolve the web context. Open /_layouts/15/settings.aspx and retry.');
    return { aborted: 'no-sp-page-context' };
  }
  const WEB = (_spPageContextInfo.webServerRelativeUrl || '').replace(/\/$/, '');
  if (!CONFIRMED) {
    log('INFO', `This page is ${window.location.origin}${WEB || '/'}.`);
    log('INFO', 'If that is the site you want, set CONFIRMED = true and paste again.');
    return { aborted: 'unconfirmed' };
  }
  const probeWrites = typeof PROBE_WRITES === 'undefined' ? true : PROBE_WRITES;
  if (probeWrites && !ALLOW_WRITES) {
    log('INFO', 'This probe writes only its declared fixture. Set ALLOW_WRITES = true to proceed.');
    return { aborted: 'writes-disabled' };
  }
  const apiUrl = (suffix) => `${WEB}/_api/${suffix}`;
  const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
  log('INFO', `probe revision 28d9c06c; core v2; results v1.`);
  log('INFO', `Running as ${_spPageContextInfo.userLoginName || '(unknown)'} on web '${WEB || '(root)'}'.`);

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const spError = (text) => {
    try {
      const parsed = JSON.parse(text);
      return parsed?.error?.message?.value
        || parsed?.odata?.error?.message?.value
        || String(text).slice(0, 300);
    } catch {
      return String(text).slice(0, 300);
    }
  };
  const isRefusal = (status) =>
    status >= 400 && status !== 401 && status !== 403
    && status !== 408 && status !== 429 && status !== 503;
  async function fetchWithRetry(url, options, attempts = PROBE_RETRY_ATTEMPTS) {
    for (let attempt = 0; ; attempt += 1) {
      const response = await fetch(url, options);
      const transient = response.status === 429 || response.status === 503;
      if (PROBE_RETRY_TRANSIENT && transient && attempt < attempts) {
        const retryAfter = Number(response.headers.get('Retry-After'))
          || Math.min(2 ** attempt, 30);
        log('INFO', `Throttled (HTTP ${response.status}); retry ${attempt + 1}/${attempts} in ${retryAfter}s.`);
        await sleep(retryAfter * 1000);
        continue;
      }
      return response;
    }
  }
  let cachedDigest = null;
  let digestExpiresAt = 0;
  async function getDigest() {
    if (cachedDigest && Date.now() < digestExpiresAt) return cachedDigest;
    const response = await fetchWithRetry(apiUrl('contextinfo'), {
      method: 'POST',
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    const text = await response.text();
    if (!response.ok) {
      throw new Error(`contextinfo failed HTTP ${response.status}: ${spError(text)}`);
    }
    const info = JSON.parse(text)?.d?.GetContextWebInformation;
    if (!info?.FormDigestValue) throw new Error('contextinfo omitted FormDigestValue');
    cachedDigest = info.FormDigestValue;
    digestExpiresAt = Date.now()
      + Math.max((Number(info.FormDigestTimeoutSeconds) || 1800) - 60, 60) * 1000;
    return cachedDigest;
  }
  const spHeaders = (digest, extra = {}) => ({
    'Accept': 'application/json;odata=verbose',
    'Content-Type': 'application/json;odata=verbose',
    'X-RequestDigest': digest,
    ...extra,
  });
  async function post(suffix, body, extraHeaders) {
    const digest = await getDigest();
    const response = await fetchWithRetry(apiUrl(suffix), {
      method: 'POST',
      headers: spHeaders(digest, extraHeaders || {}),
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        error: spError(text),
        d: null,
      };
    }
    let d = null;
    try {
      d = text ? JSON.parse(text).d : null;
    } catch {
      d = null;
    }
    return { ok: true, status: response.status, error: null, d };
  }
  async function get(suffix, accept) {
    const response = await fetchWithRetry(apiUrl(suffix), {
      method: 'GET',
      headers: { 'Accept': accept || 'application/json;odata=verbose' },
    });
    const text = await response.text();
    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        error: spError(text),
        d: null,
      };
    }
    const parsed = JSON.parse(text);
    return {
      ok: true,
      status: response.status,
      error: null,
      d: parsed.d !== undefined ? parsed.d : parsed,
    };
  }
  const merge = (suffix, body) => post(
    suffix,
    body,
    { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' },
  );
  async function entityTypeFor(listTitle) {
    const response = await get(
      `web/lists/getbytitle('${odataName(listTitle)}')?$select=ListItemEntityTypeFullName`,
    );
    if (!response.ok) {
      throw new Error(`could not resolve the item entity type: ${response.error}`);
    }
    return response.d.ListItemEntityTypeFullName;
  }
  // Shared list fixture v1: exact ownership checks and bounded recycle.
  // Title is never treated as ownership. Callers supply a stable description.
  async function inspectOwnedList(title, ownershipDescription) {
    const listPath = `web/lists/getbytitle('${odataName(title)}')`;
    const existing = await get(`${listPath}?$select=Id,Description`);
    if (!existing.ok) {
      if (existing.status === 404) return { state: 'missing', listPath, d: null };
      return {
        state: 'error', listPath, d: null,
        error: `HTTP ${existing.status}: ${existing.error}`,
      };
    }
    if (existing.d.Description !== ownershipDescription) {
      return {
        state: 'foreign', listPath, d: existing.d,
        error: `A same-title list '${title}' exists without the exact probe ownership marker; refusing to modify it.`,
      };
    }
    return { state: 'owned', listPath, d: existing.d };
  }

  async function recycleOwnedList(title, ownershipDescription) {
    const inspected = await inspectOwnedList(title, ownershipDescription);
    if (inspected.state === 'missing') return { ok: true, removed: false };
    if (inspected.state !== 'owned') {
      return { ok: false, removed: false, error: inspected.error };
    }
    const recycled = await post(`${inspected.listPath}/recycle`);
    return {
      ok: recycled.ok,
      removed: recycled.ok,
      error: recycled.ok ? null : `HTTP ${recycled.status}: ${recycled.error}`,
    };
  }

  async function prepareOwnedList(title, ownershipDescription, removeExisting) {
    const inspected = await inspectOwnedList(title, ownershipDescription);
    if (inspected.state === 'foreign' || inspected.state === 'error') {
      return { ok: false, existing: null, error: inspected.error };
    }
    if (inspected.state === 'owned' && removeExisting) {
      const recycled = await recycleOwnedList(title, ownershipDescription);
      if (!recycled.ok) return { ok: false, existing: null, error: recycled.error };
      return { ok: true, existing: null, removed: true };
    }
    return {
      ok: true,
      existing: inspected.state === 'owned' ? inspected.d : null,
      removed: false,
    };
  }

  const TARGET_OWNERSHIP = 'dbml-sharepoint multi-value lookup probe target. Safe to delete.';
  const OWNERSHIP_DESCRIPTION = 'dbml-sharepoint multi-value lookup probe. Safe to delete.';
  const listPath = `web/lists/getbytitle('${odataName(PROBE_LIST)}')`;
  const targetPath = `web/lists/getbytitle('${odataName(TARGET_LIST)}')`;
  const fieldPath = (name) => `${listPath}/fields/getbyinternalnameortitle('${odataName(name)}')`;
  // Every URL this probe logs is built on a literal placeholder rather than
  // window.location.origin, because the results get pasted back into an issue.
  // The shared pre-flight banner above prints the real host on purpose, and it
  // runs only while CONFIRMED is false, so it is never part of a transcript.
  const TENANT = '[TENANT]';
  let createdProbeList = false;
  let createdTargetList = false;

  const show = (value) => {
    try { return JSON.stringify(value); } catch { return String(value); }
  };
  const httpNote = (r) => (r.ok ? `HTTP ${r.status}` : `REFUSED HTTP ${r.status} ${r.error}`);
  const deleteField = (name) => post(
    fieldPath(name), undefined, { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' },
  );
  const dump = () => console.table(results.map(
    ({ id, question, observed, detail }) => ({ id, question, observed, detail }),
  ));
  // A setup failure returns rather than throwing, so the table still prints.
  // A thrown error would leave every row at its NOT ESTABLISHED placeholder
  // with nothing on screen saying which of them were never asked.
  const bail = (reason) => {
    dump();
    log('ERROR', `Setup failed (${reason}). Nothing below it was measured.`);
    return { aborted: reason, results };
  };

  try {
    // === Setup: two lists =================================================
    // The probe list is prepared FIRST. Its lookups reference the target, and
    // SharePoint refuses to recycle a list another list looks up into, so a
    // cleanup that took the target first would fail and leave both standing.
    const preparedProbe = await prepareOwnedList(PROBE_LIST, OWNERSHIP_DESCRIPTION, CLEANUP);
    const preparedTarget = await prepareOwnedList(TARGET_LIST, TARGET_OWNERSHIP, CLEANUP);
    if (!preparedProbe.ok || !preparedTarget.ok) {
      record('field.multilookup.fixture-lists-created', 'setup', 'ABORTED',
        `${preparedProbe.error || ''} ${preparedTarget.error || ''}`.trim());
      return bail('fixture-ownership');
    }
    if (preparedProbe.existing || preparedTarget.existing) {
      record('field.multilookup.fixture-lists-created', 'setup', 'ABORTED',
        `A fixture from a previous run is still in place (${preparedProbe.existing ? PROBE_LIST : ''}`
        + `${preparedProbe.existing && preparedTarget.existing ? ', ' : ''}`
        + `${preparedTarget.existing ? TARGET_LIST : ''}). Every question below would be answered by `
        + 'columns that run created, which is much weaker evidence than creating them. Re-run with '
        + 'CLEANUP = true.');
      return bail('fixture-retained');
    }

    const madeTarget = await post('web/lists', {
      __metadata: { type: 'SP.List' },
      BaseTemplate: 100,
      Title: TARGET_LIST,
      Description: TARGET_OWNERSHIP,
    });
    if (!madeTarget.ok) {
      record('field.multilookup.fixture-lists-created', 'the fixture actually built', 'ABORTED',
        `could not create the target list: HTTP ${madeTarget.status} ${madeTarget.error}`);
      return bail('target-list-not-created');
    }
    createdTargetList = true;
    const madeProbe = await post('web/lists', {
      __metadata: { type: 'SP.List' },
      BaseTemplate: 100,
      Title: PROBE_LIST,
      Description: OWNERSHIP_DESCRIPTION,
    });
    if (!madeProbe.ok) {
      record('field.multilookup.fixture-lists-created', 'the fixture actually built', 'ABORTED',
        `could not create the probe list: HTTP ${madeProbe.status} ${madeProbe.error}`);
      return bail('probe-list-not-created');
    }
    createdProbeList = true;
    // The target's GUID, not its title: a lookup is created by LookupListId,
    // and `List="{...}"` in field XML wants the same value.
    const targetListId = madeTarget.d?.Id || null;
    log('INFO', `Created '${TARGET_LIST}' (${targetListId}) and '${PROBE_LIST}'.`);
    if (!targetListId) {
      record('field.multilookup.fixture-lists-created', 'the fixture actually built', 'ABORTED',
        'the target list was created but its Id was not in the response, so no lookup can name it');
      return bail('target-list-id-unknown');
    }

    // Seed the target. Checked rather than assumed: a lookup into an empty
    // list creates cleanly and then has no id to write, which would read as
    // the item questions failing.
    let targetType = null;
    try {
      targetType = await entityTypeFor(TARGET_LIST);
    } catch (err) {
      record('field.multilookup.fixture-lists-created', 'the fixture actually built', 'ABORTED',
        `could not resolve the target list's item entity type: ${err.message}`);
      return bail('target-entity-type-unknown');
    }
    const seedErrors = [];
    const targetIds = [];
    for (const title of TARGET_ROWS) {
      const seeded = await post(`${targetPath}/items`, {
        __metadata: { type: targetType }, Title: title,
      });
      if (seeded.ok && seeded.d?.Id !== undefined) targetIds.push(seeded.d.Id);
      else seedErrors.push(`${title}: HTTP ${seeded.status} ${seeded.error}`);
    }
    // The two ids every item write below uses. Charlie is deliberately left
    // out so a write that stores every row is distinguishable from one that
    // stores the pair it was given.
    const WRITE_IDS = targetIds.slice(0, 2);

    // === control-single-value-lookup-created ==============================
    // The deployer's own create path, unchanged. SharePoint refuses a plain
    // POST of SP.FieldLookup to /fields ("Please use addfield to add a lookup
    // field"), which is why deploy.js uses FieldCollection.AddField with an
    // SP.FieldCreationInformation nested under `parameters`. See
    // templates/deploy/_lists.js.j2. If this refuses, nothing below can
    // attribute a refusal to multiplicity rather than to the lookup machinery.
    const addLookup = (title, extra) => post(`${listPath}/fields/addfield`, {
      parameters: {
        __metadata: { type: 'SP.FieldCreationInformation' },
        FieldTypeKind: 7,
        Title: title,
        LookupListId: targetListId,
        LookupFieldName: 'Title',
        ...(extra || {}),
      },
    });
    const madeSingle = await addLookup(SINGLE);
    const singleBack = await get(
      `${fieldPath(SINGLE)}?$select=InternalName,TypeAsString,FieldTypeKind,AllowMultipleValues,Indexed,LookupList,LookupField`,
    );
    const controlLookupHeld = madeSingle.ok && singleBack.ok;
    record(
      'field.multilookup.control-single-value-lookup-created',
      'CONTROL: a plain single-value Lookup into the target is created by the deployer\'s own AddField path',
      controlLookupHeld ? 'CREATED' : (madeSingle.ok ? 'CREATED, READBACK UNREADABLE' : 'REFUSED'),
      `AddField ${httpNote(madeSingle)}, readback ${singleBack.ok
        ? `TypeAsString=${show(singleBack.d?.TypeAsString)} FieldTypeKind=${show(singleBack.d?.FieldTypeKind)} `
          + `AllowMultipleValues=${show(singleBack.d?.AllowMultipleValues)} LookupList=${show(singleBack.d?.LookupList)}`
        : `FAILED HTTP ${singleBack.status} ${singleBack.error}`}. `
      + 'A refusal here is about lookups, the target list or this identity, and NOT about multiplicity. '
      + 'Every multi-value row below is void while it stands.',
    );

    // === create-readback-type (#409 question 1) ===========================
    // Three candidate create paths, tried in order and ALL recorded. The
    // ordering is cheapest-first for the deployer: the first would need no new
    // creation machinery at all, the second needs a second create path beside
    // AddField, and the third needs a create followed by a patch.
    //
    // Candidate 1 is the deployer's AddField call with the flag added.
    // SP.FieldCreationInformation is not documented to carry
    // AllowMultipleValues, so the interesting outcome is not a refusal but an
    // ACCEPTED whose readback says false: a create that silently drops the one
    // property being asked for is exactly the failure class this directory
    // exists to catch.
    //
    // Candidate 2 is the createfieldasxml spelling
    // library-column-interactions-probe.js already carries for a library, on
    // the same `Options: 8` call projected-lookup-probe.js proved works for a
    // dependent lookup. A refusal here does not separate "SharePoint Online
    // will not make one this way" from "this attribute spelling is wrong", and
    // the recorded detail says so rather than crediting the stronger reading.
    //
    // Candidate 3 creates a plain lookup and patches the flag on. It uses the
    // same mechanism the mutability row measures independently on its own
    // field, which is a replication rather than waste: if one works and the
    // other does not, that disagreement is itself the finding.
    const createCandidates = [
      {
        name: 'addfield-allowmultiplevalues',
        run: () => addLookup(MULTI, { AllowMultipleValues: true }),
      },
      {
        name: 'createfieldasxml-lookupmulti',
        run: () => post(`${listPath}/fields/createfieldasxml`, {
          parameters: {
            SchemaXml: `<Field Type="LookupMulti" Mult="TRUE" DisplayName="${MULTI}" `
              + `Name="${MULTI}" List="{${targetListId}}" ShowField="Title"/>`,
            Options: 8,
          },
        }),
      },
      {
        name: 'addfield-then-merge-allowmultiplevalues',
        run: async () => {
          const made = await addLookup(MULTI);
          if (!made.ok) return made;
          return merge(fieldPath(MULTI), {
            __metadata: { type: 'SP.FieldLookup' }, AllowMultipleValues: true,
          });
        },
      },
    ];
    const FIELD_SELECT = '?$select=Id,InternalName,Title,TypeAsString,FieldTypeKind,'
      + 'AllowMultipleValues,Indexed,EnforceUniqueValues,LookupList,LookupField';
    const createAttempts = [];
    let winningCreate = null;
    let multiShape = null;
    if (controlLookupHeld) {
      for (const candidate of createCandidates) {
        const attempt = await candidate.run();
        const back = await get(`${fieldPath(MULTI)}${FIELD_SELECT}`);
        createAttempts.push(
          `${candidate.name}: write ${httpNote(attempt)}, readback ${back.ok
            ? `TypeAsString=${show(back.d?.TypeAsString)} FieldTypeKind=${show(back.d?.FieldTypeKind)} `
              + `AllowMultipleValues=${show(back.d?.AllowMultipleValues)}`
            : `FAILED HTTP ${back.status} ${back.error}`}`,
        );
        if (back.ok && back.d?.AllowMultipleValues === true) {
          winningCreate = candidate;
          multiShape = back;
          break;
        }
        // A field that exists and is not multi-value has to go: it would block
        // the next candidate on its name, and left in place it would answer the
        // index and item rows about a single-value column.
        if (back.ok) {
          const removed = await deleteField(MULTI);
          if (!removed.ok) {
            createAttempts.push(
              `(the field ${candidate.name} left behind could not be deleted: `
              + `HTTP ${removed.status} ${removed.error}, so every candidate after it is blocked on the name)`,
            );
            break;
          }
        }
      }
    }
    record(
      'field.multilookup.create-readback-type',
      'which create path takes AllowMultipleValues:true, and what the field reads back as',
      controlLookupHeld
        ? (winningCreate ? `CREATED: ${winningCreate.name}` : 'NO CREATE PATH ACCEPTED')
        : 'NOT ESTABLISHED',
      controlLookupHeld
        ? `tried in order ${createCandidates.map((c) => c.name).join(', ')}. `
          + `${createAttempts.join(' || ')}. `
          + (winningCreate
            ? `The winning field reads back TypeAsString=${show(multiShape.d?.TypeAsString)} `
              + `FieldTypeKind=${show(multiShape.d?.FieldTypeKind)} `
              + `AllowMultipleValues=${show(multiShape.d?.AllowMultipleValues)} `
              + `Indexed=${show(multiShape.d?.Indexed)} `
              + `EnforceUniqueValues=${show(multiShape.d?.EnforceUniqueValues)} `
              + `LookupList=${show(multiShape.d?.LookupList)} LookupField=${show(multiShape.d?.LookupField)} `
              + `entity type=${show(multiShape.d?.__metadata?.type)}. `
              + 'Report TypeAsString and FieldTypeKind verbatim: the reconciler\'s shape check has to '
              + 'recognise whatever this is, and nothing in the codebase knows it yet.'
            : 'No candidate produced a field that reads back AllowMultipleValues=true, so the index and '
              + 'item rows below have no multi-value column to ask about. A candidate that was ACCEPTED '
              + 'and read back false is the dangerous outcome, not the harmless one: the create would '
              + 'succeed, the deploy would verify, and the column would be single-valued. A refusal of '
              + 'the createfieldasxml candidate does not separate a capability SharePoint Online lacks '
              + 'from an attribute spelling this probe got wrong.')
        : 'the single-value lookup control did not hold, so a refusal here cannot be attributed to '
          + 'multiplicity rather than to lookups on this list or this identity.',
      controlLookupHeld ? undefined : 'void',
    );
    // The entity type SharePoint itself reported for the field, used for every
    // patch below. Guessing it is avoidable here: an SP.FieldLookup that
    // reports some other type would refuse a MERGE naming the wrong one, and
    // that refusal would be recorded as an answer about Indexed.
    const multiMetaType = multiShape?.d?.__metadata?.type || 'SP.FieldLookup';
    // ASCII by construction (`Parties`), but read back rather than assumed:
    // the item write shape is keyed on the INTERNAL name, and a create path
    // that renamed the column would make every item row 400 for a reason that
    // has nothing to do with multiplicity.
    const multiName = multiShape?.d?.InternalName || MULTI;
    const idField = `${multiName}Id`;

    // === control-single-value-indexed / indexed-property (#409 question 2) =
    // The index question and its control, in the shape multi-value-probe.js
    // uses for the same pair. A single-value lookup carrying Indexed is a
    // shipping path here: SP.FieldCreationInformation has no Indexed, so a
    // [unique] lookup gets both Indexed and EnforceUniqueValues from the MERGE
    // reconcileDeclaredField issues straight after AddField. If that control
    // does not hold, the property is not reporting what this question needs on
    // this tenant and both rows are void.
    //
    // The readback GET is kept rather than folded into a default. A readback
    // that never arrived is not an observation of false, and reporting it as
    // "did not stick" would state something this run never saw.
    const indexOne = async (path, metaType) => {
      const wrote = await merge(path, { __metadata: { type: metaType }, Indexed: true });
      const back = await get(`${path}?$select=Indexed`);
      return { wrote, back };
    };
    const notAttempted = { ok: false, status: 0, error: 'the field was never created' };
    const singleIndex = controlLookupHeld
      ? await indexOne(fieldPath(SINGLE), 'SP.FieldLookup')
      : { wrote: notAttempted, back: notAttempted };
    const multiIndex = winningCreate
      ? await indexOne(fieldPath(MULTI), multiMetaType)
      : { wrote: notAttempted, back: notAttempted };
    const indexReadback = (r) => (r.back.ok
      ? show(r.back.d?.Indexed)
      : `UNREADABLE (HTTP ${r.back.status} ${r.back.error})`);
    const indexControlHeld = singleIndex.wrote.ok && singleIndex.back.ok
      && singleIndex.back.d?.Indexed === true;
    record(
      'field.multilookup.control-single-value-indexed',
      'CONTROL: Indexed:true on the SINGLE-value Lookup, which this repository already provisions',
      indexControlHeld
        ? 'STUCK'
        : (singleIndex.wrote.ok && !singleIndex.back.ok ? 'READBACK UNREADABLE' : 'DID NOT STICK'),
      `write ${httpNote(singleIndex.wrote)}, readback Indexed=${indexReadback(singleIndex)}`,
    );
    record(
      'field.multilookup.indexed-property',
      'Indexed:true on a multi-value Lookup: accepted? and what does it read back as?',
      (indexControlHeld && winningCreate)
        ? (multiIndex.wrote.ok
          ? (multiIndex.back.ok
            ? (multiIndex.back.d?.Indexed === true ? 'ACCEPTED AND STUCK' : 'ACCEPTED BUT DID NOT STICK')
            : 'ACCEPTED, READBACK UNREADABLE')
          : 'REFUSED')
        : 'NOT ESTABLISHED',
      (indexControlHeld && winningCreate)
        ? `write ${httpNote(multiIndex.wrote)}, readback Indexed=${indexReadback(multiIndex)}. `
          + (multiIndex.wrote.ok && !multiIndex.back.ok
            ? 'The write was taken and the readback never arrived, so whether it stuck is NOT established '
              + 'by this run, and that is a different finding from a property that read back false. '
            : '')
          + 'REFUSED means every view filtering a multi-value lookup is a threshold hazard and the index '
          + 'validator needs a new refusal by name. ACCEPTED AND STUCK means it does not, and the '
          + 'existing index machinery extends to this column unchanged. ACCEPTED BUT DID NOT STICK is '
          + 'the one that needs a guard rather than a rule: the deploy would claim an index that is not '
          + 'there, and only a readback could ever see the difference.'
        : (winningCreate
          ? `the single-value index control did not hold (Indexed=${indexReadback(singleIndex)}), so this `
            + 'property is not reporting what the question needs on this tenant and the row is void. That '
            + 'is the outcome native-index-probe.js hit with its own control on 2026-07-30.'
          : 'no multi-value lookup column was created, so there was nothing to index.'),
      (indexControlHeld && winningCreate) ? undefined : 'void',
    );

    // === allow-multiple-values-mutability (#409 question 3) ===============
    // Asked on a field of its own so the index control is never asked about a
    // column this probe has mutated. Both directions, because the reconciler
    // sees drift either way: a property that widens but will not narrow is an
    // asymmetric finding and decides whether AllowMultipleValues joins
    // IMMUTABLE_LOOKUP_PROPERTIES in one direction or both.
    const madeFlip = controlLookupHeld ? await addLookup(FLIP) : notAttempted;
    const flipOn = madeFlip.ok
      ? await merge(fieldPath(FLIP), {
        __metadata: { type: 'SP.FieldLookup' }, AllowMultipleValues: true,
      })
      : notAttempted;
    const flipOnBack = madeFlip.ok
      ? await get(`${fieldPath(FLIP)}?$select=AllowMultipleValues,TypeAsString`)
      : { ok: false, status: 0, error: 'the field was never created', d: null };
    const widened = flipOn.ok && flipOnBack.ok && flipOnBack.d?.AllowMultipleValues === true;
    // Narrowing is only a question once there is something to narrow. Asked
    // against the type the widened field now reports, for the reason the
    // create readback gives above.
    const flipOff = widened
      ? await merge(fieldPath(FLIP), {
        __metadata: { type: flipOnBack.d?.__metadata?.type || 'SP.FieldLookup' },
        AllowMultipleValues: false,
      })
      : notAttempted;
    const flipOffBack = widened
      ? await get(`${fieldPath(FLIP)}?$select=AllowMultipleValues,TypeAsString`)
      : { ok: false, status: 0, error: 'the field was never widened', d: null };
    const narrowed = flipOff.ok && flipOffBack.ok && flipOffBack.d?.AllowMultipleValues === false;
    record(
      'field.multilookup.allow-multiple-values-mutability',
      'AllowMultipleValues on an EXISTING lookup: can it be turned on, and can it be turned off again?',
      !madeFlip.ok
        ? 'NOT ESTABLISHED'
        : (widened
          ? (narrowed ? 'MUTABLE BOTH WAYS' : 'WIDENS ONLY')
          : (flipOn.ok ? 'WIDEN ACCEPTED BUT DID NOT STICK' : 'WIDEN REFUSED')),
      !madeFlip.ok
        ? `the single-value field '${FLIP}' this row mutates was never created (${httpNote(madeFlip)}), `
          + 'so neither direction was asked.'
        : `single -> multi: write ${httpNote(flipOn)}, readback `
          + `AllowMultipleValues=${flipOnBack.ok ? show(flipOnBack.d?.AllowMultipleValues) : `UNREADABLE HTTP ${flipOnBack.status} ${flipOnBack.error}`} `
          + `TypeAsString=${flipOnBack.ok ? show(flipOnBack.d?.TypeAsString) : '(unread)'}. `
          + `multi -> single: ${widened
            ? `write ${httpNote(flipOff)}, readback `
              + `AllowMultipleValues=${flipOffBack.ok ? show(flipOffBack.d?.AllowMultipleValues) : `UNREADABLE HTTP ${flipOffBack.status} ${flipOffBack.error}`}`
            : 'NOT ASKED, because the field was never widened'}. `
          + 'WIDEN REFUSED puts AllowMultipleValues in IMMUTABLE_LOOKUP_PROPERTIES and means an existing '
          + 'single-value lookup can never be widened in place. WIDENS ONLY puts it there in one '
          + 'direction only, which the reconciler has no vocabulary for today. MUTABLE BOTH WAYS keeps '
          + 'it out and makes it an ordinary reconciled property.',
      madeFlip.ok ? undefined : 'void',
    );

    // === item-write-shape (#409 question 4) ===============================
    // Four candidates, and EVERY one is tried rather than stopping at the
    // first that works. Which shapes SharePoint accepts is more useful than
    // which one happens to be first: an accepted shape that stores the wrong
    // members is the answer worth having, and it is only visible by writing
    // all of them and reading them all back.
    //
    // Each candidate gets its own item, titled after the shape, so the read
    // row below can attribute what it sees.
    let itemType = null;
    if (winningCreate) {
      try {
        itemType = await entityTypeFor(PROBE_LIST);
      } catch (err) {
        log('ERROR', `Could not resolve the probe list's item entity type: ${err.message}`);
      }
    }
    const writeShapes = [
      { name: 'bare-results', build: (ids) => ({ [idField]: { results: ids } }) },
      {
        name: 'collection-metadata',
        build: (ids) => ({
          [idField]: { __metadata: { type: 'Collection(Edm.Int32)' }, results: ids },
        }),
      },
      { name: 'bare-array', build: (ids) => ({ [idField]: ids }) },
      // The field's own name rather than the Id alias. A lookup is written
      // through `<Name>Id` for a single value; whether the collection form
      // insists on the same alias is a separate question and it is cheap.
      { name: 'name-not-id-alias', build: (ids) => ({ [multiName]: { results: ids } }) },
    ];
    const writeAttempts = [];
    const written = [];
    const writesRunnable = !!winningCreate && itemType !== null && WRITE_IDS.length === 2;
    if (writesRunnable) {
      for (const shape of writeShapes) {
        const made = await post(`${listPath}/items`, {
          __metadata: { type: itemType },
          Title: `W ${shape.name}`,
          ...shape.build(WRITE_IDS),
        });
        writeAttempts.push(`${shape.name}: ${httpNote(made)}`);
        if (made.ok) written.push({ shape: shape.name, id: made.d?.Id ?? null });
      }
    }
    record(
      'field.multilookup.item-write-shape',
      'which item WRITE shapes SharePoint accepts for a multi-value lookup',
      writesRunnable
        ? (written.length
          ? `ACCEPTED: ${written.map((w) => w.shape).join(', ')}`
          : 'ALL FOUR REFUSED')
        : 'NOT ESTABLISHED',
      writesRunnable
        ? `wrote ids ${show(WRITE_IDS)} (${TARGET_ROWS[0]}, ${TARGET_ROWS[1]}) through '${idField}'. `
          + `${writeAttempts.join(' || ')}. `
          + 'ACCEPTED is only half the answer. The read row below says whether an accepted shape stored '
          + 'BOTH ids, one, or none, and a shape that is taken and stores the wrong members is the '
          + 'result the deployer must not emit.'
        : (!winningCreate
          ? 'no multi-value lookup column was created, so there was nothing to write to.'
          : (itemType === null
            ? 'the probe list\'s item entity type could not be resolved, so no item body could be built.'
            : `the target list seeded ${targetIds.length} row(s) rather than ${TARGET_ROWS.length}, so `
              + 'there was no pair of ids to write.')),
      writesRunnable ? undefined : 'void',
    );

    // === item-read-shape (#409 question 4) ================================
    // Three reads, because the deployer, the reconciler and the reporting
    // layer do not all speak the same OData dialect, and they need not agree.
    // The first two differ ONLY in their Accept header, so any difference
    // between them is the content type's doing and nothing else's. The third
    // is the $expand form reportgen would use to get labels rather than ids.
    const itemsPath = `${listPath}/items`;
    const idQuery = `${itemsPath}?$select=Id,Title,${idField}&$orderby=Id`;
    const expandQuery = `${itemsPath}?$select=Id,Title,${multiName}/Id,${multiName}/Title`
      + `&$expand=${multiName}&$orderby=Id`;
    const readVerbose = writesRunnable ? await get(idQuery) : null;
    const readNoMeta = writesRunnable
      ? await get(idQuery, 'application/json;odata=nometadata')
      : null;
    const readExpanded = writesRunnable ? await get(expandQuery) : null;
    const rowsOf = (r) => (r?.d?.results || r?.d?.value || []);
    const describe = (r, key) => (r
      ? (r.ok
        ? show(rowsOf(r).map((row) => ({ [row.Title]: row[key] })))
        : `REQUEST FAILED HTTP ${r.status}: ${r.error} (not observed to be empty, not observed at all)`)
      : 'not attempted');
    // Named individually rather than collapsed to one head. A column that is
    // readable under $expand and 400s under a plain $select is a different
    // answer for the reader than one that is readable everywhere, and both
    // would otherwise print as READ.
    const readsThatWorked = [
      ['verbose-select', readVerbose],
      ['nometadata-select', readNoMeta],
      ['verbose-expand', readExpanded],
    ].filter(([, r]) => r?.ok && rowsOf(r).length).map(([name]) => name);
    record(
      'field.multilookup.item-read-shape',
      'what a multi-value lookup value READS BACK as',
      writesRunnable
        ? (readsThatWorked.length ? `READ: ${readsThatWorked.join(', ')}` : 'ALL THREE READS FAILED')
        : 'NOT ESTABLISHED',
      writesRunnable
        ? `verbose $select=${idField}: ${describe(readVerbose, idField)} || `
          + `nometadata $select=${idField}: ${describe(readNoMeta, idField)} || `
          + `verbose $expand=${multiName}: ${describe(readExpanded, multiName)}. `
          + `Each row is keyed by the WRITE shape that produced it. The ids asked for were `
          + `${show(WRITE_IDS)}; a row holding anything else was accepted and stored something other `
          + 'than what it was given. Report all three verbatim: whether the value arrives as an array, '
          + 'a { results: [...] } object or a delimited string decides what extract/decode.py has to '
          + 'read and what reportgen has to flatten, and the three dialects need not agree.'
        : 'no item carrying a multi-value lookup was written, so there was nothing to read.',
      writesRunnable ? undefined : 'void',
    );

    // === fixture-lists-created ============================================
    // Recorded last, because it reports on what everything above depended on.
    // Deliberately says nothing about the multi-value column: whether one can
    // exist at all is the create row's question, and folding it in here would
    // let a fixture FAILED stand in for an answer this probe was built to give.
    const targetCount = await get(`${targetPath}/ItemCount`);
    const seededCount = targetCount.ok ? Number(targetCount.d.ItemCount) : NaN;
    const fixtureBuilt = createdProbeList && createdTargetList
      && seededCount === TARGET_ROWS.length && !seedErrors.length && controlLookupHeld;
    record(
      'field.multilookup.fixture-lists-created',
      'the fixture actually built: two lists, three target rows, the control columns',
      fixtureBuilt ? 'BUILT' : 'FAILED',
      `target '${TARGET_LIST}' ItemCount=${seededCount}/${TARGET_ROWS.length} ids=${show(targetIds)} `
      + `probe list='${PROBE_LIST}' single-value control field=${controlLookupHeld ? 'created' : 'FAILED'} `
      + `${seedErrors.join('; ')}`,
    );
    if (!fixtureBuilt) {
      log('ERROR', 'The fixture is not what the rows above assume. Fix it and re-run before reporting.');
    }

    // === Verdict ==========================================================
    dump();
    const observedFor = (id) => results.find((r) => r.id === id)?.observed;
    log(
      'VERDICT',
      `fixture=${fixtureBuilt ? 'ok' : 'FAILED'} `
      + `create=${observedFor('field.multilookup.create-readback-type')} `
      + `type_as_string=${show(multiShape?.d?.TypeAsString)} `
      + `field_type_kind=${show(multiShape?.d?.FieldTypeKind)} `
      + `indexed=${observedFor('field.multilookup.indexed-property')} `
      + `mutability=${observedFor('field.multilookup.allow-multiple-values-mutability')} `
      + `write_shapes=${written.length ? written.map((w) => w.shape).join('+') : 'none'} `
      + `read=${observedFor('field.multilookup.item-read-shape')}`,
    );
    log('INFO', 'Paste the VERDICT line and the whole table back. The TypeAsString and FieldTypeKind '
      + 'values are the point of the run: nothing in this codebase knows them yet.');
    return { results, winningCreate: winningCreate?.name || null, written };
  } finally {
    // Probe list first: SharePoint refuses to recycle a list that another
    // list's lookup points into, so taking the target first would fail and
    // leave both behind.
    if (CLEANUP) {
      for (const [title, marker, made] of [
        [PROBE_LIST, OWNERSHIP_DESCRIPTION, createdProbeList],
        [TARGET_LIST, TARGET_OWNERSHIP, createdTargetList],
      ]) {
        if (!made) continue;
        const gone = await recycleOwnedList(title, marker);
        if (gone.ok) {
          log('INFO', `Recycled '${title}'.`);
        } else {
          log('ERROR', `COULD NOT RECYCLE '${title}' (${gone.error}). Recycle it by hand: `
            + `${TENANT}${WEB}/Lists/${encodeURIComponent(title)}`);
        }
      }
    } else if (createdProbeList || createdTargetList) {
      log('INFO', `Left '${PROBE_LIST}' and '${TARGET_LIST}' in place. Re-run with CLEANUP = true to `
        + 'recycle them, and recycle the probe list BEFORE the target: a list another list looks up '
        + 'into cannot be removed.');
    }
  }
})();
