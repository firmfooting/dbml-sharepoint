  markPhase('Phase 3.3: hidden field links');
  // === Phase 3.3: hidden field links ===
  // A calculated column leaves the Edit and Display form only through Hidden
  // on its content type's field link, which REST cannot write (PATCH on
  // SP.FieldLink is refused), so the write is CSOM. The default item content
  // type is the target (a library's Document, a list's Item), as in form
  // formatting. Two-way: an undeclared column is un-hidden.
  log('INFO', 'Starting Phase 3.3: hidden field links.');
  {
    const linksOwned = SCHEMA.field_links.length > 0
      ? await surveyOwnedListsForWrites(
        SCHEMA.field_links.map((row) => row.list), '3.3', 'Field link',
      )
      : new Map();
    if (!linksOwned) {
      log('ERROR', 'Field-link ownership survey failed; aborting before any field link is written.');
      return { ...summary, aborted: 'field-link-ownership-errors' };
    }
    const linkRows = async (path, what, size) => {
      const resp = await fetchWithRetry(apiUrl(path), { headers: { 'Accept': 'application/json;odata=verbose' } });
      if (!resp.ok) throw new Error(`${what}: HTTP ${resp.status} ${spError(await resp.text())}`);
      const page = (await resp.json()).d;
      const rows = resultsOf(page, what);
      if (pageTruncated(rows, validatedNextPage(page, what), size)) {
        throw new Error(`${what}: the page may be truncated, so a missing field link cannot be read as absent`);
      }
      return rows;
    };
    for (const row of SCHEMA.field_links) {
      try {
        const listId = sharePointGuid(surveyedListId(linksOwned, row.list, 'Field link'), 'list');
        const listPath = `web/lists(guid'${listId}')`;
        const cts = await linkRows(`${listPath}/contenttypes?$select=Name,StringId&$top=${CONTENT_TYPE_PAGE_SIZE}`,
          `Content-type read for '${row.list}'`, CONTENT_TYPE_PAGE_SIZE);
        const ct = cts.find((c) => c.StringId && c.StringId.startsWith('0x01') && !c.StringId.startsWith('0x0120'));
        if (!ct) throw new Error('no default item content type found on the list');
        const linksPath = `${listPath}/contenttypes('${ct.StringId}')/fieldlinks?$select=Id,Name,Hidden&$top=${FIELD_PAGE_SIZE}`;
        const readLinks = async () => new Map((await linkRows(linksPath, `Field-link read for '${row.list}'`, FIELD_PAGE_SIZE))
          .map((link) => [link.Name, link]));
        const before = await readLinks();
        // A column with no link is on no form, so only a hide has anything to fail on.
        const drifted = Object.entries(row.hidden).filter(([name, hidden]) =>
          before.has(name) ? before.get(name).Hidden !== hidden : hidden);
        for (const [name, hidden] of drifted) {
          if (!before.has(name)) throw new Error(`'${name}' has no field link on the default item content type, so it cannot be hidden`);
          await ownedListIdentity(row.list, listId, `before writing the field link of '${name}'`);
          const csomError = await processQuery(
            `<SetProperty Id="10" ObjectPathId="7" Name="Hidden"><Parameter Type="Boolean">${hidden}</Parameter></SetProperty>`
            // false: true errors on a list content type, which has no children.
            + '<Method Name="Update" Id="11" ObjectPathId="5"><Parameters><Parameter Type="Boolean">false</Parameter></Parameters></Method>',
            '<StaticProperty Id="0" TypeId="{3747adcd-a3c3-41b9-bfab-4a64dd2f1e0a}" Name="Current" />'
            + '<Property Id="1" ParentId="0" Name="Web" />'
            + '<Property Id="2" ParentId="1" Name="Lists" />'
            + `<Method Id="3" ParentId="2" Name="GetById"><Parameters><Parameter Type="Guid">{${listId}}</Parameter></Parameters></Method>`
            + '<Property Id="4" ParentId="3" Name="ContentTypes" />'
            + `<Method Id="5" ParentId="4" Name="GetById"><Parameters><Parameter Type="String">${ct.StringId}</Parameter></Parameters></Method>`
            + '<Property Id="6" ParentId="5" Name="FieldLinks" />'
            + `<Method Id="7" ParentId="6" Name="GetById"><Parameters><Parameter Type="Guid">{${sharePointGuid(before.get(name).Id, 'field link')}}</Parameter></Parameters></Method>`,
          );
          if (csomError !== null) throw new Error(`'${name}' field link was not written: ${csomError}`);
        }
        if (drifted.length > 0) {
          const after = await readLinks();
          const stale = drifted.filter(([name, hidden]) => after.has(name) && after.get(name).Hidden !== hidden);
          if (stale.length > 0) {
            throw new Error(`did not retain the declared Hidden on ${stale.map(([name]) => name).join(', ')}`);
          }
        }
        log('INFO', `[Phase 3.3] Field links on '${row.list}' verified (${drifted.length} changed).`);
      } catch (err) {
        log('ERROR', `Phase 3.3 field links '${row.list}': ${err.message}`);
        summary.errors.push({ phase: '3.3', list: row.list, error: err.message });
      }
    }
  }
