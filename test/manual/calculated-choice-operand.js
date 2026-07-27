/**
 * dbml-sharepoint PROBE — CALCULATED COLUMN OVER CHOICE OPERANDS
 *
 * QUESTION: does SharePoint accept a calculated column whose operands are
 * two single-select Choice columns?
 *
 * WHY: templates/tiered-huddle declares
 *
 *     Route = '=[RaisedAtTier]&" -> "&[TargetTier]'
 *
 * where both operands are Choice. No first-party Microsoft source states
 * whether that is supported, and this project has been wrong about
 * unexercised SharePoint behaviour more than once. If it is refused,
 * deploy.js fails PART-WAY THROUGH provisioning — the same failure shape
 * website/docs/reference/dbml.md warns about for person and lookup
 * operands.
 *
 * WHAT IT ASKS
 *   C1  does the calculated column CREATE over two Choice operands?
 *   C2  does it RENDER a value on a saved item? (creating is not working)
 *   C3  what does SharePoint store in Formula, versus what was sent?
 *   C4  does a Choice value containing & " < survive concatenation?
 *   C5  what happens when one operand is blank?
 *   N1  NEGATIVE CONTROL — is a Person operand refused?
 *
 * READ N1 FIRST. It is the only row that establishes this probe can tell
 * acceptance from refusal. If a Person operand is ACCEPTED, the probe is
 * not sensitive to failure and every other result is worthless.
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
 *
 * WHEN FINISHED: delete the list it created. Everything lives in it.
 */
(async () => {
  // ---- Operator gate -------------------------------------------------
  // Both default false. Pasting an unedited probe prints its plan and
  // stops; nothing touches the tenant until the operator opts in.
  const CONFIRMED = false;
  const ALLOW_WRITES = false;

  // No SITE_URL constant, deliberately. The probe reads the site it was
  // pasted into. A tenant URL committed to this repo has leaked twice, and
  // the field was the vector both times.
  const pageCtx = window._spPageContextInfo;
  if (!pageCtx) {
    console.error('[FATAL] No _spPageContextInfo — paste this into a SharePoint page.');
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

  const spPost = async (path, payload, digest) => {
    const res = await fetch(`${WEB}/_api/${path}`, {
      method: 'POST',
      headers: {
        Accept: 'application/json;odata=nometadata',
        'Content-Type': 'application/json;odata=nometadata',
        'X-RequestDigest': digest,
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

  // ---- Result table --------------------------------------------------
  // A probe answers questions. Outcome and EVIDENCE are recorded
  // separately so a run cannot be summarised as a verdict with nothing
  // behind it.
  //
  // Every question is REGISTERED UP FRONT as NOT ESTABLISHED, and record()
  // overwrites. Appending as you go looks equivalent and is not: a probe
  // that aborts early then reports only what it reached, and prints
  // "0 not established" while most of its questions were never asked.
  const RESULTS = [];
  const expect = (id, question) => {
    RESULTS.push({ id, question, outcome: 'NOT ESTABLISHED', evidence: 'the run did not reach this question' });
  };
  const record = (id, question, outcome, evidence) => {
    const row = RESULTS.find((r) => r.id === id);
    if (row) {
      Object.assign(row, { question, outcome, evidence });
    } else {
      RESULTS.push({ id, question, outcome, evidence });
    }
    const level = outcome === 'PASS' ? 'OK' : outcome === 'FAIL' ? 'FAIL' : 'INFO';
    log(level, `${id}: ${outcome} — ${question}`);
    if (evidence) console.log(`      evidence: ${evidence}`);
  };

  const report = () => {
    console.log('\n==================== RESULTS ====================');
    for (const r of RESULTS) {
      console.log(`${r.id.padEnd(6)} ${r.outcome.padEnd(16)} ${r.question}`);
      if (r.evidence) console.log(`       ${r.evidence}`);
    }
    console.log('=================================================');
    const open = RESULTS.filter((r) => r.outcome === 'NOT ESTABLISHED').length;
    console.log(`${RESULTS.length} question(s); ${RESULTS.length - open} answered, ${open} NOT established.`);
    if (open) {
      console.log('A question with no observation is NOT a pass. Report it as open.');
    }
    console.log('Copy this whole block back verbatim.');
  };

  const LIST = 'dbmlsp Probe CalcChoice';
  const TIERS = ['Tier 1', 'Tier 2', 'Tier 3'];
  // Deliberately awkward: & is SharePoint's concatenation operator, "
  // delimits its string literals, and < is significant in SchemaXml. If
  // concatenation mangles a Choice value, it mangles it here.
  const NASTY = 'A & B "quoted" <tag>';

  const xmlAttr = (s) => String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  if (!CONFIRMED) {
    log('INFO', `Would create list '${LIST}' on ${WEB}, add Choice columns`);
    log('INFO', 'RaisedAtTier/TargetTier plus a Person column, then attempt');
    log('INFO', 'calculated columns over them and read back what was stored.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  // Declared before anything can fail, so an abort reports the questions
  // it never reached instead of only the ones it managed to ask.
  expect('C1', 'Calculated column over two Choice operands is accepted');
  expect('C2', 'Renders a value for two ordinary Choice values');
  expect('C3', 'Formula as SharePoint stored it');
  expect('C4', 'Renders a Choice value containing & " <');
  expect('C5', 'Behaviour when one operand is blank');
  expect('N1', 'NEGATIVE CONTROL: a Person operand is refused');

  let digest = await getDigest();

  // ---- Bootstrap. Every step checks first, so re-running tops up ------
  const existing = await spGet(`web/lists/getbytitle('${LIST}')`);
  if (!existing.ok) {
    const made = await spPost('web/lists', {
      Title: LIST,
      BaseTemplate: 100,
      Description: 'dbml-sharepoint probe list. Safe to delete.',
    }, digest);
    if (!made.ok) {
      record('BOOT', 'Create the probe list', 'FAIL',
             `HTTP ${made.status}: ${made.text.slice(0, 300)}`);
      return report();
    }
    log('OK', `Created list '${LIST}'.`);
  } else {
    log('INFO', `List '${LIST}' already exists — topping up.`);
  }

  const fieldsPath = `web/lists/getbytitle('${LIST}')/fields`;
  const itemsPath = `web/lists/getbytitle('${LIST}')/items`;

  const addField = async (schemaXml) => {
    digest = await getDigest();
    // No __metadata: the harness sends odata=nometadata, and that format
    // REJECTS the type hint rather than ignoring it —
    //   "The property '__metadata' does not exist on type
    //    'SP.XmlSchemaFieldCreationInformation'"
    // The odata=verbose examples in Microsoft's docs all carry it, which is
    // where this gets copied from.
    return spPost(`${fieldsPath}/createfieldasxml`, {
      parameters: {
        SchemaXml: schemaXml,
        Options: 8,  // AddFieldInternalNameHint
      },
    }, digest);
  };

  const fieldExists = async (name) =>
    (await spGet(`${fieldsPath}/getbyinternalnameortitle('${name}')`)).ok;

  const choiceXml = (name) =>
    `<Field Type="Choice" DisplayName="${name}" Name="${name}" Format="Dropdown">` +
    `<CHOICES>${[...TIERS, NASTY].map((c) => `<CHOICE>${xmlAttr(c)}</CHOICE>`).join('')}` +
    `</CHOICES></Field>`;

  for (const name of ['RaisedAtTier', 'TargetTier']) {
    if (!(await fieldExists(name))) {
      const made = await addField(choiceXml(name));
      if (!made.ok) {
        record('BOOT', `Create Choice column ${name}`, 'FAIL',
               `HTTP ${made.status}: ${made.text.slice(0, 300)}`);
        return report();
      }
    }
  }
  if (!(await fieldExists('ProbeOwner'))) {
    await addField(
      '<Field Type="User" DisplayName="ProbeOwner" Name="ProbeOwner" ' +
      'UserSelectionMode="PeopleOnly"/>');
  }

  // ---- C1: the direct question ---------------------------------------
  // Display names equal internal names on this probe list, so the formula
  // needs no rewrite. jsgen does that display-name translation in a real
  // build; here it would only add a second variable to a single question.
  const ROUTE_FORMULA = '=[RaisedAtTier]&" -> "&[TargetTier]';
  const calcXml = (name, formula, refs) =>
    `<Field Type="Calculated" DisplayName="${name}" Name="${name}" ResultType="Text">` +
    `<Formula>${xmlAttr(formula)}</Formula>` +
    `<FieldRefs>${refs.map((r) => `<FieldRef Name="${r}"/>`).join('')}</FieldRefs>` +
    `</Field>`;

  if (!(await fieldExists('ProbeRoute'))) {
    const made = await addField(
      calcXml('ProbeRoute', ROUTE_FORMULA, ['RaisedAtTier', 'TargetTier']));
    record('C1', 'Calculated column over two Choice operands is accepted',
           made.ok ? 'PASS' : 'FAIL',
           made.ok
             ? `HTTP ${made.status} on createfieldasxml`
             : `HTTP ${made.status}: ${made.text.slice(0, 400)}`);
  } else {
    record('C1', 'Calculated column over two Choice operands is accepted', 'PASS',
           'column already present from an earlier run of this probe');
  }

  // ---- C3: what did SharePoint actually store? ------------------------
  const route = await spGet(`${fieldsPath}/getbyinternalnameortitle('ProbeRoute')`);
  if (route.ok) {
    record('C3', 'Formula as SharePoint stored it', 'INFO',
           `sent ${JSON.stringify(ROUTE_FORMULA)} / ` +
           `stored ${JSON.stringify(route.body.Formula)}`);
  } else {
    record('C3', 'Formula as SharePoint stored it', 'NOT ESTABLISHED',
           'the calculated column does not exist to read back');
  }

  // ---- C2 / C4 / C5: does it RENDER? ----------------------------------
  const cases = [
    ['C2', 'Renders a value for two ordinary Choice values',
     { Title: 'c2', RaisedAtTier: 'Tier 1', TargetTier: 'Tier 3' }, 'Tier 1 -> Tier 3'],
    ['C4', 'Renders a Choice value containing & " <',
     { Title: 'c4', RaisedAtTier: NASTY, TargetTier: 'Tier 2' }, `${NASTY} -> Tier 2`],
    ['C5', 'Behaviour when one operand is blank',
     { Title: 'c5', RaisedAtTier: 'Tier 1' }, null],
  ];

  if (!route.ok) {
    for (const [id, question] of cases) {
      record(id, question, 'NOT ESTABLISHED', 'no calculated column to render');
    }
  } else {
    for (const [id, question, payload, expected] of cases) {
      digest = await getDigest();
      const made = await spPost(itemsPath, payload, digest);
      if (!made.ok) {
        record(id, question, 'FAIL',
               `item create HTTP ${made.status}: ${made.text.slice(0, 300)}`);
        continue;
      }
      const back = await spGet(`${itemsPath}(${made.body.Id})?$select=ProbeRoute`);
      const actual = back.ok ? back.body.ProbeRoute : null;
      if (expected === null) {
        // No expected value: a blank operand's behaviour is the finding.
        record(id, question, 'INFO', `stored value: ${JSON.stringify(actual)}`);
      } else {
        record(id, question, actual === expected ? 'PASS' : 'FAIL',
               `expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
      }
    }
  }

  // ---- N1: NEGATIVE CONTROL -------------------------------------------
  // A Person operand in a calculated formula is documented as unsupported.
  // If this SUCCEEDS, this probe cannot distinguish acceptance from
  // refusal, and every PASS above is unproven rather than wrong.
  if (!(await fieldExists('ProbeNegative'))) {
    const negative = await addField(
      calcXml('ProbeNegative', '=[ProbeOwner]&" x"', ['ProbeOwner']));
    record('N1', 'NEGATIVE CONTROL: a Person operand is refused',
           negative.ok ? 'FAIL' : 'PASS',
           negative.ok
             ? 'Person operand was ACCEPTED — this probe cannot detect a refusal, '
               + 'so treat every other row as unproven'
             : `refused with HTTP ${negative.status}: ${negative.text.slice(0, 300)}`);
  } else {
    record('N1', 'NEGATIVE CONTROL: a Person operand is refused', 'NOT ESTABLISHED',
           'ProbeNegative already exists, so this run did not test the refusal. '
           + 'Delete the list and re-run for a clean control.');
  }

  report();
  log('INFO', `Done. Delete the list '${LIST}' when you have copied the results.`);
})();
