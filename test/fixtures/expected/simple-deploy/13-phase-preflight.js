  markPhase('Phase 1.2: read-only preflight');
  // === Preflight: fail-closed adoption of existing schema objects ===
  // A matching display name is not proof that an existing list or field was
  // created from this schema. Before Phase 1.3 performs its first write, every
  // existing list must carry this declaration's exact provenance marker and
  // every immutable shape must agree. Mutable settings are reconciled only
  // after both checks pass.
  log('INFO', 'Starting Phase 1.2: read-only preflight.');
  invalidateFieldShapes();  // probes reflect phase-start state
  // Read-only, so lanes are free of write races, but the field wave still
  // waits for ALL list shapes: lookup fields validate against their target
  // list's GUID, which another lane may still be reading.
  const preflightListShapes = Object.create(null);
  // Three outcomes: 'absent' (no such list), 'unreadable' (its probe failed),
  // 'ok' (a shape was read, whether or not that shape matched). A fourth,
  // 'mismatch', was removed: a mismatched list still has its shape stored, so
  // neither consumer could ever tell it from 'ok'.
  // Null-prototype, so a list titled 'constructor' or 'toString' cannot read
  // truthy from Object.prototype without ever being assigned.
  const listOutcomes = Object.create(null);
  // Lists found under a previous title carrying that title's own marker,
  // keyed by the current title. The renames phase acts on it; nothing here
  // writes. A previous title without its marker, present beside the current
  // title, or present twice over is an error, never a guess.
  const renamePlan = Object.create(null);
  // By declared TITLE, so a lookup can resolve its target the same way the
  // owning list resolves itself. Renames have not run yet at preflight.
  const probeTitle = (title) => (renamePlan[title] ? renamePlan[title].from : title);
  const probeTitleFor = (list) => probeTitle(list.title);
  async function previousTitleShapes(list) {
    const found = [];
    for (const previous of (list.renamed_from || [])) {
      const shape = await readListShape(previous.title);
      if (!shape) continue;
      const held = typeof shape.Description === 'string' ? shape.Description : '';
      found.push({
        title: previous.title, marker: previous.expected_marker, shape,
        carries: previous.expected_marker.length > 0 && held.includes(previous.expected_marker),
      });
    }
    return found;
  }
  await mapLanes(SCHEMA.lists, (list) => list.title, async (list) => {
    try {
      let actual = await readListShape(list.title);
      const previous = await previousTitleShapes(list);
      if (!actual && previous.length === 0) { listOutcomes[list.title] = 'absent'; return; }
      let renamedFrom = null;
      if (previous.length > 0) {
        const titles = previous.map((p) => `'${p.title}'`).join(', ');
        let refusal = null;
        if (actual) {
          refusal = `'${list.title}' exists and so does its previous title ${titles}; deploy cannot tell a rename from a collision. Remove or retitle one of them by hand.`;
        } else if (previous.length > 1) {
          refusal = `more than one previous title of '${list.title}' exists (${titles}); deploy cannot choose which to rename. Remove or retitle all but one by hand.`;
        } else if (!previous[0].carries) {
          refusal = `'${previous[0].title}' exists but does not carry the exact provenance marker for its previous name ("${previous[0].marker}"). Deploy will not adopt or rename it; restore that marker only if this tool created the list.`;
        }
        if (refusal) {
          listOutcomes[list.title] = 'ok';
          log('ERROR', `Existing-schema list '${list.title}': ${refusal}`);
          summary.errors.push({ phase: 'preflight', list: list.title, error: refusal, mismatches: [] });
          return;
        }
        renamedFrom = previous[0];
        actual = renamedFrom.shape;
        renamePlan[list.title] = { from: renamedFrom.title, marker: renamedFrom.marker, id: actual.Id };
        log('INFO', `'${renamedFrom.title}' carries the marker for its previous name; the renames phase will retitle it '${list.title}'.`);
      }
      // Stored BEFORE the shape is judged: a list with a wrong BaseTemplate
      // still resolves lookup GUIDs and its columns are still worth reporting.
      preflightListShapes[list.title] = actual;
      listOutcomes[list.title] = 'ok';
      // readListShape also fail-closes malformed or omitted mutable settings;
      // drift itself is safe to repair later and is reported for visibility.
      if (listSettingsMismatch(actual, desiredListSettings(list))) {
        log('INFO', `Existing list '${list.title}' has mutable versioning/content-type drift; Phase 2.1 will reconcile it.`);
      }
      // Ownership of a planned rename was proved by the PREVIOUS marker
      // above; the current marker is written by the renames phase.
      const mismatches = renamedFrom
        ? immutableListMismatches(list, actual)
        : listAdoptionMismatches(list, actual);
      if (mismatches.length === 0) return;
      const message = [...new Set(mismatches.map(m => m.message))].join(' ');
      log('ERROR', `Existing-schema list '${list.title}': ${message}`);
      // Last statement in the try, as in the field lane below: anything that
      // threw after this push would give one list a second entry, and the
      // grouped report reads only the first.
      summary.errors.push({
        phase: 'preflight', list: list.title, error: message, mismatches,
      });
    } catch (err) {
      listOutcomes[list.title] = 'unreadable';
      log('ERROR', `Existing-schema list '${list.title}': ${err.message}`);
      summary.errors.push({ phase: 'preflight', list: list.title, error: err.message });
    }
  }, 4);

  // Existing columns that declare unique while the site holds them
  // unconstrained, by list title. Null-prototype for the same reason
  // listOutcomes is, and written once per list by the lane that owns it.
  const newlyUniqueColumns = Object.create(null);
  // Columns that declare unique and were not in the list's field
  // enumeration, where that enumeration may have ended before the list did.
  // Held apart from the map above because "the site holds this
  // unconstrained" and "this read did not establish what the site holds"
  // are different claims and the second one must not be reported as the
  // first.
  const unseenUniqueColumns = Object.create(null);

  await mapLanes(
    SCHEMA.lists.filter((list) => preflightListShapes[list.title]),
    (list) => list.title,
    async (list) => {
    const newlyUnique = [];
    const unseenUnique = [];
    for (const field of declaredFieldsForList(list)) {
      try {
        const actual = await readFieldShape(probeTitleFor(list), field.title, field);
        if (!actual) {
          // Null is "the one field enumeration did not hold this name", and
          // on a page that may be short that is not "the list does not hold
          // it". The cache the probe just filled answers which, at no
          // request, and staying silent here would drop the warning in
          // exactly the case it exists for: a long list whose declared
          // unique column sits past the page.
          if (field.body.EnforceUniqueValues === true
              && (await listFieldShapes(probeTitleFor(list))).truncated) {
            unseenUnique.push(field.title);
          }
          continue;
        }
        // The field phase's own EnforceUniqueValues comparison, made here
        // where nothing has been written yet. Collected before the immutable
        // checks below, which `continue` past this on a clean column.
        if (field.body.EnforceUniqueValues === true && !actual.EnforceUniqueValues) {
          newlyUnique.push(field.title);
        }
        const targetGuid = field.target_list
          ? preflightListShapes[field.target_list]?.Id
          : null;
        const mismatches = await immutableFieldMismatches(
          list.title, field, actual, targetGuid,
          field.target_list ? listOutcomes[field.target_list] : null,
          probeTitle,
        );
        if (mismatches.length === 0) continue;
        const message = [...new Set(mismatches.map(m => m.message))].join(' ');
        log('ERROR', `Existing-schema field '${list.title}.${field.title}': ${message}`);
        summary.errors.push({
          phase: 'preflight', list: list.title, column: field.title,
          error: message, mismatches,
        });
      } catch (err) {
        log('ERROR', `Existing-schema field '${list.title}.${field.title}': ${err.message}`);
        summary.errors.push({
          phase: 'preflight', list: list.title, column: field.title, error: err.message,
        });
      }
    }
    if (newlyUnique.length > 0) newlyUniqueColumns[list.title] = newlyUnique;
    if (unseenUnique.length > 0) unseenUniqueColumns[list.title] = unseenUnique;
  }, 4);

  // #550 made a declared `unique` actually deploy its constraint, so a list
  // provisioned before that fix holds the column unconstrained and the field
  // phase will try to add the constraint against data that never carried it.
  // Reported here, in declaration order like the delta below and ahead of the
  // abort gate, because by the time the field phase asks, earlier phases have
  // already written to the list.
  //
  // assess.js makes the same comparison under `pending_unique:` and says it
  // before the paste, which is the only point an operator can still act on it.
  const listsGainingUnique = SCHEMA.lists.filter((list) => newlyUniqueColumns[list.title]);
  if (listsGainingUnique.length > 0) {
    log('WARN', 'Declared unique constraints this site does not carry yet:');
    for (const list of listsGainingUnique) {
      for (const column of newlyUniqueColumns[list.title]) {
        log('WARN', `  ${list.title}.${column}: declared unique, readback EnforceUniqueValues false`);
      }
    }
    // NOT ESTABLISHED: what SharePoint does with this transition over existing
    // duplicates. `unique-transition-probe.js` asks it and has not been run.
    log('WARN', 'The field phase will attempt to set EnforceUniqueValues on each of those. '
      + 'This preflight did not count duplicate values in them, so it cannot say whether the '
      + 'attempt will be accepted. Check those columns before the field phase reaches them. A '
      + 'refused write is reported with the reason SharePoint gave and stops the run.');
  }

  // The same comparison, on the columns it could not make. assess.js reports
  // these under `pending_unique:` as NOT-ASSESSABLE, so an operator who ran
  // it before the paste reads the same set here.
  const listsWithUnseenUnique = SCHEMA.lists.filter((list) => unseenUniqueColumns[list.title]);
  if (listsWithUnseenUnique.length > 0) {
    log('WARN', 'Declared unique columns this preflight could not read:');
    for (const list of listsWithUnseenUnique) {
      for (const column of unseenUniqueColumns[list.title]) {
        log('WARN', `  ${list.title}.${column}: not in a field enumeration that came back at its ${FIELD_PAGE_SIZE}-row page size`);
      }
    }
    log('WARN', 'Missing from a page that may be truncated is not missing from the list, so whether '
      + 'the site already holds those columns under the declared constraint was not established. The '
      + 'field phase reads the same enumeration, so a column it does not see is one it treats as not '
      + 'provisioned. Check those columns before it reaches them.');
  }

  if (summary.errors.length > 0) {
    // Four lanes interleave their own ERROR lines, so the whole delta is
    // regrouped here in declaration order and printed once.
    const preflight = summary.errors.filter(e => e.phase === 'preflight');
    log('ERROR', 'Existing-schema shape delta:');
    for (const list of SCHEMA.lists) {
      const own = preflight.find(e => e.list === list.title && !e.column);
      const columns = preflight.filter(e => e.list === list.title && e.column);
      if (!own && columns.length === 0) continue;
      log('ERROR', `  ${list.title}`);
      if (listOutcomes[list.title] === 'unreadable') {
        log('ERROR', `    NOT CHECKED: ${own?.error ?? 'the list shape could not be read'}`);
        log('ERROR', '    No column was checked, because the list shape could not be read.');
        continue;
      }
      if (own) {
        const entries = own.mismatches ?? [];
        if (entries.length === 0) log('ERROR', `    ${own.error}`);
        for (const m of entries) log('ERROR', `    ${describeMismatch(m)}`);
      }
      for (const column of columns) {
        log('ERROR', `    ${column.column}`);
        const entries = column.mismatches ?? [];
        if (entries.length === 0) log('ERROR', `      NOT CHECKED: ${column.error}`);
        for (const m of entries) log('ERROR', `      ${describeMismatch(m)}`);
      }
    }
    log('ERROR', 'Existing-schema shape preflight failed; no deployment writes were attempted.');
    return { ...summary, aborted: 'existing-schema-shape-errors' };
  }

