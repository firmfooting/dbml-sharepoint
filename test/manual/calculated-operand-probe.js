/**
 * dbml-sharepoint PROBE: CALCULATED COLUMN OPERAND MATRIX
 *
 * QUESTION: which SharePoint column types may a calculated field reference?
 *
 * WHY: Microsoft documents Lookup fields as unsupported and lists the
 * supported scalar operand types, while this project had live evidence that
 * a Person operand is refused with HTTP 500. Long text, rich text and
 * hyperlink were ambiguous (absent from Microsoft's supported list, which is
 * not the same as documented against), so they were kept OUT of the
 * validator's denylist until this probe ran. See STATUS.
 *
 * SOURCE
 *   https://support.microsoft.com/en-us/sharepoint/lists/data-and-lists/examples-of-common-formulas-in-lists
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`:
 * `<surface>.<scope>.<question>`. The old mnemonic each one replaces is given
 * beside it, because the run recorded below quotes the mnemonics.
 *
 *   formula.calc.operand-lookup     (LOOK)  Lookup
 *   formula.calc.operand-person     (PERS)  Person
 *   formula.calc.operand-multiline  (LONG)  plain multi-line text
 *   formula.calc.operand-richtext   (RICH)  rich text
 *   formula.calc.operand-hyperlink  (LINK)  Hyperlink
 *   formula.calc.operand-boolean    (BOOL)  Yes/No
 *   formula.calc.operand-choice     (CHOI)  Choice
 *   formula.calc.operand-date       (DATE)  Date only
 *   formula.calc.operand-datetime   (TIME)  Date and time
 *   formula.calc.operand-number     (NUMB)  Number
 *   formula.calc.operand-text       (TEXT)  single line of text
 *   formula.calc.operand-calculated (CALC)  another calculated field
 *
 * Each row records the createfieldasxml HTTP status and SharePoint error
 * body. Creation is the relevant gate: the deployment currently dies there,
 * part-way through provisioning.
 *
 * HOW TO RUN
 *   1. Open a disposable SharePoint Online site you own.
 *   2. F12 -> Console -> paste -> Enter. The committed defaults only print.
 *   3. Set CONFIRMED and ALLOW_WRITES to true. Set CLEANUP to true for a
 *      clean run and CLEANUP_AT_END to true to recycle both probe lists.
 *   4. Paste again and copy the complete RESULTS block back verbatim.
 *
 * STATUS: RUN 2026-07-30 against a live SharePoint Online site. All twelve
 * questions answered, none left open. Verbatim outcome:
 *
 *   LOOK  REFUSED    Lookup
 *   PERS  REFUSED    Person
 *   LONG  REFUSED    plain multi-line text (Note, RichText="FALSE")
 *   RICH  REFUSED    rich text (Note, RichText="TRUE")
 *   LINK  REFUSED    Hyperlink (URL)
 *   BOOL  ACCEPTED   Yes/No
 *   CHOI  ACCEPTED   Choice
 *   DATE  ACCEPTED   Date only
 *   TIME  ACCEPTED   Date and time
 *   NUMB  ACCEPTED   Number
 *   TEXT  ACCEPTED   single line of text
 *   CALC  ACCEPTED   another calculated column
 *
 * Every refusal was HTTP 500 with one identical body:
 *
 *   {"odata.error":{"code":"-2130575272, Microsoft.SharePoint.SPException",
 *    "message":{"lang":"en-US","value":"One or more column references are not
 *    allowed, because the columns are defined as a data type that is not
 *    supported in formulas."}}}
 *
 * All five refused types are now in _FORBIDDEN_CALCULATED_OPERANDS in
 * analysis/checks/_structure.py, so the build refuses them before a script is
 * emitted. Note what the run also showed: the three ambiguous types were
 * refused, so the cautious guess would have been RIGHT, and that is not a
 * reason to guess next time. The same caution kept Yes/No out of the
 * denylist, where a guess would have been WRONG.
 *
 * Incidental, and worth knowing before reading a future run: a GET on
 * fields/getbyinternalnameortitle() for a field that does not exist answers
 * HTTP 400, not 404. fieldExists() treats any non-2xx as absent, so this is
 * already handled, but a reader scanning the console for 404s will not find
 * them.
 */
(async () => {
  const CONFIRMED = false;
  const ALLOW_WRITES = false;
  const CLEANUP = false;
  const CLEANUP_AT_END = false;
  const PROBE_RETRY_TRANSIENT = true;
  const PROBE_RETRY_ATTEMPTS = 5;

  const LIST = 'dbmlsp Probe CalcOperands';
  const TARGET = `${LIST} Target`;
  const OWNERSHIP_DESCRIPTION = 'dbml-sharepoint calculated-operand probe. Safe to recycle.';

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
  const QUESTIONS = [
    ['formula.calc.operand-lookup', 'Lookup operand in a calculated formula'],
    ['formula.calc.operand-person', 'Person operand in a calculated formula'],
    ['formula.calc.operand-multiline', 'Plain multi-line-text operand in a calculated formula'],
    ['formula.calc.operand-richtext', 'Rich-text operand in a calculated formula'],
    ['formula.calc.operand-hyperlink', 'Hyperlink operand in a calculated formula'],
    ['formula.calc.operand-boolean', 'Yes/No operand in a calculated formula'],
    ['formula.calc.operand-choice', 'Choice operand in a calculated formula'],
    ['formula.calc.operand-date', 'Date-only operand in a calculated formula'],
    ['formula.calc.operand-datetime', 'Date-and-time operand in a calculated formula'],
    ['formula.calc.operand-number', 'Number operand in a calculated formula'],
    ['formula.calc.operand-text', 'Single-line-text operand in a calculated formula'],
    ['formula.calc.operand-calculated', 'Calculated-column operand in another calculated formula'],
  ];
  // Literal registrations are deliberate: test_probes statically proves that
  // every record('ID', ...) of a DECLARED QUESTION has a matching upfront
  // expect('ID', ...), so an aborted run cannot make unanswered questions
  // disappear. BOOT-prefixed ids are exempt there by design. They report a
  // bootstrap failure rather than answering a question, so there is no
  // question for them to hide.
  expect('formula.calc.operand-lookup', 'Lookup operand in a calculated formula');
  expect('formula.calc.operand-person', 'Person operand in a calculated formula');
  expect('formula.calc.operand-multiline', 'Plain multi-line-text operand in a calculated formula');
  expect('formula.calc.operand-richtext', 'Rich-text operand in a calculated formula');
  expect('formula.calc.operand-hyperlink', 'Hyperlink operand in a calculated formula');
  expect('formula.calc.operand-boolean', 'Yes/No operand in a calculated formula');
  expect('formula.calc.operand-choice', 'Choice operand in a calculated formula');
  expect('formula.calc.operand-date', 'Date-only operand in a calculated formula');
  expect('formula.calc.operand-datetime', 'Date-and-time operand in a calculated formula');
  expect('formula.calc.operand-number', 'Number operand in a calculated formula');
  expect('formula.calc.operand-text', 'Single-line-text operand in a calculated formula');
  expect('formula.calc.operand-calculated', 'Calculated-column operand in another calculated formula');

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
  log('INFO', `probe revision c1e98851; core v2; results v1.`);
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

  // Main first because it owns the lookup into TARGET.
  const preparedMain = await prepareOwnedList(LIST, OWNERSHIP_DESCRIPTION, CLEANUP);
  const preparedTarget = await prepareOwnedList(TARGET, OWNERSHIP_DESCRIPTION, CLEANUP);
  if (!preparedMain.ok || !preparedTarget.ok) {
    record(
      'BOOTOWNERSHIP',
      'Probe fixture ownership is established before mutation',
      'ABORTED',
      preparedMain.error || preparedTarget.error,
    );
    console.table(results);
    return { results };
  }

  // bootId is per LIST, not a shared 'BOOT'. record() overwrites by id, so one
  // id for both lists means whichever fails second erases the first, and the
  // surviving row names the wrong list in its own question text. Two lists
  // bootstrap here, so two ids.
  const ensureList = async (title, bootId) => {
    const existing = await get(
      `web/lists/getbytitle('${odataName(title)}')?$select=Id,Description`,
    );
    if (existing.ok) return existing.d;
    const created = await post('web/lists', {
      __metadata: { type: 'SP.List' },
      Title: title,
      BaseTemplate: 100,
      Description: OWNERSHIP_DESCRIPTION,
    });
    if (!created.ok) {
      record(bootId, `Create probe list ${title}`, 'FAIL',
             `HTTP ${created.status}: ${created.error}`);
      return null;
    }
    // SharePoint's response shape varies with OData mode and can be empty
    // after a successful create. Re-read the list so the Lookup schema below
    // always receives a measured Id rather than trusting the POST payload.
    const reread = await get(
      `web/lists/getbytitle('${odataName(title)}')?$select=Id`,
    );
    if (!reread.ok || !reread.d || !reread.d.Id) {
      record(bootId, `Read back probe list ${title}`, 'FAIL',
             `HTTP ${reread.status}: successful create returned no usable list Id`);
      return null;
    }
    return reread.d;
  };

  // Both are attempted even if the first fails, so one run reports the state
  // of both lists rather than only the one it reached.
  const target = await ensureList(TARGET, 'BOOTTARGET');
  const main = await ensureList(LIST, 'BOOTMAIN');
  if (!target || !main) {
    console.table(results);
    return { results };
  }

  const fieldsPath = `web/lists/getbytitle('${odataName(LIST)}')/fields`;
  const xmlAttr = (value) => String(value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const fieldExists = async (name) =>
    (await get(`${fieldsPath}/getbyinternalnameortitle('${odataName(name)}')?$select=Id`)).ok;
  const addField = async (schemaXml) => post(`${fieldsPath}/createfieldasxml`, {
    parameters: { SchemaXml: schemaXml, Options: 8 },
  });

  const choiceXml =
    '<Field Type="Choice" DisplayName="ProbeChoice" Name="ProbeChoice" Format="Dropdown">' +
    '<CHOICES><CHOICE>Alpha</CHOICE><CHOICE>Beta</CHOICE></CHOICES></Field>';
  const sources = [
    ['ProbeLookup',
     `<Field Type="Lookup" DisplayName="ProbeLookup" Name="ProbeLookup" ` +
     `List="{${target.Id}}" ShowField="Title"/>`],
    ['ProbePerson',
     '<Field Type="User" DisplayName="ProbePerson" Name="ProbePerson" ' +
     'UserSelectionMode="PeopleOnly"/>'],
    ['ProbeLong',
     '<Field Type="Note" DisplayName="ProbeLong" Name="ProbeLong" ' +
     'RichText="FALSE" NumLines="6"/>'],
    ['ProbeRich',
     '<Field Type="Note" DisplayName="ProbeRich" Name="ProbeRich" ' +
     'RichText="TRUE" RichTextMode="FullHtml" NumLines="6"/>'],
    ['ProbeLink',
     '<Field Type="URL" DisplayName="ProbeLink" Name="ProbeLink" Format="Hyperlink"/>'],
    ['ProbeBool',
     '<Field Type="Boolean" DisplayName="ProbeBool" Name="ProbeBool"/>'],
    ['ProbeChoice', choiceXml],
    ['ProbeDate',
     '<Field Type="DateTime" DisplayName="ProbeDate" Name="ProbeDate" Format="DateOnly"/>'],
    ['ProbeTime',
     '<Field Type="DateTime" DisplayName="ProbeTime" Name="ProbeTime" Format="DateTime"/>'],
    ['ProbeNumber',
     '<Field Type="Number" DisplayName="ProbeNumber" Name="ProbeNumber"/>'],
    ['ProbeText',
     '<Field Type="Text" DisplayName="ProbeText" Name="ProbeText" MaxLength="255"/>'],
  ];
  const sourceReady = new Set();
  for (const [name, schemaXml] of sources) {
    if (await fieldExists(name)) {
      sourceReady.add(name);
      continue;
    }
    const made = await addField(schemaXml);
    if (made.ok) {
      sourceReady.add(name);
    } else {
      log('FAIL', `Could not create source ${name}: HTTP ${made.status} ${made.error}`);
    }
  }

  const calcXml = (name, formula, refs, resultType = 'Text') =>
    `<Field Type="Calculated" DisplayName="${name}" Name="${name}" ` +
    `ResultType="${resultType}">` +
    `<Formula>${xmlAttr(formula)}</Formula>` +
    `<FieldRefs>${refs.map((ref) => `<FieldRef Name="${ref}"/>`).join('')}</FieldRefs>` +
    '</Field>';

  const attempts = [
    ['formula.calc.operand-lookup', 'ProbeLookup', 'CalcLookup', '=[ProbeLookup]', 'Text'],
    ['formula.calc.operand-person', 'ProbePerson', 'CalcPerson', '=[ProbePerson]', 'Text'],
    ['formula.calc.operand-multiline', 'ProbeLong', 'CalcLong', '=[ProbeLong]', 'Text'],
    ['formula.calc.operand-richtext', 'ProbeRich', 'CalcRich', '=[ProbeRich]', 'Text'],
    ['formula.calc.operand-hyperlink', 'ProbeLink', 'CalcLink', '=[ProbeLink]', 'Text'],
    ['formula.calc.operand-boolean', 'ProbeBool', 'CalcBool', '=IF([ProbeBool],"yes","no")', 'Text'],
    ['formula.calc.operand-choice', 'ProbeChoice', 'CalcChoice', '=[ProbeChoice]', 'Text'],
    ['formula.calc.operand-date', 'ProbeDate', 'CalcDate', '=[ProbeDate]', 'DateTime'],
    ['formula.calc.operand-datetime', 'ProbeTime', 'CalcTime', '=[ProbeTime]', 'DateTime'],
    ['formula.calc.operand-number', 'ProbeNumber', 'CalcNumber', '=[ProbeNumber]', 'Number'],
    ['formula.calc.operand-text', 'ProbeText', 'CalcText', '=[ProbeText]', 'Text'],
  ];

  const questionFor = (id) => QUESTIONS.find(([candidate]) => candidate === id)[1];
  const attempt = async (id, source, output, formula, resultType) => {
    const question = questionFor(id);
    if (!sourceReady.has(source)) {
      record(id, question, 'NOT ESTABLISHED', `${source} could not be created`);
      return false;
    }
    if (await fieldExists(output)) {
      record(id, question, 'NOT ESTABLISHED',
             `${output} already exists; use CLEANUP=true for a real creation attempt`);
      return true;
    }
    const made = await addField(calcXml(output, formula, [source], resultType));
    record(
      id,
      question,
      made.ok ? 'ACCEPTED' : (isRefusal(made.status) ? 'REFUSED' : 'NOT ESTABLISHED'),
      `HTTP ${made.status}${made.error ? `: ${made.error}` : ''}`,
    );
    return made.ok;
  };

  for (const row of attempts) await attempt(...row);

  // CALC needs an accepted calculated source. Number is documented as a
  // supported operand and produces a simple, type-stable base field.
  const baseReady = await fieldExists('CalcNumber');
  if (!baseReady) {
    record('formula.calc.operand-calculated', questionFor('formula.calc.operand-calculated'),
           'NOT ESTABLISHED',
           'CalcNumber was not created, so no calculated source exists');
  } else {
    sourceReady.add('CalcNumber');
    await attempt('formula.calc.operand-calculated', 'CalcNumber', 'CalcCalculated',
                  '=[CalcNumber]', 'Number');
  }

  console.table(results);

  if (CLEANUP_AT_END) {
    // Main first: SharePoint may refuse to recycle a list still targeted by
    // a Lookup column on another list.
    for (const title of [LIST, TARGET]) {
      const recycled = await recycleOwnedList(title, OWNERSHIP_DESCRIPTION);
      log(
        recycled.ok ? 'OK' : 'FAIL',
        recycled.ok
          ? `Recycled '${title}'. It is recoverable from the site recycle bin.`
          : `Could not recycle '${title}': ${recycled.error}`,
      );
    }
  } else {
    log('INFO', `Probe lists remain: '${LIST}' and '${TARGET}'.`);
    log('INFO', 'After copying results, set CLEANUP_AT_END=true and rerun, or recycle them manually.');
  }
  return { results };
})();
