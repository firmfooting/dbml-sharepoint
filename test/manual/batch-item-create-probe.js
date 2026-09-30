
/** ---- dbml-sharepoint PROBE: WHAT A $BATCH OF ITEM CREATES ANSWERS, PART BY PART ----
 *
 * REVISION: ffea73da
 *
 * QUESTION: what does a `$batch` ChangeSet of item creates answer for each
 * part, including a part that fails, and may a part omit the list's
 * ListItemEntityTypeFullName? And for a ChangeSet of parts calling
 * AddValidateUpdateItemUsingPath, one of them made to fail: what does each part
 * answer, may a part omit listItemCreateInfo.FolderPath, and does formValues take
 * a person as claims and a date as ISO 8601 text?
 *
 * WHY: a flow that writes one history row per changed column sends them as
 * one `$batch`, each part calling AddValidateUpdateItemUsingPath; the plain item
 * creates are kept as a comparison. "Make batch requests with the REST APIs"
 * settles the request format and says a ChangeSet is not transactional; it
 * shows no item-create response. "Working with lists and list items with REST" sends the entity
 * type as `__metadata.type` on a single create, and a flow would rather not
 * have to read it first. Its "Create list item in a folder" section documents
 * AddValidateUpdateItemUsingPath with FolderPath.DecodedUrl, formValues and a
 * per-field HasException; it shows neither FolderPath omitted, nor a person, nor
 * a date among the formValues. These rows measure the browser's form, a digest on
 * every part and no Accept on the outer request; they do not cover a part sent
 * without a digest, as a flow's connector may send it.
 *
 * DEPENDS ON (read back, and voiding what rests on them when they do not hold)
 *   transport.batch.fixture-item-batch-list  a generic list this probe created,
 *       whose ListItemEntityTypeFullName reads back
 *   transport.batch.control-single-item-create  one single typed create lands and
 *       its Title reads back; without it a batch answer says nothing about the transport
 *   transport.batch.control-single-item-unknown-property-refused  a single typed
 *       create naming a column the list lacks is refused, and the items read shows no
 *       item under its Title; the failed-part row rests on it
 *   transport.batch.fixture-item-batch-columns  a person column and a date-and-time
 *       column read back with their TypeAsString, the date column with DisplayFormat 1;
 *       the claims and date rows rest on it
 *   transport.batch.control-current-user  this account's Id and Email read back; the
 *       claims row rests on it
 *   transport.batch.control-single-addvalidate-create  one AddValidateUpdateItemUsingPath
 *       call in Learn's form (FolderPath given, Title only) lands; the four rows below rest on it
 *   transport.batch.control-single-addvalidate-unknown-field-refused  one such call naming
 *       the missing column in formValues is refused, and the items read shows no item under
 *       its Title; the failed-part row rests on it
 *   A control that FAILs voids what rests on it; one NOT ESTABLISHED leaves it open.
 *
 * OBSERVES (recorded verbatim, never compared with an expected value)
 *   transport.batch.changeset-item-creates-per-part   three typed creates in one
 *       ChangeSet, the middle one naming the missing column: each part's status line,
 *       headers and body, and which of the three items exist afterwards
 *   transport.batch.changeset-item-create-failed-part the middle part's answer, and
 *       whether its neighbours landed
 *   transport.batch.changeset-item-create-untyped-verbose     one create with verbose
 *       part headers and no __metadata
 *   transport.batch.changeset-item-create-untyped-nometadata  one create with
 *       nometadata part headers and no type
 *   Every part's request line names the list by its title URL-encoded, its space as %20,
 *   and each $batch is sent only while that title still names the list this run created;
 *   otherwise its rows are NOT ESTABLISHED, left open. Every other request goes by the list's Id.
 *   One ChangeSet of four nometadata AddValidateUpdateItemUsingPath parts, the shape a
 *   history write sends, each recorded with its per-field answer, whether it landed, and
 *   what reads back:
 *   transport.batch.changeset-addvalidate-folderpath-omitted  no FolderPath, Title only
 *   transport.batch.changeset-addvalidate-failed-part  FolderPath given, naming the missing
 *       column; its answer, and whether its neighbours landed
 *   transport.batch.changeset-addvalidate-person-claims  FolderPath given, the person
 *       column as [{"Key":"i:0#.f|membership|<email>"}]
 *   transport.batch.changeset-addvalidate-date-iso  FolderPath given, the date column
 *       as ISO 8601 UTC text
 *
 * HOW TO READ IT: PART ANSWERED 2XX and PART REFUSED are what one part's status
 * line said, beside whether its item exists afterwards; a part throttled or not
 * authorised is NOT ESTABLISHED, left open, and any row whose items read (which
 * says what landed) went unanswered keeps its head and is left open. OUTER REQUEST REFUSED
 * is the whole $batch refused, and its text says why. ANSWERS NOT MATCHED, left
 * open, is a $batch whose answers cannot be matched to its parts: their count
 * differs from the parts sent, an AddValidate answer names other fields than
 * its part sent, more than one AddValidate answer carries no per-field list, or the three typed creates' answers cannot be paired with
 * their parts by the Title each names (one answer naming no Title is paired
 * with the one part left, and the evidence says so). FIELD REFUSED is a 2xx
 * AddValidate answer with HasException on the missing column. Any other
 * AddValidate row is WRITTEN when its part answered
 * 2xx with no field exception, its item exists, and the value it wrote reads back:
 * the person as this account's Id, the date as the same UTC instant as the one
 * sent. When the item exists but the value does not read back so, the claims row
 * is ACCEPTED, NOT STORED and the date row is ACCEPTED, STORED DIFFERENTLY, with
 * both values quoted; a date with no time is compared as a date and still heads
 * ACCEPTED, STORED DIFFERENTLY. A date and time with no zone heads STORED WITHOUT
 * A ZONE and is not compared, since the browser would read it in its own zone.
 * Any other answer is NOT ESTABLISHED, with the answer quoted, and the probe goes on.
 * Email addresses, claims logins and this account's display name are masked.
 * When no display name comes back, no text from an answer is quoted, only statuses.
 *
 * HOW TO RUN: F12 -> Console on a site you own, paste, Enter; it prints its
 * plan and stops. Set CONFIRMED and ALLOW_WRITES to true and paste again.
 * Copy the RESULTS block back verbatim.
 *
 * WHEN FINISHED: nothing to delete. The probe recycles its list before it
 * reports. Each title ends in a token unique to the run, so no run finds,
 * reuses or recycles another run's list; one a run could not recycle is
 * named on the console, with its Id, to recycle by hand.
 */
(async () => {
  // ---- Operator gate -------------------------------------------------
  // All default false. Pasting an unedited probe prints its plan and
  // stops; nothing touches the tenant until the operator opts in.
  const CONFIRMED = false;
  const ALLOW_WRITES = false;

  // CLEANUP deletes the probe's own list BEFORE the run, so every question
  // is answered by actually creating something rather than reporting
  // "already present" from a previous run, which is much weaker evidence.
  //
  // It is destructive and needs CONFIRMED and ALLOW_WRITES as well. It only
  // ever touches the explicitly named probe-owned list or lists; it never
  // enumerates or deletes anything else. Each list is RECYCLED, not purged,
  // so a mistake is recoverable from the site recycle bin.
  const CLEANUP = false;

  // No SITE_URL constant, deliberately. The probe reads the site it was
  // pasted into. A tenant URL committed to this repo has leaked twice, and
  // the field was the vector both times.
  const pageCtx = window._spPageContextInfo;
  if (!pageCtx) {
    console.error('[FATAL] No _spPageContextInfo. Paste this into a SharePoint page.');
    return;
  }
  const WEB = pageCtx.webAbsoluteUrl;

  const log = (level, msg) => console.log(`[${level}] ${msg}`);

  const getDigest = async () => {
    const res = await fetch(`${WEB}/_api/contextinfo`, {
      method: 'POST', headers: { Accept: 'application/json;odata=verbose' },
    });
    if (!res.ok) throw new Error(`contextinfo failed: HTTP ${res.status}`);
    const body = await res.json();
    return body.d.GetContextWebInformation.FormDigestValue;
  };

  const spGet = async (path) => {
    const res = await fetch(`${WEB}/_api/${path}`, {
      headers: { Accept: 'application/json;odata=nometadata' },
    });
    return { ok: res.ok, status: res.status, body: await res.json().catch(() => null) };
  };

  // NOTE the contract, because getting it wrong has produced false verdicts
  // here twice: `body` is the PARSED payload whether or not the request
  // succeeded. SharePoint answers a 403 or a 429 with a JSON error object,
  // so `body !== null` says the response was JSON, never that the call
  // worked. Anything asking "did I actually read this?" must test `ok`.
  const readFailed = (r) => !r.ok || r.body === null;

  // Was this request REFUSED (the server saying no to what was sent) or
  // did it merely fail? A negative control that cannot tell the difference
  // certifies the surface as observable on the strength of a throttle, and
  // every row it guards is then read as evidence.
  //
  // Defined by what it EXCLUDES, because the tempting definition is wrong
  // here. "400 means bad request" is the HTTP convention and it is not what
  // this tenant does: every SharePoint refusal this project has recorded
  // came back 500:
  //
  //   "To add an item to a document library, use SPFileCollection.Add()"
  //   "One or more column references are not allowed, because the columns
  //    are defined as a data type that is not supported in formulas"
  //   "The formula refers to a column that does not exist"
  //   "This field type does not support..."
  //
  // (analysis/checks/_structure.py, analysis/conditions.py, generators/
  // jsgen.py, each dated and cited to a live run). A 400-only test would
  // therefore have reported NOT ESTABLISHED for every negative control on a
  // tenant behaving exactly as recorded, which is the opposite failure and a
  // worse one: it would quietly retire the controls the stack's own evidence
  // rests on.
  //
  // So: 401/403 are about WHO is asking and 408/429 about the moment; those
  // are never refusals. Everything else non-2xx is treated as the server
  // rejecting the content, and the response TEXT is always printed beside
  // the verdict so a reader can see which it was.
  const isRefusal = (status) =>
    status >= 400 && status !== 401 && status !== 403
    && status !== 408 && status !== 429 && status !== 503; // 503: the other documented throttle

  // extraHeaders carries X-HTTP-Method for MERGE/DELETE: SharePoint tunnels
  // both through POST rather than accepting them as real verbs.
  const spPost = async (path, payload, digest, extraHeaders = {}) => {
    const res = await fetch(`${WEB}/_api/${path}`, {
      method: 'POST',
      headers: {
        Accept: 'application/json;odata=nometadata',
        'Content-Type': 'application/json;odata=nometadata',
        'X-RequestDigest': digest,
        ...extraHeaders,
      },
      body: JSON.stringify(payload),
    });
    // The interesting result is often the REFUSAL, so the response text is
    // returned rather than thrown: a 400 here is the finding, not a crash.
    const text = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(text); } catch { /* SharePoint sent plain text */ }
    return { ok: res.ok, status: res.status, body: parsed, text };
  };

  // ---- Pre-run reset --------------------------------------------------
  // Call this before bootstrapping. A no-op unless CLEANUP is on, so the
  // probe body reads the same either way.
  //
  // expectedId is OPTIONAL because most callers have no claimed Id to bracket
  // with, and the behaviour without one is unchanged. Supply one and every
  // request below addresses that list Id instead of the title, so a title
  // rebound mid-run cannot redirect the deletes or the recycle onto a list
  // this run never owned.
  //
  // DOCUMENTED: `web/lists(guid'<id>')` is the list resource, and `/items`
  // and `/items(<id>)` hang off it (Working with lists and list items with
  // REST, and the CSOM/REST API index, both checked 2026-09-23).
  // NOT DOCUMENTED: `/recycle` on the by-Id form appears on no Learn page.
  // It is the call this project has live evidence for with only the
  // addressing changed, and an unsupported URL fails visibly here rather
  // than losing somebody's list. One CLEANUP run settles it; see issue #611.
  const resetList = async (title, expectedId = null) => {
    if (!CLEANUP) return false;
    if (!ALLOW_WRITES) {
      log('INFO', `CLEANUP is on but ALLOW_WRITES is false, so '${title}' is not deleted.`);
      return false;
    }
    // An Id that is not a GUID would be spliced into a URL that addresses
    // something else, so it fails closed instead of being sent.
    const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (expectedId !== null && !GUID.test(String(expectedId))) {
      log('FAIL', `CLEANUP: '${expectedId}' is not a list Id, so nothing was deleted or `
                  + `recycled under '${title}'.`);
      return false;
    }
    const listPath = expectedId === null
      ? `web/lists/getbytitle('${title}')`
      : `web/lists(guid'${expectedId}')`;
    const found = await spGet(expectedId === null ? listPath : `${listPath}?$select=Id`);
    if (!found.ok) {
      log('INFO', `CLEANUP: no list named '${title}' to remove.`);
      return false;
    }
    // Addressing by Id still gets read back, because every destructive
    // request below rests on this one answer.
    const answeredId = found.body && found.body.Id
      ? String(found.body.Id).replace(/[{}]/g, '').toLowerCase() : null;
    if (expectedId !== null && answeredId !== String(expectedId).toLowerCase()) {
      log('FAIL', `CLEANUP: list ${expectedId} answered as ${answeredId}, so nothing was `
                  + `deleted or recycled under '${title}'.`);
      return false;
    }
    log('INFO', `CLEANUP: removing list '${title}' and its items.`);

    // Items first. Recycling the list takes them with it, but doing this
    // explicitly still clears the data if the list itself cannot be
    // removed. A locked or no-delete list would otherwise leave rows from
    // a previous run answering this run's questions.
    let digest = await getDigest();
    const items = await spGet(`${listPath}/items?$select=Id&$top=5000`);
    const rows = (items.ok && items.body && items.body.value) || [];
    for (const row of rows) {
      digest = await getDigest();
      await spPost(`${listPath}/items(${row.Id})`, {}, digest,
                   { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' });
    }
    if (rows.length) log('INFO', `CLEANUP: deleted ${rows.length} item(s).`);
    if (rows.length === 5000) {
      log('INFO', 'CLEANUP: hit the 5000-row page limit; re-run to clear the rest.');
    }

    digest = await getDigest();
    const gone = await spPost(`${listPath}/recycle`, {}, digest);
    // The Id is named where there is one, because a repair by hand off the
    // title would go to whatever the title resolves to now.
    const which = expectedId === null ? `'${title}'` : `'${title}' (list ${expectedId})`;
    if (gone.ok) {
      log('OK', `CLEANUP: recycled list ${which}. It is restorable from the recycle bin.`);
    } else {
      log('FAIL', `CLEANUP: could not recycle ${which}: HTTP ${gone.status} ${gone.text.slice(0, 200)}`);
    }
    return gone.ok;
  };

  // ---- Result table --------------------------------------------------
  // A probe answers questions. Outcome and EVIDENCE are recorded
  // separately so a run cannot be summarised as a verdict with nothing
  // behind it.
  //
  // Every question is REGISTERED UP FRONT as NOT ESTABLISHED, and record()
  // overwrites. Appending as you go looks equivalent and is not: a probe
  // that aborts early then reports only what it reached, and prints
  // "0 not established" while most of its questions were never asked.
  //
  // STATE carries the coarse answer alongside the prose, from the five-value
  // vocabulary in test/manual/SURFACES.md: settled, open, awaiting-capture,
  // void, needs-human. There are 83 distinct outcome heads across the
  // committed evidence, which is good prose and a bad enum, so a reader
  // downstream sorts on state and quotes outcome. record() takes an explicit
  // state and that always wins; the classifier below is the default for the
  // rows nobody has ruled on yet, and it reproduces exactly what report()
  // used to derive from the outcome head.
  //
  // ABORTED is open, not settled. It is the head a probe records when its
  // fixture never built, so the question it names was never asked; classifying
  // it settled printed "N answered, 0 open" for a run that measured nothing.
  const OPEN_HEADS = ['NOT ESTABLISHED', 'SHORT', 'ABORTED'];
  const AWAITING_CAPTURE_HEADS = ['MANUAL', 'NOT REACHED'];
  const stateFor = (outcome) => {
    if (AWAITING_CAPTURE_HEADS.some((p) => outcome.startsWith(p))) return 'awaiting-capture';
    if (OPEN_HEADS.some((p) => outcome.startsWith(p))) return 'open';
    return 'settled';
  };
  const RESULTS = [];
  const expect = (id, question) => {
    RESULTS.push({
      id, question, outcome: 'NOT ESTABLISHED',
      evidence: 'the run did not reach this question', state: 'open',
    });
  };
  const record = (id, question, outcome, evidence, state) => {
    const next = { question, outcome, evidence, state: state || stateFor(outcome) };
    const row = RESULTS.find((r) => r.id === id);
    if (row) {
      Object.assign(row, next);
    } else {
      RESULTS.push({ id, ...next });
    }
    const level = outcome === 'PASS' ? 'OK' : outcome === 'FAIL' ? 'FAIL' : 'INFO';
    log(level, `${id}: ${outcome}. ${question}`);
    if (evidence) console.log(`      evidence: ${evidence}`);
  };

  // ---- Fixtures (#559) -----------------------------------------------
  // Why a response carries no reading, or null when it does. Learn documents
  // 429 and 503 as the two SharePoint Online throttle statuses.
  const unanswered = (r) => {
    if (r.ok) {
      return r.body !== null && typeof r.body === 'object'
        ? null : `answered HTTP ${r.status} with no payload`;
    }
    if (r.status === 429 || r.status === 503) return `was throttled (HTTP ${r.status})`;
    if (r.status === 408) return 'timed out (HTTP 408)';
    if (r.status === 401 || r.status === 403) return `was not authorised (HTTP ${r.status})`;
    return isRefusal(r.status) ? `was refused (HTTP ${r.status})` : `did not answer (HTTP ${r.status})`;
  };

  // A voided row keeps its question and is counted apart from open and answered.
  const voidDependents = (ids, reason) => {
    for (const id of ids) {
      const row = RESULTS.find((r) => r.id === id);
      record(id, row ? row.question : id, 'NOT ESTABLISHED', reason, 'void');
    }
  };

  // `read` resolves to a harness response ({ ok, status, body }). `declared`
  // maps each property the measurement depends on to a value or a predicate.
  // PASS needs every one read back; otherwise FAIL, void `dependents`, false.
  const establishFixture = async (id, read, declared, dependents) => {
    const row = RESULTS.find((r) => r.id === id);
    const question = row ? row.question : id;
    const problems = [];
    const seen = [];
    let got = null;
    let threw = false;
    try {
      got = await read();
    } catch (err) {
      threw = true;
      problems.push(`the read threw: ${err && err.message ? err.message : String(err)}`);
    }
    if (!threw) {
      const silent = got && typeof got === 'object' ? unanswered(got) : 'returned no response';
      if (silent) problems.push(`the read ${silent}`);
    }
    if (!problems.length) {
      for (const [name, want] of Object.entries(declared)) {
        if (!Object.prototype.hasOwnProperty.call(got.body, name) || got.body[name] === undefined) {
          problems.push(`${name} is absent from the payload`);
          continue;
        }
        const value = got.body[name];
        seen.push(`${name}=${JSON.stringify(value)}`);
        const held = typeof want === 'function' ? want(value) === true : value === want;
        if (!held) {
          problems.push(`${name} differs: read ${JSON.stringify(value)}, declared `
            + (typeof want === 'function' ? 'by a predicate it fails' : JSON.stringify(want)));
        }
      }
    }
    if (!problems.length) {
      record(id, question, 'PASS', `read back ${seen.join(', ')}`);
      return true;
    }
    record(id, question, 'FAIL', problems.join('; ') + (seen.length ? `; read ${seen.join(', ')}` : ''));
    voidDependents(dependents, `the fixture ${id} did not hold: ${problems.join('; ')}`);
    return false;
  };

  const report = () => {
    console.log('\n==================== RESULTS ====================');
    for (const r of RESULTS) {
      console.log(`${r.id.padEnd(6)} ${r.state.padEnd(16)} ${r.outcome.padEnd(16)} ${r.question}`);
      if (r.evidence) console.log(`       ${r.evidence}`);
    }
    console.log('=================================================');
    // Counted off state rather than off the outcome head, so the summary and
    // the per-row state can never disagree. awaiting-capture stays open until
    // a person records the observation. void does NOT: the control row names a
    // reason this identity can never answer, so counting it open reports work
    // that no re-run can clear, and counting it answered claims a measurement
    // nobody made. It gets its own number.
    const voided = RESULTS.filter((r) => r.state === 'void').length;
    const open = RESULTS.filter((r) => r.state !== 'settled' && r.state !== 'void').length;
    const waiting = RESULTS.filter((r) => r.state === 'awaiting-capture').length;
    const answered = RESULTS.length - open - voided;
    console.log(`${RESULTS.length} question(s); ${answered} answered, ${open} open, ${voided} voided.`);
    if (waiting) {
      console.log(`${waiting} of those are waiting on an observation somebody has to make.`);
    }
    if (open) {
      console.log('A question with no observation is NOT a pass. Report it as open.');
    }
    console.log('Copy this whole block back verbatim.');
  };
  // ---- Raw requests (v1) ----------------------------------------------
  // The text is kept whole, since a refusal is often not JSON and its text is the finding.
  const sendRaw = async (path, options = {}) => {
    const method = options.method || 'GET';
    const accept = options.accept || 'application/json;odata=nometadata';
    let res;
    try {
      res = await fetch(`${WEB}/_api/${path}`, {
        method,
        headers: { Accept: accept, ...(options.headers || {}) },
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
      });
    } catch (err) {
      // A request that never answered is a row with no status, so the table still prints.
      return { ok: false, status: null, parsed: null, date: null,
        text: `no response: ${err && err.message ? err.message : String(err)}` };
    }
    const text = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(text); } catch { /* not JSON; the text is kept */ }
    const date = res.headers && typeof res.headers.get === 'function' ? res.headers.get('date') : null;
    return { ok: res.ok, status: res.status, text, parsed, date };
  };

  // An error message can quote the request URL, and evidence must not name the tenant.
  const TENANT_ORIGIN = (() => {
    const scheme = WEB.indexOf('//');
    const slash = scheme === -1 ? -1 : WEB.indexOf('/', scheme + 2);
    return slash === -1 ? WEB : WEB.slice(0, slash);
  })();
  // A JSON body can escape the origin's slashes, and a host can appear with no scheme at all.
  const TENANT_PATTERN = (() => {
    const scheme = TENANT_ORIGIN.indexOf('//');
    const host = scheme === -1 ? '' : TENANT_ORIGIN.slice(scheme + 2);
    const needles = [TENANT_ORIGIN, TENANT_ORIGIN.replace(/\//g, '\\/'), host].filter((n) => n);
    const literal = (n) => n.replace(/[.*+?^$()|[\]\\{}]/g, '\\$&');
    return needles.length ? new RegExp(needles.map(literal).join('|'), 'gi') : null;
  })();
  const redactTenant = (value) => {
    const text = String(value);
    return TENANT_PATTERN ? text.replace(TENANT_PATTERN, '[TENANT]') : text;
  };

  // The head a non-2xx or unanswered request earns, or null when its payload decides.
  const rawHead = (res) => {
    if (res.status === null) return { outcome: 'NOT ESTABLISHED', why: redactTenant(res.text) };
    if (res.ok) return null;
    const said = redactTenant(res.text).slice(0, 400);
    if (isRefusal(res.status)) return { outcome: 'REFUSED', why: `HTTP ${res.status}: ${said}` };
    const reason = unanswered({ ok: false, status: res.status, body: res.parsed });
    return { outcome: 'NOT ESTABLISHED', why: `the request ${reason}: ${said}` };
  };

  // contextinfo wraps its answer in d under odata=verbose and not under nometadata.
  const issueDigest = async () => {
    const res = await sendRaw('contextinfo', { method: 'POST', accept: 'application/json;odata=verbose' });
    const parsed = res.parsed && typeof res.parsed === 'object' ? res.parsed : null;
    const info = parsed && parsed.d ? parsed.d.GetContextWebInformation : parsed;
    const digest = res.ok && info && typeof info.FormDigestValue === 'string'
      ? info.FormDigestValue : null;
    return { res, digest };
  };
  // ---- Identity masking (v1) ------------------------------------------
  // Strings that name a person, masked wherever evidence quotes an answer.
  const IDENTITIES = [];
  // `whole` masks the value only where no letter, digit or underscore adjoins it, as a display name needs.
  const knowIdentity = (value, mask, whole = false) => {
    const text = value === null || value === undefined ? '' : String(value);
    if (text.length < 2) return;
    IDENTITIES.push({ text, mask, whole });
    // An answer's JSON may spell a non-ASCII letter as a \u escape, so that spelling is masked too.
    const escaped = text.replace(/[^\x20-\x7e]/g, (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, '0')}`);
    if (escaped !== text) IDENTITIES.push({ text: escaped, mask, whole });
    IDENTITIES.sort((a, b) => b.text.length - a.text.length);
  };
  const literal = (text) => text.replace(/[.*+?^$()|[\]\\{}]/g, '\\$&');
  const pattern = ({ text, whole }) => (whole
    ? new RegExp(`(?<![\\p{L}\\p{N}_])${literal(text)}(?![\\p{L}\\p{N}_])`, 'giu')
    : new RegExp(literal(text), 'gi'));
  // Logins and emails go first, even ones never learned, so a display name inside one cannot break it up.
  // A login's value runs through apostrophes and a backslash before a letter or digit (a Windows claim's
  // domain\user, escaped or not), and stops at a backslash before anything else, so JSON escapes survive.
  // An address's local part is RFC 5322's atext and dots, with any letter or digit (RFC 6531).
  const scrub = (value) => {
    let out = redactTenant(value)
      .replace(/(i:0[^|\s'"]*\|([^|\s'"]+\|)?)(?:[^\s"|\\]|\\+(?=[\p{L}\p{N}]))+/giu, '$1<account>')
      .replace(/[\p{L}\p{N}!#$%&'*+/=?^_`{|}~.-]+@[^\s'"<>\\]+/giu, '<account>');
    for (const known of IDENTITIES) out = out.replace(pattern(known), known.mask);
    return out;
  };
  // The one switch: set once this account's display name is not learned, since no mask can then be complete.
  let withheld = false;
  const WITHHELD = '(text withheld: this account\'s display name was not learned)';
  // Text from an answer, masked, or withheld once masking cannot be complete.
  const quote = (text) => (withheld ? WITHHELD : scrub(text));
  // Every answer's text once text is withheld, so a fixture can tell a value read from one from its own.
  const ANSWERS = [];
  // A value from an answer as JSON; one holding any text is withheld with it, since a number names nobody.
  const quoteValue = (value) => {
    const json = JSON.stringify(value);
    return withheld && typeof json === 'string' && json.includes('"') ? WITHHELD : scrub(json);
  };
  // Every answer maskedHead found unanswered or refused, so a fixture can tell an unanswered request, which
  // leaves it open, from a refusal, which is settled.
  const UNHEARD = [];
  const REFUSED = [];
  // Set by an unanswered write and cleared by beginFixture, since an absence after one may be that write unlanded.
  let writeUnheard = false;
  // An answer that a thing is not there: a 404, or the absent-field 400 that rollback.js.j2 also accepts.
  const absenceOf = (status, parsed) => {
    const error = parsed && typeof parsed === 'object' ? parsed['odata.error'] || parsed.error : null;
    const code = String((error && error.code) || '');
    return status === 404 || (status === 400 && code.includes('-2147024809')
      && code.includes('System.ArgumentException'));
  };
  // rawHead cuts a response's text short, so the text is masked first and a cut never splits a name unmasked.
  const maskedHead = (res, write = false) => {
    // A request that never answered carries its error, not an answer, in its text.
    const head = rawHead({ ...res, text: res.status === null ? scrub(res.text) : quote(res.text) });
    if (withheld && res.status !== null) ANSWERS.push(String(res.text));
    if (head && head.outcome === 'NOT ESTABLISHED') {
      UNHEARD.push(head.why);
      if (write) writeUnheard = true;
    } else if (head && head.outcome === 'REFUSED') {
      if (write || !writeUnheard || !absenceOf(res.status, res.parsed !== undefined ? res.parsed : res.body)) {
        REFUSED.push(head.why);
      } else UNHEARD.push(`${head.why}, after a write that went unanswered`);
    }
    return head;
  };
  // A single-entity read's body when it is a JSON object, or null, so no property is read off anything else.
  const recordBody = (res) => (res.parsed && typeof res.parsed === 'object' && !Array.isArray(res.parsed)
    ? res.parsed : null);
  // A read answered 2xx with no JSON object has nothing to read, which the harness's unanswered counts as none.
  const readHead = (res) => {
    const head = maskedHead(res);
    if (!head && recordBody(res) === null) UNHEARD.push(`the read answered HTTP ${res.status} with no JSON object`);
    return head;
  };
  // Reads this account before any mask for its display name exists, so nothing of a failed answer is quoted,
  // and withholds every later answer's text when no display name of two or more characters comes back.
  const readAccount = async () => {
    const res = await sendRaw('web/currentuser?$select=Id,Email,LoginName,Title');
    const account = res.ok ? recordBody(res) : null;
    const said = res.status === null ? 'the account read never answered'
      : `the account read answered HTTP ${res.status}${res.ok && !account ? ' with no JSON object' : ''}`;
    if (!account && (res.status === null || res.ok || !isRefusal(res.status))) UNHEARD.push(said);
    if (account) {
      knowIdentity(account.Email, '<account>');
      knowIdentity(account.LoginName, '<account>');
      knowIdentity(account.Title, '<name>', true);
    }
    const named = account && typeof account.Title === 'string' && account.Title.length >= 2;
    if (!named) {
      withheld = true;
      log('INFO', `this account's display name was not learned (${account ? 'no display name to mask came back'
        : said}), so no text from an answer is quoted for the rest of this run; statuses still are.`);
    }
    return { account, said: account ? `HTTP ${res.status}` : said };
  };
  // For a probe with no current-user fixture: learns this account so its display name is masked too.
  const learnIdentity = async () => {
    await readAccount();
  };
  // ---- Scratch lists (v1) ---------------------------------------------
  // Lists this run created, by title and Id, so the recycle touches those and never a list it only found.
  const CREATED_LISTS = [];
  // A token drawn once per run and ending every scratch title, so no run finds, reuses or recycles another's list.
  const RUN = Math.random().toString(36).slice(2, 10);
  const runTitle = (base) => `${base} ${RUN}`;
  // A list Id as a bare lower-case GUID, or null when the value is not one.
  const guidOf = (value) => {
    const bare = value === null || value === undefined ? '' : String(value).replace(/[{}]/g, '').toLowerCase();
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(bare) ? bare : null;
  };
  // Whether two arrays hold the same elements as often each, compared by ===, never by a serialised form.
  const sameElements = (a, b) => Array.isArray(a) && Array.isArray(b) && a.length === b.length
    && a.every((x) => a.filter((y) => y === x).length === b.filter((y) => y === x).length);
  // A title or server-relative path inside an OData string literal, its apostrophes doubled as deploy/_folders does.
  const pathLiteral = (path) => String(path).replace(/'/g, "''");
  // A 2xx body's value array when every entry is a JSON object; otherwise rows is null and shape says why.
  const entriesOf = (parsed) => {
    if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.value)) {
      return { rows: null, shape: 'carried no value array' };
    }
    const bad = parsed.value.findIndex((row) => !row || typeof row !== 'object' || Array.isArray(row));
    return bad === -1 ? { rows: parsed.value, shape: null } : { rows: null, shape: `carried entry ${bad + 1} `
      + `of its value array as ${quoteValue(parsed.value[bad]).slice(0, 80)}, not an object` };
  };
  // A continuation link in the three spellings the search-discovery probe reads plus a bare __next, or null.
  const continuationOf = (parsed) => {
    if (!parsed || typeof parsed !== 'object') return null;
    const link = parsed['odata.nextLink'] || parsed['@odata.nextLink'] || parsed.__next
      || (parsed.d && typeof parsed.d === 'object' ? parsed.d.__next : undefined);
    return typeof link === 'string' && link ? link : null;
  };
  // voidDependents, except that a row already void keeps its first reason: void is terminal.
  const voidRows = (ids, reason) => voidDependents(ids.filter((one) => {
    const row = RESULTS.find((r) => r.id === one);
    return !row || row.state !== 'void';
  }), reason);
  // The numeric Id a 2xx create answered, or null; a 2xx with no JSON object is noted as unanswered.
  const createdId = (made) => {
    if (!made.ok) return null;
    const body = recordBody({ parsed: made.body });
    if (body === null) UNHEARD.push(`the create answered HTTP ${made.status} with no JSON object`);
    return body && Number.isInteger(body.Id) ? body.Id : null;
  };
  // Where the requests of the fixture about to be established begin in UNHEARD.
  let fixtureStart = 0;
  let refusedStart = 0;
  const beginFixture = () => {
    fixtureStart = UNHEARD.length;
    refusedStart = REFUSED.length;
    writeUnheard = false;
  };
  // A write's answer is noted, so a fixture can tell an unanswered write from a refused one.
  const spWrite = async (...args) => {
    const res = await spPost(...args);
    maskedHead(res, true);
    return res;
  };
  // establishFixture, except that a fixture any of whose requests since beginFixture went unanswered is left
  // open with its dependents, since an unanswered request says nothing about the fixture.
  const settleFixture = async (id, read, declared, dependents) => {
    const start = fixtureStart;
    const refusedFrom = refusedStart;
    // Rows an earlier fixture voided are put back as they were, since establishFixture voids them again.
    const earlier = RESULTS.filter((r) => dependents.includes(r.id) && r.state === 'void').map((r) => ({ ...r }));
    // The harness prints every value it reads, so once text is withheld a declared value holding text found in
    // an answer is judged here and handed on as a verdict; one equal to its declared literal stays.
    const HELD = '(text withheld; it held)';
    const textsOf = (v) => (typeof v === 'string' ? [v]
      : v && typeof v === 'object' ? Object.values(v).flatMap(textsOf) : []);
    const answered = (value) => textsOf(value).some((s) => s.length > 0
      && ANSWERS.some((a) => a.includes(s) || a.includes(JSON.stringify(s).slice(1, -1))));
    const judged = (body) => (!withheld || !body || typeof body !== 'object' ? body
      : Object.fromEntries(Object.entries(body).map(([name, value]) => {
        const want = declared[name];
        if (want === undefined || value === want || !answered(value)) return [name, value];
        return [name, typeof want === 'function' && want(value) === true ? HELD : WITHHELD];
      })));
    const verdicts = Object.fromEntries(Object.entries(declared).map(([name, want]) => [name,
      typeof want === 'function' ? (v) => v === HELD || (v !== WITHHELD && want(v)) : want]));
    // A read that throws never answered, so it counts as unanswered like a throttle.
    const heard = async () => {
      try {
        const got = await read();
        return got && typeof got === 'object' ? { ...got, body: judged(got.body) } : got;
      } catch (err) {
        UNHEARD.push(`the read never answered (${scrub(String((err && err.message) || err)).slice(0, 200)})`);
        throw err;
      }
    };
    const held = await establishFixture(id, heard, verdicts, dependents);
    const restore = () => earlier.forEach((was) => Object.assign(RESULTS.find((r) => r.id === was.id), was));
    if (held) return true;
    // A refusal is a settled answer, so it keeps the FAIL even beside a request that went unanswered.
    if (UNHEARD.length === start || REFUSED.length > refusedFrom) {
      restore();
      return false;
    }
    const why = `${[...new Set(UNHEARD.slice(start))].join('; ')}; a re-run can ask it`;
    const row = RESULTS.find((r) => r.id === id);
    record(id, row ? row.question : id, 'NOT ESTABLISHED', why);
    for (const one of dependents) {
      if (earlier.some((was) => was.id === one)) continue;
      const dependent = RESULTS.find((r) => r.id === one);
      record(one, dependent ? dependent.question : one, 'NOT ESTABLISHED', `not asked: ${why}`);
    }
    restore();
    return false;
  };
  // __metadata is verbose OData, so every write carrying it declares the verbose content type.
  const VERBOSE_WRITE = { 'Content-Type': 'application/json;odata=verbose' };
  // A list read by its Id after a recycle: gone true, false, or null with the reason it cannot say.
  const listGone = async (listId) => {
    let res;
    try {
      res = await spGet(`web/lists(guid'${listId}')?$select=Id`);
    } catch (err) {
      return { gone: null, why: `the read-back never answered (${scrub(String((err && err.message) || err))})` };
    }
    if (res.ok) return { gone: false, why: `it still reads back by its Id (HTTP ${res.status})` };
    if (absenceOf(res.status, res.body)) return { gone: true, why: null };
    return { gone: null, why: `the read-back that would confirm it ${unanswered(res)}` };
  };
  // Recycles one list by its Id and logs OK only once a by-Id read shows it gone; gone is as listGone's.
  const recycleList = async (title, listId) => {
    let sent;
    try {
      sent = await spPost(`web/lists(guid'${listId}')/recycle`, {}, await getDigest());
    } catch (err) {
      sent = { ok: false, status: null, text: String((err && err.message) || err) };
    }
    // A request that threw has no status, so its message is what the operator is shown.
    const why = sent.status === null ? scrub(sent.text).slice(0, 240) : `HTTP ${sent.status}`;
    if (!sent.ok) {
      log('FAIL', `could not recycle '${title}' (list ${listId}, ${why}); recycle it by hand.`);
      return { gone: false, why: `its recycle was not answered 2xx (${why})` };
    }
    const after = await listGone(listId);
    log(after.gone ? 'OK' : 'FAIL', after.gone
      ? `recycled '${title}' (list ${listId}); it is restorable from the recycle bin.`
      : `the recycle of '${title}' (list ${listId}) answered ${why}, but ${after.why}; `
        + 'check it and recycle it by hand.');
    return { gone: after.gone, why: after.gone ? null : `its recycle answered ${why}, but ${after.why}` };
  };

  // Creates a list or library (generic unless `baseTemplate` says otherwise) owned by `description`, then reads it back.
  const claimScratchList = async ({ id, question, title, description, dependents,
    settings = null, declared = {}, baseTemplate = 100 }) => {
    const path = `web/lists/getbytitle('${pathLiteral(title)}')`;
    // An answer that settles nothing leaves the fixture and its dependents open for a re-run.
    const leaveOpen = (why) => {
      record(id, question, 'NOT ESTABLISHED', `${why}; a re-run can ask it`);
      for (const one of dependents) {
        const row = RESULTS.find((r) => r.id === one);
        // A row an earlier fixture voided keeps its reason.
        if (row && row.state === 'void') continue;
        record(one, row ? row.question : one, 'NOT ESTABLISHED', `not asked: ${why}; a re-run can ask it`);
      }
      return { held: false, merge: null, body: null };
    };
    const pre = await spGet(`${path}?$select=Id,Description`);
    // A 2xx with no JSON says nothing about whose list it is, so it is neither refused nor built over.
    if (pre.ok && recordBody({ parsed: pre.body }) === null) {
      return leaveOpen(`the ownership read of '${title}' answered HTTP ${pre.status} with no JSON; `
        + 'nothing was created');
    }
    if (pre.ok) {
      // A title ending in this run's token names no list before this run makes one, so a list found here is
      // not this run's, whatever its description, and is never recycled or built over.
      record(id, question, 'FAIL', `a list named '${title}' already exists`
        + `${pre.body.Description === description ? ' with this probe\'s description' : ''}; refusing to modify it`);
      voidRows(dependents, 'the scratch list is not one this run created');
      return { held: false, merge: null, body: null };
    } else if (isRefusal(pre.status) && pre.status !== 404) {
      // A refused ownership read is an answer, so nothing is created and the claim fails with its reason.
      record(id, question, 'FAIL', `the ownership read of '${title}' was refused (HTTP ${pre.status})`
        + `${pre.body ? `: ${quoteValue(pre.body).slice(0, 200)}` : ''}; nothing was created`);
      voidRows(dependents, 'the scratch list was not created');
      return { held: false, merge: null, body: null };
    } else if (pre.status !== 404) {
      // A by-title read answers an absent list 404 (the live finding rollback.js.j2 cites); anything else is unknown.
      return leaveOpen(`the ownership read of '${title}' ${unanswered(pre)}`
        + `${pre.body ? `: ${quoteValue(pre.body).slice(0, 200)}` : ''}; nothing was created`);
    }
    const digest = await getDigest();
    let made;
    try {
      made = await spPost('web/lists', { Title: title, BaseTemplate: baseTemplate, Description: description },
        digest);
    } catch (err) {
      // The create may have reached the server, so the title is kept for the recycle line to name.
      CREATED_LISTS.push({ title, id: null });
      return leaveOpen(`the list create never answered (${scrub(String((err && err.message) || err))}), so a `
        + `list '${title}' may now exist`);
    }
    if (!made.ok && isRefusal(made.status)) {
      // A refused create may still have made the list, so its title is read back before it is let go.
      let back;
      try {
        back = await spGet(`${path}?$select=Id,Description`);
      } catch (err) {
        back = { ok: false, status: null, why: `never answered (${scrub(String((err && err.message) || err))})` };
      }
      const found = back.ok ? recordBody({ parsed: back.body }) : null;
      const landedId = found && found.Description === description ? guidOf(found.Id) : null;
      if (landedId !== null) CREATED_LISTS.push({ title, id: landedId });
      else if (back.status !== 404) CREATED_LISTS.push({ title, id: null });
      const unknown = back.why || (!back.ok ? unanswered(back) : found === null
        ? `answered HTTP ${back.status} with no JSON object` : 'found it with another description');
      const landing = landedId !== null ? `, but a list '${title}' with this probe's description reads back `
        + `(list ${landedId}), so it is recycled` : back.status === 404 ? `; no list holds '${title}'`
        : `; whether a list '${title}' landed is unknown (the read-back ${unknown}), so check it by hand`;
      record(id, question, 'FAIL',
        `the list create answered HTTP ${made.status}: ${quote(made.text).slice(0, 300)}${landing}`);
      voidRows(dependents, 'the scratch list was not created');
      return { held: false, merge: null, body: null };
    }
    if (!made.ok) {
      // Throttled, unauthorised or unavailable is no answer, and the list may exist, so the title is kept.
      CREATED_LISTS.push({ title, id: null });
      return leaveOpen(`the list create ${unanswered({ ok: false, status: made.status })}: `
        + `${quote(made.text).slice(0, 200)}, so a list '${title}' may now exist`);
    }
    if (recordBody({ parsed: made.body }) === null) {
      CREATED_LISTS.push({ title, id: null });
      return leaveOpen(`the list create answered HTTP ${made.status} with no JSON object, so a list '${title}' `
        + 'may now exist');
    }
    const created = { title, id: guidOf(made.body.Id) };
    // Two creates answering one Id would send both lists' writes to one list, so the second is not built on.
    if (created.id !== null && CREATED_LISTS.some((one) => one.id === created.id)) {
      log('FAIL', `'${title}' answered list ${created.id}, which another list this run created holds; `
        + `recycle '${title}' by hand.`);
      record(id, question, 'FAIL', `the list create answered HTTP ${made.status} with the Id of another list `
        + `this run created (${created.id}), so nothing was written to it; recycle it by hand`);
      voidRows(dependents, 'the scratch list answered the Id of another list this run created');
      return { held: false, merge: null, body: null };
    }
    // Without the create's own Id a title read could name a rebound list, so nothing more is written.
    if (created.id === null) {
      CREATED_LISTS.push(created);
      record(id, question, 'FAIL', `the list create answered HTTP ${made.status} with no list Id, so nothing `
        + `ties '${title}' to the list it made; nothing was written to it`);
      voidRows(dependents, 'the scratch list answered no Id to address it by');
      return { held: false, merge: null, body: null };
    }
    // The answered Id is written to or recycled only once it reads back this run's title and this probe's
    // Description, since a wrong Id would point both at a list this run did not make.
    let mine;
    try {
      mine = await spGet(`web/lists(guid'${created.id}')?$select=Id,Title,Description`);
    } catch (err) {
      mine = { ok: false, status: null, why: `never answered (${scrub(String((err && err.message) || err))})` };
    }
    const own = mine.ok ? recordBody({ parsed: mine.body }) : null;
    const proved = own !== null && own.Title === title && own.Description === description
      && guidOf(own.Id) === created.id;
    if (!proved) {
      const said = mine.why || (own !== null ? `reads back Title ${quoteValue(own.Title)} and `
        + `${own.Description === description ? 'this probe\'s Description' : 'another Description'}, not '${title}' `
        + 'with this probe\'s' : mine.ok ? `answered HTTP ${mine.status} with no JSON object`
        : absenceOf(mine.status, mine.body) ? 'answered that no list holds it' : unanswered(mine));
      const why = own !== null ? `list ${created.id} ${said}` : `the read of list ${created.id} ${said}`;
      // Named for a check by hand, never recycled by an Id this run did not prove its own.
      CREATED_LISTS.push({ title, id: null, why: `answered list ${created.id}, which did not read back as this `
        + 'run\'s list' });
      // A contradicting read or a refusal settles it; a read that said nothing leaves it open.
      if (own === null && (mine.why || mine.ok || !isRefusal(mine.status))) {
        return leaveOpen(`${why}, so nothing was written to it`);
      }
      record(id, question, 'FAIL', `${why}; nothing was written to it`);
      voidRows(dependents, 'the scratch list did not read back as this run\'s');
      return { held: false, merge: null, body: null };
    }
    CREATED_LISTS.push(created);
    let merge = null;
    beginFixture();
    if (settings !== null) {
      // Sent by Id, so a title rebound cannot take this list's settings.
      merge = await spWrite(`web/lists(guid'${created.id}')`, { __metadata: { type: 'SP.List' }, ...settings },
        await getDigest(), { ...VERBOSE_WRITE, 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });
      log('INFO', `list settings MERGE on '${title}': HTTP ${merge.status}`
        + `${merge.ok ? '' : ` ${quote(merge.text).slice(0, 200)}`}`);
    }
    const select = [...new Set(['Id', 'BaseTemplate', 'Description', ...Object.keys(declared)])].join(',');
    // The MERGE's answer joins the read-back, so a refused setting shows its reason in RESULTS.
    const answered = merge === null ? {} : { Settings: `HTTP ${merge.status}`
      + `${merge.ok ? '' : `: ${quote(merge.text).slice(0, 200)}`}` };
    // Recorded, never judged: what the MERGE answered is an observation, and the read-back decides.
    const settled = merge === null ? {} : { Settings: (v) => typeof v === 'string' };
    let read = null;
    const held = await settleFixture(id, async () => {
      read = await spGet(`${path}?$select=${select}`);
      readHead({ ...read, parsed: read.body, text: JSON.stringify(read.body) });
      // A body that is not a JSON object is no answer; the harness would read a property off it.
      if (read.ok && recordBody({ parsed: read.body }) === null) read = { ...read, body: null };
      return read.ok && read.body && typeof read.body === 'object'
        ? { ...read, body: { ...read.body, ...answered } } : read;
    }, { BaseTemplate: baseTemplate, Description: description, ...declared, ...settled,
      // The title must still name the list this run created, so every write after it reaches that list.
      Id: (v) => guidOf(v) !== null && guidOf(v) === created.id }, dependents);
    // The read-back is handed on, so a caller uses the values the fixture certified, and writes by its Id.
    return { held, merge, body: held ? read.body : null, path: held ? `web/lists(guid'${created.id}')` : null };
  };

  // Recycles every list this run created by its Id, newest first, and says which one to recycle by hand.
  const recycleScratchLists = async () => {
    for (const { title, id, why } of [...CREATED_LISTS].reverse()) {
      if (id === null) {
        log('FAIL', `'${title}' ${why || 'never answered a list Id'}, so it was not recycled; if it stands, `
          + 'recycle it by hand.');
        continue;
      }
      // By Id, so a title rebound cannot redirect it.
      await recycleList(title, id);
    }
  };
  log('INFO', 'probe revision ffea73da. Quote this when reporting results.');

  // The parts name the list by title, the form a history write sends and these rows measure; the run's token
  // means no other list holds it, and none can take it between a check and a use.
  const LIST = runTitle('dbmlsp Probe BatchItems');
  // The Description marks the list as this probe's for anyone recycling it by hand, and the read-back checks it.
  const OWNERSHIP = 'dbml-sharepoint batch-item-create probe scratch list. Safe to delete.';
  // A part's request line carries the title quoted then URL-encoded, as a history write sends it.
  const partPath = `web/lists/getbytitle('${encodeURIComponent(pathLiteral(LIST))}')`;
  const MISSING = 'dbmlspNoSuchColumn';
  const WHO = 'ProbeWho';
  const WHEN = 'ProbeWhen';
  const STAMP = '2026-01-15T09:30:00Z';
  const NOMETADATA = 'application/json;odata=nometadata';
  const TITLES = {
    single: 'dbmlsp batch single', unknown: 'dbmlsp batch single missing column',
    a: 'dbmlsp batch part A', b: 'dbmlsp batch part B', c: 'dbmlsp batch part C',
    verbose: 'dbmlsp batch untyped verbose', nometadata: 'dbmlsp batch untyped nometadata',
    addvalidate: 'dbmlsp addvalidate single', avunknown: 'dbmlsp addvalidate single missing column',
    avfailed: 'dbmlsp addvalidate part missing column', folder: 'dbmlsp addvalidate no folder',
    claims: 'dbmlsp addvalidate claims', iso: 'dbmlsp addvalidate iso date',
  };

  const Q = {
    list: 'a generic list this probe created, whose ListItemEntityTypeFullName reads back',
    single: 'CONTROL: one single typed item create lands and its Title reads back',
    unknown: `CONTROL: a single typed create naming ${MISSING}, which the list lacks, is refused and its Title `
      + 'is absent from the items read',
    parts: 'three typed creates in one ChangeSet, the middle one naming the missing column: what each part answered',
    failed: 'what the middle part answered, and whether its neighbours landed',
    verbose: 'what a create part with verbose headers and no __metadata answered',
    nometadata: 'what a create part with nometadata headers and no type answered',
    columns: `${WHO} (User) and ${WHEN} (DateTime, DisplayFormat 1) read back with their TypeAsString`,
    user: 'this account\'s Id and Email read back from web/currentuser',
    addvalidate: 'CONTROL: one AddValidateUpdateItemUsingPath call with FolderPath and a Title lands',
    avunknown: `CONTROL: one AddValidateUpdateItemUsingPath call naming ${MISSING} in formValues is refused and `
      + 'its Title is absent from the items read',
    avfailed: `what an AddValidateUpdateItemUsingPath part naming ${MISSING} answered, and whether its neighbours landed`,
    folder: 'what an AddValidateUpdateItemUsingPath part with no listItemCreateInfo.FolderPath answered',
    claims: `what an AddValidateUpdateItemUsingPath part writing ${WHO} as claims in formValues answered`,
    iso: `what an AddValidateUpdateItemUsingPath part writing ${WHEN} as ISO 8601 text in formValues answered`,
  };
  expect('transport.batch.fixture-item-batch-list', Q.list);
  expect('transport.batch.control-single-item-create', Q.single);
  expect('transport.batch.control-single-item-unknown-property-refused', Q.unknown);
  expect('transport.batch.changeset-item-creates-per-part', Q.parts);
  expect('transport.batch.changeset-item-create-failed-part', Q.failed);
  expect('transport.batch.changeset-item-create-untyped-verbose', Q.verbose);
  expect('transport.batch.changeset-item-create-untyped-nometadata', Q.nometadata);
  expect('transport.batch.fixture-item-batch-columns', Q.columns);
  expect('transport.batch.control-current-user', Q.user);
  expect('transport.batch.control-single-addvalidate-create', Q.addvalidate);
  expect('transport.batch.control-single-addvalidate-unknown-field-refused', Q.avunknown);
  expect('transport.batch.changeset-addvalidate-failed-part', Q.avfailed);
  expect('transport.batch.changeset-addvalidate-folderpath-omitted', Q.folder);
  expect('transport.batch.changeset-addvalidate-person-claims', Q.claims);
  expect('transport.batch.changeset-addvalidate-date-iso', Q.iso);

  const SINGLE = 'transport.batch.control-single-item-create';
  const UNKNOWN = 'transport.batch.control-single-item-unknown-property-refused';
  const OBSERVED = ['transport.batch.changeset-item-creates-per-part',
    'transport.batch.changeset-item-create-failed-part',
    'transport.batch.changeset-item-create-untyped-verbose',
    'transport.batch.changeset-item-create-untyped-nometadata'];
  const COLUMNS = 'transport.batch.fixture-item-batch-columns';
  const USER = 'transport.batch.control-current-user';
  const ADDVALIDATE = 'transport.batch.control-single-addvalidate-create';
  const AV_UNKNOWN = 'transport.batch.control-single-addvalidate-unknown-field-refused';
  const AV_FAILED = 'transport.batch.changeset-addvalidate-failed-part';
  const FOLDER = 'transport.batch.changeset-addvalidate-folderpath-omitted';
  const CLAIMS = 'transport.batch.changeset-addvalidate-person-claims';
  const ISO = 'transport.batch.changeset-addvalidate-date-iso';
  // Every row resting on the AddValidate control, asked or not, as the catalogue declares them.
  const AFTER_ADDVALIDATE = [AV_UNKNOWN, AV_FAILED, FOLDER, CLAIMS, ISO];
  const AFTER_SINGLE = [UNKNOWN, ...OBSERVED, ADDVALIDATE, ...AFTER_ADDVALIDATE];
  const AFTER_LIST = [COLUMNS, SINGLE, ...AFTER_SINGLE];

  if (!CONFIRMED) {
    log('INFO', `Would create a list '${LIST}' on ${WEB} with a person and a date column, create two`);
    log('INFO', 'items one at a time (one naming a column the list lacks), then send three $batch requests');
    log('INFO', 'of item creates: three typed parts with the middle one naming that column, one part with');
    log('INFO', 'no __metadata, and one nometadata part with no type. It then calls');
    log('INFO', 'AddValidateUpdateItemUsingPath twice on its own (once naming the missing column), and');
    log('INFO', 'sends one $batch of four such calls, the second naming that column. The list is');
    log('INFO', 'recycled on the way out.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write. Stopping.');
    return;
  }

  const said = (text) => quote(text).slice(0, 300);
  const ok2xx = (status) => status >= 200 && status < 300;
  // Each part's status line, headers and body, read line by line so a nested ChangeSet answer is walked too.
  const batchParts = (text) => {
    const parts = [];
    let current = null;
    for (const line of String(text).split(/\r?\n/)) {
      if (line.startsWith('--')) {
        if (current) parts.push(current);
        current = null;
        continue;
      }
      const status = /^HTTP\/1\.1 (\d{3})(.*)$/.exec(line);
      if (status && current === null) {
        current = { status: Number(status[1]), reason: status[2].trim(), headers: [], body: [], inBody: false };
        continue;
      }
      if (!current) continue;
      if (!current.inBody) {
        if (line === '') current.inBody = true;
        else current.headers.push(line);
        continue;
      }
      current.body.push(line);
    }
    if (current) parts.push(current);
    return parts.map((part) => ({ status: part.status, reason: part.reason, headers: part.headers,
      body: part.body.join('\n').trim() }));
  };

  // A part carries its own headers, so the verbose and nometadata parts differ only where they must.
  const partOf = (op, digest, inner) => {
    const headers = { Accept: `application/json;odata=${op.odata}`,
      'Content-Type': `application/json;odata=${op.odata}`, 'X-RequestDigest': digest };
    return `--${inner}\r\n`
      + 'Content-Type: application/http\r\n'
      + 'Content-Transfer-Encoding: binary\r\n'
      + '\r\n'
      + `POST ${WEB}/_api/${partPath}/${op.path || 'items'} HTTP/1.1\r\n`
      + Object.entries(headers).map(([name, value]) => `${name}: ${value}\r\n`).join('')
      + '\r\n'
      + `${JSON.stringify(op.body)}\r\n`;
  };
  const token = () => Math.random().toString(36).slice(2, 10);
  // The Id the scratch list was certified with, which the title must still name when a $batch is sent.
  let claimed = null;
  // One $batch request holding one ChangeSet of `ops`, with no retry, since a retry would hide the answer.
  const sendChangeSet = async (ops) => {
    // The parts name the list by title, as a history write does, so that title must still name this run's list.
    const named = await sendRaw(`web/lists/getbytitle('${pathLiteral(LIST)}')?$select=Id,Title`);
    const namedHead = maskedHead(named);
    const namedId = !namedHead && recordBody(named) ? guidOf(recordBody(named).Id) : null;
    if (namedId === null || namedId !== claimed) {
      return { ok: false, status: null, parts: [], sent: ops.length, text: `not sent: the title read `
        + `${namedHead ? namedHead.why : `answered ${namedId === null ? 'no list Id' : `list ${namedId}`}`}, `
        + `where the list this run created is ${claimed}` };
    }
    const digest = await getDigest();
    const outer = `batch_${token()}${token()}`;
    const inner = `changeset_${token()}${token()}`;
    const body = `--${outer}\r\n`
      + `Content-Type: multipart/mixed; boundary=${inner}\r\n`
      + '\r\n'
      + ops.map((op) => partOf(op, digest, inner)).join('')
      + `--${inner}--\r\n`
      + `--${outer}--\r\n`;
    let res;
    try {
      // No Accept header, for #401's reason: a JSON Accept turns the throttling-page redirect into a 406.
      res = await fetch(`${WEB}/_api/$batch`, { method: 'POST',
        headers: { 'Content-Type': `multipart/mixed; boundary=${outer}`, 'X-RequestDigest': digest }, body });
    } catch (err) {
      return { ok: false, status: null, text: `no response: ${err && err.message ? err.message : String(err)}`,
        parts: [], sent: ops.length };
    }
    const text = await res.text();
    return { ok: res.ok, status: res.status, text, parts: batchParts(text), sent: ops.length };
  };
  // The head a whole $batch earns when it carried no part answers, or null when its parts decide.
  const outerHead = (batch) => {
    if (batch.status === null) return { outcome: 'NOT ESTABLISHED', why: scrub(batch.text) };
    if (batch.ok && batch.parts.length) return null;
    // A 2xx whose text this probe found no part status line in says nothing about the parts, so it stays open.
    if (batch.ok) {
      return { outcome: 'NO PART STATUS', why: `HTTP ${batch.status} carried no part: ${said(batch.text)}`,
        state: 'open' };
    }
    if (isRefusal(batch.status)) {
      return { outcome: 'OUTER REQUEST REFUSED', why: `HTTP ${batch.status}: ${said(batch.text)}` };
    }
    return { outcome: 'NOT ESTABLISHED', why: `the $batch ${unanswered({ ok: false, status: batch.status })}: `
      + said(batch.text) };
  };
  const partSaid = (part) => `HTTP ${part.status} ${part.reason}; headers ${said(part.headers.join('; '))}; `
    + `body ${said(part.body) || '(none)'}`;
  // A throttled or unauthorised part answered nothing about the question, so its head leaves the row open.
  const partHead = (part) => (!part ? 'NO PART STATUS' : ok2xx(part.status) ? 'PART ANSWERED 2XX'
    : isRefusal(part.status) ? 'PART REFUSED' : 'NOT ESTABLISHED');
  const fieldsOf = (parsed) => entriesOf(parsed).rows;
  const parsedOf = (text) => { try { return JSON.parse(text); } catch { return null; } };
  // Why the answers cannot be matched to the parts by position, or null when they can; no document says they arrive
  // one per part in order. `names[i]`, when given, are the fields part i sent, which an answer's field list must name.
  const unmatched = (batch, names = null) => {
    if (batch.parts.length !== batch.sent) return `${batch.sent} part(s) sent, ${batch.parts.length} answer(s)`;
    // An answer with no per-field list names no fields, so only one such answer can be placed, by elimination.
    const fieldless = names === null ? 0
      : batch.parts.filter((part) => fieldsOf(parsedOf(part.body)) === null).length;
    if (fieldless > 1) return `${fieldless} answers carry no per-field list, so which part each answers is unknown`;
    const differ = (names || []).map((sent, i) => {
      const fields = fieldsOf(parsedOf(batch.parts[i].body));
      if (fields === null) return null;
      const answered = fields.map((f) => f.FieldName).filter((name) => name !== 'Id');
      return sameElements(answered, sent) ? null
        : `answer ${i + 1} names ${quoteValue(answered)} where part ${i + 1} sent ${JSON.stringify(sent)}`;
    }).filter((problem) => problem !== null);
    return differ.length ? scrub(differ.join('; ')) : null;
  };
  const answersSaid = (batch) => batch.parts.map((part, i) => `answer ${i + 1}: ${partSaid(part)}`).join(' | ');
  // The Title an item-create answer names, verbose or nometadata, or null when it names none.
  const titleOf = (part) => {
    const parsed = parsedOf(part.body);
    const entity = parsed && parsed.d && typeof parsed.d === 'object' ? parsed.d : parsed;
    return entity && typeof entity.Title === 'string' ? entity.Title : null;
  };
  // Pairs part k with the answer naming titles[k]; one answer naming no Title goes to the one part left.
  const byTitle = (batch, titles) => {
    const count = unmatched(batch);
    if (count) return { why: count, answerOf: null, inferred: null };
    const answerOf = titles.map(() => null);
    const loose = [];
    const problems = [];
    batch.parts.forEach((part, i) => {
      const named = titleOf(part);
      const k = named === null ? -1 : titles.indexOf(named);
      if (named === null) loose.push(i);
      else if (k === -1) problems.push(`answer ${i + 1} names Title ${quoteValue(named)}, which no part sent`);
      else if (answerOf[k] !== null) problems.push(`answers ${answerOf[k] + 1} and ${i + 1} both name part ${k + 1}`);
      else answerOf[k] = i;
    });
    if (!problems.length && loose.length > 1) {
      problems.push(`${loose.length} answers name no Title, so which part each answers is unknown`);
    }
    if (problems.length) return { why: scrub(problems.join('; ')), answerOf: null, inferred: null };
    const left = answerOf.findIndex((i) => i === null);
    if (left !== -1) answerOf[left] = loose[0];
    return { why: null, answerOf, inferred: left === -1 ? null : left };
  };
  const NOT_MATCHED = 'ANSWERS NOT MATCHED';

  let me = null;
  try {
    beginFixture();
    const userHeld = await settleFixture(USER, async () => {
      const { account, said: read } = await readAccount();
      if (!account) return { ok: true, status: 200, body: { Read: read } };
      me = account;
      // The email itself is never put in the row; only that there is one to build claims from.
      return { ok: true, status: 200, body: { Read: read, Id: account.Id,
        HasEmail: typeof account.Email === 'string' && account.Email.includes('@') } };
    }, { Read: 'HTTP 200', Id: (v) => Number.isInteger(v) && v > 0, HasEmail: true }, [CLAIMS]);

    const list = await claimScratchList({ id: 'transport.batch.fixture-item-batch-list', question: Q.list,
      title: LIST, description: OWNERSHIP, dependents: AFTER_LIST,
      declared: { ListItemEntityTypeFullName: (v) => typeof v === 'string' && v.length > 0 } });
    if (!list.held) return;
    // Every write that does not ask about title addressing goes by the certified Id.
    const listPath = list.path;
    claimed = guidOf(list.body.Id);
    const itemType = list.body.ListItemEntityTypeFullName;
    const typed = (title, extra = {}) => ({ __metadata: { type: itemType }, Title: title, ...extra });
    const single = async (body) => sendRaw(`${listPath}/items`, { method: 'POST',
      headers: { ...VERBOSE_WRITE, 'X-RequestDigest': await getDigest() }, body });

    // The deploy's create bodies for a person and a date-and-time column, which the AddValidate parts write.
    const created = {};
    beginFixture();
    for (const [name, body] of [
      [WHO, { __metadata: { type: 'SP.FieldUser' }, FieldTypeKind: 20, SelectionMode: 0 }],
      [WHEN, { __metadata: { type: 'SP.FieldDateTime' }, FieldTypeKind: 4, DisplayFormat: 1 }],
    ]) {
      const sent = await spWrite(`${listPath}/fields`, { ...body, Title: name, Required: false },
        await getDigest(), VERBOSE_WRITE);
      created[`${name}.Create`] = `HTTP ${sent.status}${sent.ok ? '' : `: ${said(sent.text)}`}`;
      log('INFO', `create ${name}: ${created[`${name}.Create`]}`);
    }
    // Recorded, never judged: the read-back decides whether the columns hold.
    const recorded = (v) => typeof v === 'string';
    const columnsHeld = await settleFixture(COLUMNS, async () => {
      // The creates' answers join the read-back, so a refused column shows its reason in RESULTS.
      const body = { ...created };
      for (const name of [WHO, WHEN]) {
        // The whole field is read, as datetime-sentinel-probe does, since $select of a subtype property can 400.
        const read = await sendRaw(`${listPath}/fields/getbyinternalnameortitle('${name}')`);
        const head = readHead(read);
        body[`${name}.Read`] = head ? head.why : `HTTP ${read.status}`;
        const field = head ? null : recordBody(read);
        if (field) body[`${name}.TypeAsString`] = field.TypeAsString;
        if (field && name === WHEN) body[`${name}.DisplayFormat`] = field.DisplayFormat;
      }
      return { ok: true, status: 200, body };
    }, { [`${WHO}.Create`]: recorded, [`${WHO}.Read`]: 'HTTP 200', [`${WHO}.TypeAsString`]: 'User',
      [`${WHEN}.Create`]: recorded, [`${WHEN}.Read`]: 'HTTP 200', [`${WHEN}.TypeAsString`]: 'DateTime',
      // DisplayFormat 1 is what makes it date and time, which the ISO row's comparison rests on.
      [`${WHEN}.DisplayFormat`]: 1 },
    [CLAIMS, ISO]);

    const made = await single(typed(TITLES.single));
    const madeHead = maskedHead(made);
    const madeId = !madeHead && recordBody(made) && Number.isInteger(recordBody(made).Id) ? recordBody(made).Id : null;
    const back = madeId === null ? null : await sendRaw(`${listPath}/items(${madeId})?$select=Id,Title`);
    const backHead = back === null ? null : maskedHead(back);
    const backBody = back === null || backHead ? null : recordBody(back);
    const singleHeld = backBody !== null && backBody.Title === TITLES.single;
    // A read-back answered 2xx with no JSON object says nothing about the Title, so it leaves the control open.
    const backUnread = back !== null && !backHead && backBody === null;
    // A create answered 2xx with no JSON object says nothing about the Id, so it too leaves the control open.
    const madeUnread = !madeHead && recordBody(made) === null;
    const singleOutcome = singleHeld ? 'PASS' : backUnread || madeUnread
      || [madeHead, backHead].some((h) => h && h.outcome === 'NOT ESTABLISHED') ? 'NOT ESTABLISHED' : 'FAIL';
    record(SINGLE, Q.single, singleOutcome, madeHead ? `the create: ${madeHead.why}`
      : madeId === null ? `the create answered HTTP ${made.status} with no Id: ${said(made.text)}`
        : backHead ? `created Id ${madeId}; the read-back: ${backHead.why}`
          : `created Id ${madeId}; it reads back Title ${quoteValue(backBody && backBody.Title)}`);
    if (singleOutcome === 'FAIL') {
      voidRows(AFTER_SINGLE, 'a single typed create did not land, so a batch answer '
        + 'would say nothing about the transport');
      return;
    }
    if (singleOutcome === 'NOT ESTABLISHED') {
      for (const id of AFTER_SINGLE) {
        const row = RESULTS.find((r) => r.id === id);
        if (row.state === 'void') continue;
        record(id, row.question, 'NOT ESTABLISHED', 'not asked: the single-create control was not '
          + 'established; a re-run can ask it');
      }
      return;
    }

    const refused = await single(typed(TITLES.unknown, { [MISSING]: 'x' }));
    // Recorded once the items read says whether its Title landed, since a refusal alone proves nothing stored.
    const refusedAnswer = refused.status !== null && isRefusal(refused.status) ? 'PASS'
      : refused.status !== null && ok2xx(refused.status) ? 'FAIL' : 'NOT ESTABLISHED';
    const refusedSaid = refused.status === null ? scrub(refused.text)
      : `HTTP ${refused.status}: ${said(refused.text)}`;

    const three = await sendChangeSet([
      { odata: 'verbose', body: typed(TITLES.a) },
      { odata: 'verbose', body: typed(TITLES.b, { [MISSING]: 'x' }) },
      { odata: 'verbose', body: typed(TITLES.c) },
    ]);
    const untypedVerbose = await sendChangeSet([{ odata: 'verbose', body: { Title: TITLES.verbose } }]);
    const untypedNometadata = await sendChangeSet([{ odata: 'nometadata', body: { Title: TITLES.nometadata } }]);

    // Learn's "Create list item in a folder" body; `folder` null omits FolderPath, which is one question here.
    const addValidateBody = (folder, values) => ({
      listItemCreateInfo: folder === null ? { UnderlyingObjectType: 0 }
        : { FolderPath: { DecodedUrl: folder }, UnderlyingObjectType: 0 },
      formValues: Object.entries(values).map(([FieldName, FieldValue]) => ({ FieldName, FieldValue })),
      bNewDocumentUpdate: false,
    });
    const fieldsSaid = (fields) => quote(fields.map((f) => `${f.FieldName} HasException=`
      + `${JSON.stringify(f.HasException)} ErrorMessage=${JSON.stringify(f.ErrorMessage)} `
      + `FieldValue=${JSON.stringify(f.FieldValue)}`).join('; ')).slice(0, 600);
    const headOutcome = (head) => (head.outcome === 'NOT ESTABLISHED' ? 'NOT ESTABLISHED' : 'FAIL');
    // The control: Learn's form, sent alone, with the list's root folder as an absolute FolderPath.
    const addValidateControl = async () => {
      const root = await sendRaw(`${listPath}/RootFolder?$select=ServerRelativeUrl`);
      const rootHead = maskedHead(root);
      const rootBody = rootHead ? null : recordBody(root);
      if (rootHead || !rootBody || typeof rootBody.ServerRelativeUrl !== 'string') {
        // A 2xx with no JSON object settles nothing; an object without the URL is an answer.
        const outcome = rootHead ? headOutcome(rootHead) : rootBody ? 'FAIL' : 'NOT ESTABLISHED';
        return { outcome, folder: null, evidence: 'the root folder '
          + `read: ${rootHead ? rootHead.why : `HTTP ${root.status} carried no ServerRelativeUrl`}` };
      }
      const folder = `${new URL(WEB).origin}${rootBody.ServerRelativeUrl}`;
      const sent = await sendRaw(`${listPath}/AddValidateUpdateItemUsingPath`, { method: 'POST',
        headers: { 'Content-Type': NOMETADATA, 'X-RequestDigest': await getDigest() },
        body: addValidateBody(folder, { Title: TITLES.addvalidate }) });
      const head = maskedHead(sent);
      if (head) return { outcome: headOutcome(head), folder, evidence: `the call: ${head.why}` };
      const { rows: fields, shape } = entriesOf(sent.parsed);
      // A 2xx whose per-field list cannot be read is no answer about the call, so it is left open.
      if (!fields) {
        return { outcome: 'NOT ESTABLISHED', folder, evidence: `the call answered HTTP ${sent.status} and ${shape}: `
          + `${quote(sent.text).slice(0, 400)}` };
      }
      const idField = fields.find((f) => f.FieldName === 'Id');
      const madeAt = idField ? Number(idField.FieldValue) : NaN;
      if (fields.some((f) => f.HasException === true) || !Number.isInteger(madeAt) || madeAt < 1) {
        return { outcome: 'FAIL', folder, evidence: `the call answered HTTP ${sent.status}: `
          + `${quote(sent.text).slice(0, 400)}` };
      }
      const back = await sendRaw(`${listPath}/items(${madeAt})?$select=Id,Title`);
      const backHead = maskedHead(back);
      if (backHead) return { outcome: headOutcome(backHead), folder, evidence: `created Id ${madeAt}; the `
        + `read-back: ${backHead.why}` };
      if (!recordBody(back)) {
        return { outcome: 'NOT ESTABLISHED', folder, evidence: `created Id ${madeAt}; the read-back answered `
          + `HTTP ${back.status} with no JSON object: ${said(back.text)}` };
      }
      const title = recordBody(back).Title;
      return { outcome: title === TITLES.addvalidate ? 'PASS' : 'FAIL', folder,
        evidence: `created Id ${madeAt}; it reads back Title ${quoteValue(title)}` };
    };
    const control = await addValidateControl();
    record(ADDVALIDATE, Q.addvalidate, control.outcome, control.evidence);
    let avUnknown = null;
    let avSaid = null;
    if (control.outcome === 'PASS') {
      const sent = await sendRaw(`${listPath}/AddValidateUpdateItemUsingPath`, { method: 'POST',
        headers: { 'Content-Type': NOMETADATA, 'X-RequestDigest': await getDigest() },
        body: addValidateBody(control.folder, { Title: TITLES.avunknown, [MISSING]: 'x' }) });
      const head = maskedHead(sent);
      const fields = head ? null : fieldsOf(sent.parsed);
      const fieldRefused = fields !== null && fields.some((f) => f.FieldName === MISSING && f.HasException === true);
      // A 2xx with no readable per-field list says nothing about the field, so it is left open.
      avUnknown = head ? (head.outcome === 'NOT ESTABLISHED' ? 'NOT ESTABLISHED' : 'PASS')
        : fieldRefused ? 'PASS' : fields === null ? 'NOT ESTABLISHED' : 'FAIL';
      avSaid = head ? head.why : `HTTP ${sent.status}: `
        + `${fields ? `fields ${fieldsSaid(fields)}` : quote(sent.text).slice(0, 400)}`;
    }
    // Each part asked only when what it rests on held, so a voided row is never overwritten.
    const asked = [
      { id: FOLDER, question: Q.folder, title: TITLES.folder, folder: null, values: {} },
      { id: AV_FAILED, question: Q.avfailed, title: TITLES.avfailed, folder: control.folder,
        values: { [MISSING]: 'x' } },
      ...(userHeld && columnsHeld ? [{ id: CLAIMS, question: Q.claims, title: TITLES.claims,
        folder: control.folder, values: { [WHO]: JSON.stringify([{ Key: `i:0#.f|membership|${me.Email}` }]) } }]
        : []),
      ...(columnsHeld ? [{ id: ISO, question: Q.iso, title: TITLES.iso, folder: control.folder,
        values: { [WHEN]: STAMP } }] : []),
    ];
    const addValidate = control.outcome !== 'PASS' ? null : await sendChangeSet(asked.map((one) => ({
      odata: 'nometadata', path: 'AddValidateUpdateItemUsingPath',
      body: addValidateBody(one.folder, { Title: one.title, ...one.values }) })));

    const select = columnsHeld ? `Id,Title,${WHO}Id,${WHEN}` : 'Id,Title';
    const titles = await sendRaw(`${listPath}/items?$select=${select}&$top=100`);
    const titlesHead = maskedHead(titles);
    // Every item under each Title, so an item created twice is counted and never collapsed into one.
    const titleRows = titlesHead ? { rows: null, shape: null } : entriesOf(titles.parsed);
    // A page the read did not follow may hold any Title, so a paged read says nothing about what landed.
    const titlesNext = titleRows.rows === null ? null : continuationOf(titles.parsed);
    if (titlesNext !== null) {
      titleRows.rows = null;
      titleRows.shape = `carried a continuation link (${quote(titlesNext).slice(0, 200)}), which this probe `
        + 'does not follow';
    }
    const present = titleRows.rows === null ? null : new Map();
    for (const row of titleRows.rows || []) {
      present.set(row.Title, [...(present.get(row.Title) || []), row]);
    }
    const landed = (title) => {
      const count = present === null ? null : (present.get(title) || []).length;
      return count === null ? 'unknown' : count === 0 ? 'no' : count === 1 ? 'yes' : `${count} times`;
    };
    const titlesSaid = present === null ? `; the items read-back failed: ${titlesHead ? titlesHead.why
      : `HTTP ${titles.status} ${titleRows.shape}`}` : '';
    // A row that reports whether items landed stays open when the read that would say so failed.
    const landing = present === null ? 'open' : undefined;
    // A refused control passes only once its Title is absent; unknown landing leaves it open.
    const absentOr = (answer, title) => (answer !== 'PASS' ? answer : landed(title) === 'no' ? 'PASS'
      : landed(title) === 'unknown' ? 'NOT ESTABLISHED' : 'FAIL');
    const refusedOutcome = absentOr(refusedAnswer, TITLES.unknown);
    record(UNKNOWN, Q.unknown, refusedOutcome, `${refusedSaid}; landed ${landed(TITLES.unknown)}${titlesSaid}`);
    if (avUnknown !== null) {
      avUnknown = absentOr(avUnknown, TITLES.avunknown);
      record(AV_UNKNOWN, Q.avunknown, avUnknown, `${avSaid}; landed ${landed(TITLES.avunknown)}${titlesSaid}`);
    }

    const threeHead = outerHead(three);
    // Matched by the Title each answer names, since no document says the answers come back in part order.
    const threeMatch = threeHead ? null : byTitle(three, [TITLES.a, TITLES.b, TITLES.c]);
    const threeUnmatched = threeMatch ? threeMatch.why : null;
    const threeAnswer = (k) => three.parts[threeMatch.answerOf[k]];
    const threeLanded = `landed A ${landed(TITLES.a)}, B ${landed(TITLES.b)}, C ${landed(TITLES.c)}${titlesSaid}`;
    const threeSaid = `${threeUnmatched}; ${answersSaid(three)}; ${threeLanded}`;
    // The one answer paired by elimination is named, since it names no Title of its own.
    const inferredSaid = threeMatch && threeMatch.inferred !== null
      ? `; answer ${threeMatch.answerOf[threeMatch.inferred] + 1} names no Title and is part `
        + `${threeMatch.inferred + 1}'s as the one part left` : '';
    if (threeUnmatched) {
      record('transport.batch.changeset-item-creates-per-part', Q.parts, NOT_MATCHED, threeSaid, 'open');
    } else {
      record('transport.batch.changeset-item-creates-per-part', Q.parts, threeHead ? threeHead.outcome : 'RECORDED',
        threeHead ? threeHead.why : `outer HTTP ${three.status}, ${three.parts.length} part answer(s) matched by `
          + `Title: ${[0, 1, 2].map((k) => `part ${k + 1} (answer ${threeMatch.answerOf[k] + 1}): `
            + partSaid(threeAnswer(k))).join(' | ')}${inferredSaid}; ${threeLanded}`,
        threeHead ? threeHead.state : landing);
    }

    if (refusedOutcome === 'FAIL') {
      voidRows(['transport.batch.changeset-item-create-failed-part'], 'a single create naming '
        + `${MISSING} was not refused, so the middle part is not a known failing request`);
    } else if (refusedOutcome === 'NOT ESTABLISHED') {
      record('transport.batch.changeset-item-create-failed-part', Q.failed, 'NOT ESTABLISHED',
        'not asked: the missing-column control was not established; a re-run can ask it');
    } else if (threeUnmatched) {
      record('transport.batch.changeset-item-create-failed-part', Q.failed, NOT_MATCHED, threeSaid, 'open');
    } else {
      const middle = threeHead ? null : threeAnswer(1);
      record('transport.batch.changeset-item-create-failed-part', Q.failed,
        threeHead ? threeHead.outcome : partHead(middle),
        threeHead ? threeHead.why : `answer ${threeMatch.answerOf[1] + 1}: ${partSaid(middle)}${inferredSaid}; `
          + `landed B ${landed(TITLES.b)}; neighbours landed A ${landed(TITLES.a)}, C ${landed(TITLES.c)}`
          + titlesSaid, threeHead ? threeHead.state : landing);
    }

    for (const [id, question, batch, title] of [
      ['transport.batch.changeset-item-create-untyped-verbose', Q.verbose, untypedVerbose, TITLES.verbose],
      ['transport.batch.changeset-item-create-untyped-nometadata', Q.nometadata, untypedNometadata,
        TITLES.nometadata],
    ]) {
      const head = outerHead(batch);
      const apart = head ? null : unmatched(batch);
      if (apart) {
        record(id, question, NOT_MATCHED, `${apart}; ${answersSaid(batch)}; landed ${landed(title)}${titlesSaid}`,
          'open');
        continue;
      }
      record(id, question, head ? head.outcome : partHead(batch.parts[0]), head ? head.why
        : `${partSaid(batch.parts[0])}; landed ${landed(title)}${titlesSaid}`, head ? head.state : landing);
    }

    if (control.outcome === 'FAIL') {
      voidRows(AFTER_ADDVALIDATE, 'the single AddValidateUpdateItemUsingPath '
        + 'call in Learn\'s form did not land, so a part calling it says nothing about the question');
    } else if (control.outcome === 'NOT ESTABLISHED') {
      for (const [id, question] of [[AV_UNKNOWN, Q.avunknown], ...asked.map((one) => [one.id, one.question])]) {
        record(id, question, 'NOT ESTABLISHED', 'not asked: the AddValidateUpdateItemUsingPath control '
          + 'was not established; a re-run can ask it');
      }
    } else {
      // What reads back for the value a part wrote, against what it sent; `head` is null when WRITTEN applies.
      const readsBack = (one) => {
        // Only a Title held by exactly one item says which item the part wrote.
        const row = landed(one.title) === 'yes' ? present.get(one.title)[0] : null;
        if (!row || (one.id !== CLAIMS && one.id !== ISO)) return { said: '', head: null };
        const shown = (value) => (value === undefined ? '(absent)' : quoteValue(value));
        if (one.id === CLAIMS) {
          const who = row[`${WHO}Id`];
          return { head: who === me.Id ? null : 'ACCEPTED, NOT STORED', said: `; ${WHO}Id reads back `
            + `${shown(who)}, this account's Id: ${who === me.Id ? 'yes' : 'no'} (the account read back Id ${me.Id})` };
        }
        const when = row[WHEN];
        const text = typeof when === 'string' ? when : '';
        const read = `; ${WHEN} reads back ${shown(when)}`;
        // A date alone has lost the time sent, so it is compared as a date and never heads WRITTEN.
        if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
          return { head: 'ACCEPTED, STORED DIFFERENTLY', said: `${read}, a date with no time; as a date against `
            + `the sent ${STAMP.slice(0, 10)}: ${text === STAMP.slice(0, 10) ? 'same' : 'different'}` };
        }
        // A date-time with no zone would be read in the browser's zone, so it is not compared at all.
        if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(text)) {
          return { head: 'STORED WITHOUT A ZONE', said: `${read}, a date and time with no zone; not compared` };
        }
        const zoned = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/i.test(text);
        const at = zoned ? Date.parse(text) : NaN;
        const sent = Date.parse(STAMP);
        return { head: at === sent ? null : 'ACCEPTED, STORED DIFFERENTLY', said: `${read}; as a UTC instant `
          + `${Number.isNaN(at) ? '(not a zoned date and time)' : new Date(at).toISOString()} against the sent `
          + `${new Date(sent).toISOString()}: ${at === sent ? 'same' : 'different'}` };
      };
      const outer = outerHead(addValidate);
      const avUnmatched = outer ? null : unmatched(addValidate,
        asked.map((one) => ['Title', ...Object.keys(one.values)]));
      const avLanded = asked.map((one) => `${one.title} ${landed(one.title)}`).join(', ');
      const neighbours = asked.filter((one) => one.id !== AV_FAILED)
        .map((one) => `${one.title} ${landed(one.title)}`).join(', ');
      asked.forEach((one, i) => {
        if (one.id === AV_FAILED && avUnknown === 'FAIL') {
          voidRows([AV_FAILED], `a single call naming ${MISSING} was not refused, so the second part `
            + 'is not a known failing request');
          return;
        }
        if (one.id === AV_FAILED && avUnknown === 'NOT ESTABLISHED') {
          record(AV_FAILED, Q.avfailed, 'NOT ESTABLISHED', 'not asked: the missing-column control was not '
            + 'established; a re-run can ask it');
          return;
        }
        if (outer) {
          // The failing part keeps the batch's own head; a write under question is not established.
          record(one.id, one.question, one.id === AV_FAILED ? outer.outcome : 'NOT ESTABLISHED',
            `the $batch was not answered part by part: ${outer.outcome}: ${outer.why}`,
            one.id === AV_FAILED ? outer.state : undefined);
          return;
        }
        if (avUnmatched) {
          record(one.id, one.question, NOT_MATCHED, `${avUnmatched}; ${answersSaid(addValidate)}; landed `
            + `${avLanded}${titlesSaid}`, 'open');
          return;
        }
        const part = addValidate.parts[i];
        const fields = fieldsOf(parsedOf(part.body));
        const refused = fields !== null && fields.some((f) => f.HasException === true);
        const kept = readsBack(one);
        const answer = `HTTP ${part.status} ${part.reason}; ${fields ? `fields ${fieldsSaid(fields)}`
          : `body ${said(part.body) || '(none)'}`}; landed ${landed(one.title)}${kept.said}`;
        if (one.id === AV_FAILED) {
          const missing = fields !== null && fields.some((f) => f.FieldName === MISSING && f.HasException === true);
          record(AV_FAILED, Q.avfailed, ok2xx(part.status) ? (missing ? 'FIELD REFUSED' : 'PART ANSWERED 2XX')
            : partHead(part), `${answer}; neighbours landed ${neighbours}${titlesSaid}`, landing);
          return;
        }
        const why = !ok2xx(part.status) ? (isRefusal(part.status) ? 'the write was refused'
          : 'the part was not answered; a re-run can ask it')
          : fields === null ? 'the part answered with no per-field list'
            : refused ? 'a field was refused' : landed(one.title) !== 'yes' ? 'no single item with its Title is known to exist'
              : null;
        // A refused write leaves the spelling not established; it is recorded and the probe goes on.
        const head = why !== null ? 'NOT ESTABLISHED' : kept.head || 'WRITTEN';
        record(one.id, one.question, head,
          why === null ? `${answer}${titlesSaid}` : `${why}: ${answer}${titlesSaid}`);
      });
    }
  } catch (err) {
    log('FAIL', `probe aborted: ${scrub(String((err && err.message) || err)).slice(0, 240)}. `
      + 'The unasked rows stay open.');
  } finally {
    await recycleScratchLists();
    // Reported here, after the recycle, so every path prints the recycle line above the table.
    report();
  }
})();
