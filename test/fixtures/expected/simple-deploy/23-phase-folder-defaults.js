  markPhase('Phase 2.3: folder default values');
  // === Phase 2.3: folder default values ===
  log('INFO', 'Starting Phase 2.3: folder default values.');
  // The stored file applies nothing until the library has the location-based defaults ItemAdded receiver, which is registered once the file is reconciled.
  const DEFAULTS_RECEIVER_CLASS = 'Microsoft.Office.DocumentManagement.LocationBasedMetadataDefaultsReceiver';
  const DEFAULTS_RECEIVER_ASSEMBLY = 'Microsoft.Office.DocumentManagement, Version=16.0.0.0, Culture=neutral, PublicKeyToken=71e9bce111e9429c';
  const ITEM_ADDED = 10001;
  const readReceivers = async (title) => {
    const r = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(title)}')/EventReceivers?$select=ReceiverClass,EventType,Synchronization`), {
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    if (!r.ok) throw new Error(`event receiver read failed: HTTP ${r.status} ${spError(await r.text())}`);
    const results = (((await r.json()) || {}).d || {}).results;
    // Fail before registering: an unreadable collection must not look like an absent receiver.
    if (!Array.isArray(results)) throw new Error('event receiver read returned no collection');
    return results;
  };
  // Synchronization 1 is synchronous; 0 and 2 run the receiver after the upload is visible.
  const defaultsReceivers = (receivers) => receivers.filter((e) => e.ReceiverClass === DEFAULTS_RECEIVER_CLASS && e.EventType === ITEM_ADDED);
  const hasDefaultsReceiver = (receivers) => defaultsReceivers(receivers).some((e) => e.Synchronization === 1);
  async function reconcileDefaultsReceiver(list) {
    const present = await readReceivers(list.title);
    if (hasDefaultsReceiver(present)) return;
    if (defaultsReceivers(present).length) {
      throw new Error('the library has a location-based defaults event receiver that is not synchronous; remove it in the site so the deploy can register the synchronous one');
    }
    await assertDeclaredListOwnedNow(list.title);
    const put = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(list.title)}')/EventReceivers`), {
      method: 'POST',
      headers: { 'Accept': 'application/json;odata=verbose', 'Content-Type': 'application/json;odata=verbose', 'X-RequestDigest': await getDigest() },
      body: JSON.stringify({
        __metadata: { type: 'SP.EventReceiverDefinition' },
        ReceiverName: 'LocationBasedMetadataDefaultsReceiver ItemAdded', EventType: ITEM_ADDED,
        ReceiverAssembly: DEFAULTS_RECEIVER_ASSEMBLY, ReceiverClass: DEFAULTS_RECEIVER_CLASS,
        SequenceNumber: 1000, Synchronization: 1,
      }),
    });
    if (!put.ok) throw new Error(`event receiver registration failed: HTTP ${put.status} ${spError(await put.text())}`);
    if (!hasDefaultsReceiver(await readReceivers(list.title))) {
      throw new Error('the location-based defaults event receiver did not read back after registration');
    }
    log('OK', `Registered the location-based defaults event receiver on '${list.title}'.`);
    logChange({ key: `list-setting:${list.title}:folder-defaults-receiver`, kind: 'list-setting', target: list.title,
      oldValue: 'absent', newValue: 'registered' });
  }
  const DEFAULTS_FILE = 'client_LocationBasedDefaults.html';
  const xmlEscape = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const xmlUnescape = (s) => String(s).replace(/&quot;/g, '"').replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>').replace(/&amp;/g, '&');
  // Entries are matched as text, not parsed as DOM, so a preserved entry comes back byte for byte.
  function parseFolderDefaults(text) {
    const whole = String(text).trim();
    if (whole === '') return [];
    const shell = /^<MetadataDefaults\s*>([\s\S]*)<\/MetadataDefaults>$/.exec(whole);
    if (!shell) {
      if (/^<MetadataDefaults\s*\/>$/.test(whole)) return [];
      throw new Error('the existing defaults file is not a MetadataDefaults document; it was left alone');
    }
    const entries = [];
    const rest = shell[1].replace(/<a\s+href="([^"]*)"\s*>([\s\S]*?)<\/a>/g, (raw, href, inner) => {
      const values = new Map();
      for (const m of inner.matchAll(/<DefaultValue\s+FieldName="([^"]*)"\s*>([\s\S]*?)<\/DefaultValue>/g)) {
        values.set(xmlUnescape(m[1]), xmlUnescape(m[2]));
      }
      let path = xmlUnescape(href);
      try { path = decodeURIComponent(path); } catch { /* keep the text as stored */ }
      entries.push({ path, raw, values });
      return '';
    });
    if (rest.trim() !== '') {
      throw new Error('the existing defaults file holds content this deploy does not recognise; it was left alone');
    }
    return entries;
  }
  const sameValues = (have, want) => have.size === want.length
    && want.every((v) => have.get(v.field) === v.value);
  for (const list of SCHEMA.lists.filter((l) => l.is_library && (l.folder_defaults || []).length)) {
    try {
      const root = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(list.title)}')/RootFolder?$select=ServerRelativeUrl`), {
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
      if (!root.ok) throw new Error(`RootFolder read failed: HTTP ${root.status} ${spError(await root.text())}`);
      const rootUrl = (((await root.json()) || {}).d || {}).ServerRelativeUrl;
      if (typeof rootUrl !== 'string' || !rootUrl.startsWith('/') || rootUrl.endsWith('/')) {
        throw new Error('RootFolder read back no valid ServerRelativeUrl');
      }
      const fileUrl = `${rootUrl}/Forms/${DEFAULTS_FILE}`;
      const read = async () => {
        const r = await fetchWithRetry(apiUrl(`web/GetFileByServerRelativeUrl('${pathLiteral(fileUrl)}')/$value`));
        if (r.status === 404) return '';
        if (!r.ok) throw new Error(`defaults file read failed: HTTP ${r.status} ${spError(await r.text())}`);
        return r.text();
      };
      const before = await read();
      const existing = parseFolderDefaults(before);
      const declaredPaths = new Set(list.folders.map((name) => `${rootUrl}/${name}`));
      const wanted = new Map(list.folder_defaults.map((d) => [`${rootUrl}/${d.folder}`, d.values]));
      const settled = [...declaredPaths].every((path) => {
        const have = existing.find((e) => e.path === path);
        const want = wanted.get(path) || [];
        return have ? sameValues(have.values, want) : want.length === 0;
      });
      if (settled) {
        // After the file is reconciled, so a failed reconcile never leaves stale defaults live.
        await reconcileDefaultsReceiver(list);
        continue;
      }
      const kept = existing.filter((e) => !declaredPaths.has(e.path)).map((e) => e.raw);
      const written = [...wanted.entries()].filter(([, values]) => values.length).map(([path, values]) =>
        `<a href="${xmlEscape(path)}">${values.map((v) =>
          `<DefaultValue FieldName="${xmlEscape(v.field)}">${xmlEscape(v.value)}</DefaultValue>`).join('')}</a>`);
      const text = `<MetadataDefaults>${[...kept, ...written].join('')}</MetadataDefaults>`;
      // Immediately before the overwrite: a same-titled library that replaced ours is not written.
      await assertDeclaredListOwnedNow(list.title);
      const digest = await getDigest();
      const put = await fetchWithRetry(apiUrl(`web/GetFolderByServerRelativeUrl('${pathLiteral(`${rootUrl}/Forms`)}')/Files/add(url='${DEFAULTS_FILE}',overwrite=true)`), {
        method: 'POST',
        headers: { 'Accept': 'application/json;odata=verbose', 'X-RequestDigest': digest },
        body: text,
      });
      if (!put.ok) throw new Error(`defaults file write failed: HTTP ${put.status} ${spError(await put.text())}`);
      if ((await read()) !== text) {
        throw new Error('the defaults file did not read back as written');
      }
      await reconcileDefaultsReceiver(list);
      log('OK', `Wrote folder defaults for '${list.title}' (${wanted.size} folder(s) declared).`);
      logChange({ key: `list-setting:${list.title}:folder-defaults`, kind: 'list-setting', target: list.title,
        oldValue: `${existing.length} entr${existing.length === 1 ? 'y' : 'ies'}`,
        newValue: `${kept.length + written.length} entr${kept.length + written.length === 1 ? 'y' : 'ies'}` });
    } catch (err) {
      log('ERROR', `Phase 2.3 folder defaults '${list.title}': ${err.message}`);
      summary.errors.push({ phase: '2.3', list: list.title, error: err.message });
    }
  }
