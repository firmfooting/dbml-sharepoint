  markPhase('Phase 2.2: declared folders');
  // === Phase 2.2: declared folders ===
  log('INFO', 'Starting Phase 2.2: declared folders.');
  // MEASURED 2026-09-03, `library.folder.creation-path` in folder-probe.js:
  // POST web/GetFolderByServerRelativeUrl('<root>')/folders/add(url='<name>')
  // answered HTTP 200 and returned an SP.Folder (Name, ServerRelativeUrl,
  // ItemCount, Exists, UniqueId); Files/add makes a file, never a folder.
  // `library.folder.filesystem-object-type`, same run: the folder's own list
  // item reads FileSystemObjectType 1, and a file's reads 0
  // (`library.folder.item-shape-of-file-by-name`, 2026-09-13,
  // folder-shape-probe.js), which is the shape check below.
  // `library.folder.creation-blocked-when-disabled`
  // (2026-09-13, library-guards-probe.js): the endpoint answers with
  // EnableFolderCreation off, so this phase needs no ordering against that
  // switch.
  //
  // A live run of this phase answered HTTP 500 "Cannot create folder" for
  // every declared folder, and folder-create-refusal-probe.js was written to
  // find out why. MEASURED 2026-09-13, all four cells of
  // `library.folder.control-plain-name-default-library`,
  // `library.folder.spaced-name-default-library`,
  // `library.folder.plain-name-content-types-disabled` and
  // `library.folder.spaced-name-content-types-disabled`: the call is accepted
  // and the folder reads back whether the name carries spaces or not, and
  // whether or not the library was created with ContentTypesEnabled false.
  // `library.folder.add-using-path-spaced-name`, same run: the ResourcePath
  // spelling lands too. So the refusal is not the call, not the name and not
  // that switch, and what remains is what this run applies to the library
  // before this phase. folder-under-schema-probe.js asks that.
  //
  // THE CAUSE, MEASURED 2026-09-13 in folder-under-schema-probe.js, walking
  // one library through the states this run applies to it in order. Broken
  // role inheritance is innocent (`library.folder.add-with-broken-inheritance`),
  // so is a REQUIRED column with no default, and so is a ValidationFormula on
  // that column: a folder lands under both and reads its own item back with
  // the column null, so neither is evaluated for it. The LIST's
  // ValidationFormula is not innocent. With one set that a blank item fails,
  // `library.folder.add-with-list-validation` answered HTTP 500 "Cannot
  // create folder", the same error and the same SPException code the live
  // run produced. Neither other spelling escapes it: the ResourcePath call
  // is refused identically (`library.folder.add-using-path-under-validation`)
  // and an items POST is refused as "To add an item to a document library,
  // use SPFileCollection.Add()" (`library.folder.add-as-list-item-under-validation`),
  // which is the items endpoint declining libraries outright rather than a
  // way around the formula.
  //
  // So a declared save rule and a declared folder are in direct conflict on
  // a library, and this phase cannot create a folder while the rule is on.
  // The fix has to open the list, create the folders and close it again. The
  // last four rows of that probe measure whether that shape is safe.
  const FOLDER_OBJECT_TYPE = 1;
  // A server-relative path inside the quotes, spelled as the probes sent it:
  // quotes doubled, slashes and spaces left for fetch to encode. NOT
  // odataName, whose encodeURIComponent would turn every slash into %2F,
  // which no probe has sent. Names that would need more than this (`#`,
  // `%`) are refused at build by analysis/file_names.py.
  const pathLiteral = (path) => String(path).replace(/'/g, "''");
  // Absent and "a file stands here" are the SAME answer from this read.
  // MEASURED 2026-09-13, `library.folder.folder-read-on-file-path` in
  // folder-shape-probe.js: the read on a file's own path answered HTTP 200
  // with Exists false, exactly as it does for a path holding nothing
  // (`library.folder.control-missing-path-read`). So a null here means only
  // "no folder", and what is really there is asked for at the create.
  async function readFolder(serverRelativeUrl) {
    const r = await fetchWithRetry(apiUrl(`web/GetFolderByServerRelativeUrl('${pathLiteral(serverRelativeUrl)}')?$select=Exists,Name,ServerRelativeUrl`), {
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    if (r.status === 404) return null;
    if (!r.ok) {
      const text = await r.text();
      if (isAbsent400(r.status, text)) return null;
      throw new Error(`folder read failed: HTTP ${r.status} ${spError(text)}`);
    }
    const j = await r.json();
    return j && j.d && j.d.Exists ? j.d : null;
  }
  async function folderItemShape(listTitle, name) {
    const filter = encodeURIComponent(`FileLeafRef eq '${String(name).replace(/'/g, "''")}'`);
    const r = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(listTitle)}')/items?$select=Id,FileSystemObjectType,FileLeafRef&$filter=${filter}&$top=2`), {
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    if (!r.ok) throw new Error(`folder item probe failed: HTTP ${r.status} ${spError(await r.text())}`);
    const j = await r.json();
    const rows = (j && j.d && j.d.results) || [];
    return rows.length ? rows[0] : null;
  }
  for (const list of SCHEMA.lists.filter((l) => l.is_library && l.folders.length)) {
    let rootUrl = null;
    try {
      const root = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(list.title)}')/RootFolder?$select=ServerRelativeUrl`), {
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
      if (!root.ok) throw new Error(`RootFolder read failed: HTTP ${root.status} ${spError(await root.text())}`);
      const j = await root.json();
      rootUrl = j && j.d && j.d.ServerRelativeUrl;
      if (!rootUrl) throw new Error('RootFolder read back no ServerRelativeUrl');
    } catch (err) {
      log('ERROR', `Phase 2.2 folders '${list.title}': ${err.message}`);
      summary.errors.push({ phase: '2.2', list: list.title, error: err.message });
      continue;
    }
    // Which declared folders are actually missing. Asked for the whole list
    // BEFORE anything is written, because the answer decides whether the
    // library's save rule has to be lifted at all: a redeploy whose folders
    // all exist writes nothing here and never touches the rule.
    const missing = [];
    for (const name of list.folders) {
      const label = `${list.title}/${name}`;
      try {
        if (await readFolder(`${rootUrl}/${name}`)) {
          // Present already: verify it is a folder and leave its contents alone.
          const item = await folderItemShape(list.title, name);
          if (item && item.FileSystemObjectType !== FOLDER_OBJECT_TYPE) {
            throw new Error(`'${name}' is a file where a folder was declared (FileSystemObjectType ${item.FileSystemObjectType}); nothing was written`);
          }
          summary.foldersVerified.push(label);
        } else {
          missing.push(name);
        }
      } catch (err) {
        log('ERROR', `Phase 2.2 folders '${label}': ${err.message}`);
        summary.errors.push({ phase: '2.2', list: list.title, folder: name, error: err.message });
      }
    }
    if (missing.length === 0) continue;

    // Lift the declared save rule for the creates, and put it back in the
    // finally below whatever happens in between. The rule that is restored
    // is the one READ here rather than the one declared, so a rule an owner
    // has edited by hand comes back as it was rather than being quietly
    // reconciled by a phase whose job is folders.
    let listShape = null;
    let lifted = null;
    try {
      listShape = await readListShape(list.title, true);
      if (!listShape) throw new Error('the library disappeared before its folders could be created');
      assertListAdoptable(list, listShape);
      if ((listShape.ValidationFormula || '') !== '') {
        lifted = [listShape.ValidationFormula || '', listShape.ValidationMessage || ''];
        const digest = await getDigest();
        await patchListById(listShape.Id, {
          __metadata: { type: 'SP.List' },
          ValidationFormula: '',
          ValidationMessage: '',
        }, digest);
        // Registered only once the write has been sent, and before it is
        // verified: a MERGE SharePoint commits and whose response is lost
        // still has to be put back by exit cleanup.
        listValidationLiftedForRun.set(list.title, [listShape.Id, lifted[0], lifted[1]]);
        const cleared = await readListShape(list.title, true);
        if (!cleared || cleared.Id !== listShape.Id) {
          throw new Error('the library changed identity while its save rule was being lifted');
        }
        if ((cleared.ValidationFormula || '') !== '') {
          throw new Error(
            `the library's save rule did not lift (readback ${JSON.stringify(cleared.ValidationFormula)}); no folder was created`,
          );
        }
        log('INFO', `Lifted the save rule on '${list.title}' to create ${missing.length} declared folder(s).`);
      }
    } catch (err) {
      log('ERROR', `Phase 2.2 folders '${list.title}': ${err.message}`);
      summary.errors.push({ phase: '2.2', list: list.title, error: err.message });
      if (lifted !== null) {
        try {
          await restoreListValidation(list.title, listShape.Id, lifted[0], lifted[1]);
        } catch (restoreErr) {
          log('ERROR', `Could not put the save rule back on '${list.title}': ${restoreErr.message}. `
              + 'The library is accepting saves its declaration forbids; restore it in list settings.');
          summary.errors.push({ phase: '2.2', list: list.title, error: `restore the save rule: ${restoreErr.message}` });
        }
      }
      continue;
    }

    try {
      for (const name of missing) {
        const label = `${list.title}/${name}`;
        try {
          const folderUrl = `${rootUrl}/${name}`;
          const digest = await getDigest();
          // MEASURED 2026-09-13, `library.folder.add-under-existing-folder-name`
          // in folder-shape-probe.js: this call on a name a folder already holds
          // answers HTTP 200 and returns that folder, so a re-paste that raced
          // the read above creates nothing twice.
          try {
            await postJson(apiUrl(`web/GetFolderByServerRelativeUrl('${pathLiteral(rootUrl)}')/folders/add(url='${pathLiteral(name)}')`), {}, digest);
          } catch (err) {
            // Same run, `library.folder.add-under-existing-file-name`: with a
            // FILE of that name in place the call answers HTTP 404 "File Not
            // Found", which names the opposite of the problem. Ask the item
            // shape and say what is actually standing there.
            const blocking = await folderItemShape(list.title, name);
            if (blocking && blocking.FileSystemObjectType !== FOLDER_OBJECT_TYPE) {
              throw new Error(`'${name}' is a file where a folder was declared (FileSystemObjectType ${blocking.FileSystemObjectType}); nothing was written`);
            }
            throw err;
          }
          if (!(await readFolder(folderUrl))) {
            throw new Error(`'${name}' did not read back after creation`);
          }
          const item = await folderItemShape(list.title, name);
          if (!item || item.FileSystemObjectType !== FOLDER_OBJECT_TYPE) {
            throw new Error(`'${name}' read back as FileSystemObjectType ${item && item.FileSystemObjectType}, not a folder`);
          }
          summary.foldersCreated.push(label);
          logChange({ key: `folder: ${label}`, kind: 'create', target: list.title, oldValue: '', newValue: name });
          log('OK', `Created folder '${name}' in '${list.title}'.`);
        } catch (err) {
          log('ERROR', `Phase 2.2 folders '${label}': ${err.message}`);
          summary.errors.push({ phase: '2.2', list: list.title, folder: name, error: err.message });
        }
      }
    } finally {
      // A folder create that threw must not carry the lifted rule out of
      // this phase with it, so the restore is a finally rather than a line
      // after the loop. Exit cleanup is the backstop for a failure HERE.
      if (lifted !== null) {
        try {
          await restoreListValidation(list.title, listShape.Id, lifted[0], lifted[1]);
          log('INFO', `Put the save rule back on '${list.title}'.`);
        } catch (err) {
          log('ERROR', `Could not put the save rule back on '${list.title}': ${err.message}. `
              + 'The library is accepting saves its declaration forbids; restore it in list settings.');
          summary.errors.push({ phase: '2.2', list: list.title, error: `restore the save rule: ${err.message}` });
        }
      }
    }
  }
