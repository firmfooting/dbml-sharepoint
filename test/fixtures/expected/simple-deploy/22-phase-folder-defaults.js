  markPhase('Phase 2.3: folder default values');
  // === Phase 2.3: folder default values ===
  log('INFO', 'Starting Phase 2.3: folder default values.');
  // `library.folder-defaults.declare-writes-readback`: the file
  // Forms/client_LocationBasedDefaults.html takes a Files/add(overwrite=true)
  // of <MetadataDefaults><a href="<folder path>"><DefaultValue FieldName="<internal
  // name>">value</DefaultValue></a></MetadataDefaults> and reads back as the
  // text written. Whether SharePoint applies the stored values to an upload is
  // not established, so this phase proves the file and nothing past it.
  // `overwrite=true` replaces the whole file, so the new text is built from the
  // existing entries (kept verbatim unless their folder is declared) and read
  // back after the write.
  const DEFAULTS_FILE = 'client_LocationBasedDefaults.html';
  const xmlEscape = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const xmlUnescape = (s) => String(s).replace(/&quot;/g, '"').replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>').replace(/&amp;/g, '&');
  // Entries are matched as text, not parsed as DOM: the file holds nothing else
  // of interest and a preserved entry must come back byte for byte.
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
      if (settled) continue;
      const kept = existing.filter((e) => !declaredPaths.has(e.path)).map((e) => e.raw);
      const written = [...wanted.entries()].filter(([, values]) => values.length).map(([path, values]) =>
        `<a href="${xmlEscape(path)}">${values.map((v) =>
          `<DefaultValue FieldName="${xmlEscape(v.field)}">${xmlEscape(v.value)}</DefaultValue>`).join('')}</a>`);
      const text = `<MetadataDefaults>${[...kept, ...written].join('')}</MetadataDefaults>`;
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
      log('OK', `Wrote folder defaults for '${list.title}' (${wanted.size} folder(s) declared).`);
      logChange({ key: `list-setting:${list.title}:folder-defaults`, kind: 'list-setting', target: list.title,
        oldValue: `${existing.length} entr${existing.length === 1 ? 'y' : 'ies'}`,
        newValue: `${kept.length + written.length} entr${kept.length + written.length === 1 ? 'y' : 'ies'}` });
    } catch (err) {
      log('ERROR', `Phase 2.3 folder defaults '${list.title}': ${err.message}`);
      summary.errors.push({ phase: '2.3', list: list.title, error: err.message });
    }
  }
