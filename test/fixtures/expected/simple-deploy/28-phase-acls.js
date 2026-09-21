  markPhase('Phase 4.2: role inheritance and assignments');
  // === Phase 4.2: break inheritance + role assignments ===
  log('INFO', 'Starting Phase 4.2: role inheritance and assignments.');
  {
    let digest4 = await getDigest();

    // FileSystemObjectType for a folder. Declared here rather than read
    // from the folder phase's own constant: that is a different phase
    // body, and a name that resolves only when another branch has run is
    // how #454 shipped an abort that threw instead of explaining itself.
    const ACL_FOLDER_OBJECT_TYPE = 1;

    // Cache resolved IDs across assignments to avoid redundant fetches.
    const principalIdCache = {};
    const roleDefIdCache = {};

    async function resolvePrincipalId(principal) {
      const cacheKey = JSON.stringify(principal);
      if (principalIdCache[cacheKey] !== undefined) return principalIdCache[cacheKey];
      let id;
      if (principal.kind === 'group') {
        const r = await fetchWithRetry(apiUrl(`web/sitegroups/getbyname('${odataName(principal.name)}')?$select=Id`), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!r.ok) throw new Error(`Group '${principal.name}' not found (HTTP ${r.status})`);
        const j = await r.json();
        id = j.d.Id;
      } else if (principal.kind === 'associated_owner_group') {
        const r = await fetchWithRetry(apiUrl('web/AssociatedOwnerGroup?$select=Id'), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!r.ok) throw new Error(`AssociatedOwnerGroup not found (HTTP ${r.status})`);
        const j = await r.json();
        id = j.d.Id;
      } else if (principal.kind === 'associated_member_group') {
        const r = await fetchWithRetry(apiUrl('web/AssociatedMemberGroup?$select=Id'), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!r.ok) throw new Error(`AssociatedMemberGroup not found (HTTP ${r.status})`);
        const j = await r.json();
        id = j.d.Id;
      } else if (principal.kind === 'associated_visitor_group') {
        const r = await fetchWithRetry(apiUrl('web/AssociatedVisitorGroup?$select=Id'), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!r.ok) throw new Error(`AssociatedVisitorGroup not found (HTTP ${r.status})`);
        const j = await r.json();
        id = j.d.Id;
      } else {
        throw new Error(`Unknown principal kind: ${principal.kind}`);
      }
      principalIdCache[cacheKey] = id;
      return id;
    }

    async function resolveRoleDefId(levelName) {
      if (roleDefIdCache[levelName] !== undefined) return roleDefIdCache[levelName];
      const r = await fetchWithRetry(apiUrl(`web/roledefinitions/getbyname('${odataName(levelName)}')?$select=Id`), {
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
      if (!r.ok) throw new Error(`Role definition '${levelName}' not found (HTTP ${r.status})`);
      const j = await r.json();
      const id = j.d.Id;
      roleDefIdCache[levelName] = id;
      return id;
    }

    // ONE enumeration answers both descendant questions: which scopes exist
    // below this list, and which item id each declared folder has. They have
    // to come from the same read -- a guard and a writer that resolved the
    // folders separately could disagree about which scopes are expected, and
    // the guard's whole job is to abort on a scope nobody declared.
    async function surveyDescendants(listTitle, wantedFolders) {
      const rows = [];
      let itemsUrl = apiUrl(`web/lists/getbytitle('${odataName(listTitle)}')/items?$select=Id,HasUniqueRoleAssignments,FileSystemObjectType,FileRef&$top=5000`);
      while (itemsUrl) {
        const itemsResp = await fetchWithRetry(itemsUrl, {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!itemsResp.ok) {
          const text = await itemsResp.text();
          throw new Error(`item/folder permission-scope enumeration failed: HTTP ${itemsResp.status} ${text}`);
        }
        const itemsJson = await itemsResp.json();
        const next = validatedNextPage(itemsJson.d, `Item/folder permission-scope enumeration for '${listTitle}'`);
        rows.push(...((itemsJson.d && itemsJson.d.results) || []));
        itemsUrl = next;
      }
      const folderIds = new Map();
      if (wantedFolders.length > 0) {
        const rootResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(listTitle)}')/RootFolder?$select=ServerRelativeUrl`), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!rootResp.ok) {
          const text = await rootResp.text();
          throw new Error(`RootFolder read failed for '${listTitle}': HTTP ${rootResp.status} ${text}`);
        }
        const rootUrl = ((await rootResp.json()).d || {}).ServerRelativeUrl;
        if (typeof rootUrl !== 'string' || !rootUrl) {
          throw new Error(`RootFolder for '${listTitle}' returned no ServerRelativeUrl`);
        }
        // Matched on the FULL server-relative path and FileSystemObjectType,
        // never on the leaf name: a subfolder may share a leaf with a root
        // folder, and securing the wrong one reads back clean.
        for (const name of wantedFolders) {
          const wanted = `${rootUrl}/${name}`;
          const hit = rows.find(r => r.FileSystemObjectType === ACL_FOLDER_OBJECT_TYPE && r.FileRef === wanted);
          if (!hit) {
            throw new Error(`declared folder '${name}' was not found at '${wanted}'; its permissions cannot be set until the folder phase has created it`);
          }
          folderIds.set(name, hit.Id);
        }
      }
      const declared = new Set(folderIds.values());
      return {
        folderIds,
        undeclared: rows.filter(r => r.HasUniqueRoleAssignments && !declared.has(r.Id)),
      };
    }

    function assertNoUndeclaredScopes(listTitle, undeclared) {
      if (undeclared.length === 0) return;
      const sample = undeclared.slice(0, 10).map(r => `${r.Id} (${r.FileRef || 'path unknown'})`).join(', ');
      throw new Error(`${undeclared.length} undeclared item/folder unique permission scope(s) remain on '${listTitle}': ${sample}${undeclared.length > 10 ? ', ...' : ''}; review and remove them, or declare them under list_permissions.folders, before rerunning; the deployer will never erase descendant scopes`);
    }

    // Ownership was last proved by the structural phases, and everything
    // below addresses a list by title. Survey the whole batch first: a list
    // that has lost its marker or been replaced must stop the phase before
    // the lists ahead of it in the loop have their permissions rewritten.
    const aclOwned = await surveyOwnedListsForWrites(
      [...new Set([
        ...SCHEMA.list_assignments.map(la => la.list),
        ...SCHEMA.folder_assignments.map(fa => fa.list),
      ])], '4.2', 'ACL',
    );
    if (!aclOwned) {
      log('ERROR', 'ACL ownership survey failed; aborting before any role assignment changes.');
      return { ...summary, aborted: 'acl-ownership-errors' };
    }

    // Every role-assignment endpoint SharePoint documents is addressed by
    // list title; there is no by-Id form to switch these to the way a field
    // MERGE can be. What is available is to bracket the request: prove the
    // title resolves to the surveyed list immediately before it, and prove it
    // still does immediately after. A rebind can then only produce a failed
    // phase, never a grant or a removal applied to a stranger.
    const withOwnedList = async (listTitle, expectedId, what, request) => {
      await ownedListIdentity(listTitle, expectedId, `before ${what}`);
      const result = await request();
      await ownedListIdentity(listTitle, expectedId, `after ${what}`);
      return result;
    };

    // One securable at a time: a list, or one folder's list item. Every
    // endpoint below hangs off one literal base plus `scope.suffix`, the only
    // thing that differs between the two, so a list allowlist and a folder
    // allowlist cannot be reconciled by two rules that have drifted apart.
    const reconcileScope = async (scope) => {
      if (scope.break_inheritance) {
        const checkResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(scope.listTitle)}')${scope.suffix}?$select=HasUniqueRoleAssignments`), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!checkResp.ok) {
          const text = await checkResp.text();
          throw new Error(`HasUniqueRoleAssignments probe failed: HTTP ${checkResp.status} ${text}`);
        }
        const checkJson = await checkResp.json();
        if (!checkJson.d.HasUniqueRoleAssignments) {
          await withOwnedList(scope.listTitle, scope.listId, `breakroleinheritance on '${scope.label}'`, async () => {
            digest4 = await getDigest();
            const breakResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(scope.listTitle)}')${scope.suffix}/breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false)`), {
              method: 'POST',
              headers: { 'Accept': 'application/json;odata=verbose', 'X-RequestDigest': digest4 },
            });
            if (!breakResp.ok) {
              const text = await breakResp.text();
              throw new Error(`breakroleinheritance failed: HTTP ${breakResp.status} ${text}`);
            }
          });
          // MEASURED 2026-09-09, `library.access.unique-permissions-library`
          // in library-access-probe.js: on a document library the break
          // answered HTTP 200 and HasUniqueRoleAssignments read false on the
          // first read and true on the second, within 10 s, exactly as on a
          // generic list once settled. So a library is re-read until the flag
          // turns, and refused if it never does: an exact-mode allowlist
          // written onto a list that still inherits would be a no-op the
          // verify below could not tell from success.
          if (scope.settle) {
            const LIBRARY_ACL_SETTLE_MS = 2000;
            let unique = false;
            for (let attempt = 0; attempt < 5 && !unique; attempt += 1) {
              if (attempt > 0) await sleep(LIBRARY_ACL_SETTLE_MS);
              const again = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(scope.listTitle)}')${scope.suffix}?$select=HasUniqueRoleAssignments`), {
                headers: { 'Accept': 'application/json;odata=verbose' },
              });
              if (!again.ok) {
                const text = await again.text();
                throw new Error(`HasUniqueRoleAssignments re-read failed: HTTP ${again.status} ${text}`);
              }
              unique = Boolean((await again.json()).d.HasUniqueRoleAssignments);
            }
            if (!unique) {
              throw new Error(`'${scope.label}' still reads HasUniqueRoleAssignments=false after breakroleinheritance; refusing to write an allowlist onto a library that inherits`);
            }
          }
          log('INFO', `[Phase 4.2] Broke inheritance on '${scope.label}'.`);
        } else {
          log('INFO', `[Phase 4.2] '${scope.label}' already has unique role assignments, reconciling existing bindings.`);
        }
      }

      // Resolve the complete desired state before removing anything. If a
      // principal or role cannot be resolved, fail closed without partially
      // applying an allowlist that could lock out the intended administrators.
      const resolvedAssignments = [];
      for (const assignment of scope.assignments) {
        try {
          const principalId = await resolvePrincipalId(assignment.principal);
          const roleDefId = await resolveRoleDefId(assignment.level);
          resolvedAssignments.push({ assignment, principalId, roleDefId });
        } catch (err) {
          throw new Error(`cannot resolve desired assignment principal=${JSON.stringify(assignment.principal)}, level=${assignment.level}: ${err.message}`);
        }
      }

      // The one irreversible operation in this phase, so it carries the
      // strictest bracket: nothing is removed unless the title still
      // resolves to the surveyed list at the moment of the request.
      const removeBinding = async (principalId, roleDefId, reason) => {
        await withOwnedList(scope.listTitle, scope.listId, `removeroleassignment (${reason}) on '${scope.label}'`, async () => {
          digest4 = await getDigest();
          const rmResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(scope.listTitle)}')${scope.suffix}/roleassignments/removeroleassignment(principalid=${principalId},roleDefId=${roleDefId})`), {
            method: 'POST',
            headers: { 'Accept': 'application/json;odata=verbose', 'X-RequestDigest': digest4 },
          });
          if (!rmResp.ok) {
            const text = await rmResp.text();
            throw new Error(`removeroleassignment (${reason}, principal ${principalId}, binding ${roleDefId}) failed: HTTP ${rmResp.status} ${text}`);
          }
        });
        log('INFO', `[Phase 4.2] '${scope.label}' removed ${reason} binding ${roleDefId} for principal ${principalId}.`);
      };

      // Establish every desired grant before pruning. This keeps at least the
      // declared owner path in place when breakroleinheritance(false) has
      // temporarily granted the current operator direct Full Control. Any add
      // failure aborts the list before exact mode removes a single binding.
      // GetByPrincipalId is positional in SharePoint REST; add/remove role
      // assignment methods below use their documented named parameters.
      // ONE enumeration answers every question below. getbyprincipalid
      // answers 404 for a principal that has no assignment on this list
      // yet (which every declared principal is on a first deploy), and
      // the browser paints that red whether or not the script handles it.
      // Same treatment lists, views and site groups already get.
      //
      // Deliberately not fatal: if the enumeration is refused we fall
      // back to per-principal probing, which is noisier and still
      // correct. Exact mode below reuses this same snapshot; it was
      // taken BEFORE the adds, which changes no removal because a
      // binding this run adds is by definition declared, and exact mode
      // only removes bindings that are not.
      let existingAssignments = null;
      {
        const collected = [];
        let pageUrl = apiUrl(`web/lists/getbytitle('${odataName(scope.listTitle)}')${scope.suffix}/roleassignments?$expand=Member,RoleDefinitionBindings&$select=Member/Id,Member/Title,RoleDefinitionBindings/Id,RoleDefinitionBindings/Name`);
        let ok = true;
        while (pageUrl && ok) {
          const pageResp = await fetchWithRetry(pageUrl, {
            headers: { 'Accept': 'application/json;odata=verbose' },
          });
          if (!pageResp.ok) { ok = false; break; }
          const pageJson = await pageResp.json();
          const next = validatedNextPage(pageJson.d, `Role assignment enumeration for '${scope.label}'`);
          collected.push(...((pageJson.d && pageJson.d.results) || []));
          pageUrl = next;
        }
        if (ok) existingAssignments = collected;
      }
      const bindingsFor = (principalId) => {
        if (!existingAssignments) return null;
        const hit = existingAssignments.find(
          (a) => a.Member && a.Member.Id === principalId,
        );
        return (hit && hit.RoleDefinitionBindings && hit.RoleDefinitionBindings.results) || [];
      };

      // Which grants are missing is a question of reads, and it is settled
      // for every declared assignment before the first add: the adds are
      // independent of one another, so they go out as ONE $batch rather
      // than one POST each. breakroleinheritance above and every removal
      // below stay single, because those are ordered against the reads
      // around them.
      const missingGrants = [];
      for (const resolved of resolvedAssignments) {
        let desiredBindings = bindingsFor(resolved.principalId);
        if (desiredBindings === null) {
          const desiredResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(scope.listTitle)}')${scope.suffix}/roleassignments/getbyprincipalid(${resolved.principalId})?$expand=RoleDefinitionBindings&$select=RoleDefinitionBindings/Id`), {
            headers: { 'Accept': 'application/json;odata=verbose' },
          });
          if (desiredResp.ok) {
            const desiredJson = await desiredResp.json();
            desiredBindings = (desiredJson.d && desiredJson.d.RoleDefinitionBindings && desiredJson.d.RoleDefinitionBindings.results) || [];
          } else if (desiredResp.status === 404) {
            desiredBindings = [];
          } else {
            const text = await desiredResp.text();
            throw new Error(`desired binding probe failed: HTTP ${desiredResp.status} ${text}`);
          }
        }
        const desiredPresent = desiredBindings.some(binding => binding.Id === resolved.roleDefId);
        if (!desiredPresent) missingGrants.push(resolved);
      }
      if (missingGrants.length > 0) {
        // The bracket is no weaker for holding a batch, only wider: the
        // title is proved to be the surveyed list immediately before the
        // request and immediately after it, and every add sits inside that
        // window, including one the body budget flushes early. A rebind can
        // still only produce a failed phase, never a grant on a stranger.
        await withOwnedList(scope.listTitle, scope.listId, `addroleassignment on '${scope.label}'`, async () => {
          const addBatch = new BatchWriter({ getDigest, fetchWithRetry, apiUrl, log });
          try {
            for (const resolved of missingGrants) {
              // No body: addroleassignment takes its arguments in the URL,
              // exactly as the single POST this replaces did.
              await addBatch.add('POST', `web/lists/getbytitle('${odataName(scope.listTitle)}')${scope.suffix}/roleassignments/addroleassignment(principalid=${resolved.principalId},roleDefId=${resolved.roleDefId})`);
            }
            await addBatch.done();
          } catch (err) {
            // Still fatal for this list, and still before a single removal:
            // exact mode must never prune against a desired state it failed
            // to establish. SharePoint does not roll a ChangeSet back, so
            // some grants may have landed; the phase is rerunnable and the
            // next run reads the bindings again.
            throw new Error(`addroleassignment batch failed before reconciliation: ${err.message}`);
          }
        });
      }

      if (scope.reconcile_mode === 'exact') {
        // Exact mode treats the mapping as an allowlist. Enumerate every
        // direct role binding, including principals absent from the mapping,
        // and remove all non-declared pairs. SharePoint's derived "Limited
        // Access" binding is protected: it is created to support lower-scope
        // access and is not a direct permission grant at this list scope.
        const expected = new Set(resolvedAssignments.map(
          x => `${x.principalId}:${x.roleDefId}`,
        ));
        // Reuses the snapshot taken above when it succeeded. Exact mode
        // is an allowlist, so it must never run on a PARTIAL view of the
        // bindings: if that enumeration was refused, this one repeats it
        // and stays fatal on failure rather than pruning against
        // whatever it managed to read.
        let allAssignments = existingAssignments;
        if (allAssignments === null) {
          allAssignments = [];
          let assignmentsUrl = apiUrl(`web/lists/getbytitle('${odataName(scope.listTitle)}')${scope.suffix}/roleassignments?$expand=Member,RoleDefinitionBindings&$select=Member/Id,Member/Title,RoleDefinitionBindings/Id,RoleDefinitionBindings/Name`);
          while (assignmentsUrl) {
            const allResp = await fetchWithRetry(assignmentsUrl, {
              headers: { 'Accept': 'application/json;odata=verbose' },
            });
            if (!allResp.ok) {
              const text = await allResp.text();
              throw new Error(`role assignment enumeration failed: HTTP ${allResp.status} ${text}`);
            }
            const allJson = await allResp.json();
            const next = validatedNextPage(allJson.d, `Role assignment enumeration for '${scope.label}'`);
            allAssignments.push(...((allJson.d && allJson.d.results) || []));
            assignmentsUrl = next;
          }
        }
        // The snapshot above may have been taken before the adds; either
        // way it is the allowlist this loop prunes against, so the title it
        // was read through has to still be the surveyed list.
        await ownedListIdentity(scope.listTitle, scope.listId, `before exact-mode pruning on '${scope.label}'`);
        for (const existing of allAssignments) {
          const principalId = existing.Member && existing.Member.Id;
          if (principalId == null) {
            throw new Error('role assignment enumeration returned an entry without Member.Id');
          }
          const bindings = (existing.RoleDefinitionBindings && existing.RoleDefinitionBindings.results) || [];
          for (const binding of bindings) {
            if (binding.Name === 'Limited Access') {
              continue;
            }
            if (!expected.has(`${principalId}:${binding.Id}`)) {
              await removeBinding(principalId, binding.Id, 'unlisted');
            }
          }
        }
      } else {
        // Backward-compatible configured-principal mode: remove stale levels
        // for declared principals but leave unrelated principals untouched.
        //
        // Grouped by principal, because one principal may be declared with
        // more than one level. Per assignment, each pass treated its own
        // level as the principal's whole desired state: the pass for level A
        // removed B as stale and the pass for B removed A, off the same
        // pre-write snapshot, leaving the principal with neither.
        const desiredByPrincipal = new Map();
        for (const resolved of resolvedAssignments) {
          if (!desiredByPrincipal.has(resolved.principalId)) {
            desiredByPrincipal.set(resolved.principalId, new Set());
          }
          desiredByPrincipal.get(resolved.principalId).add(resolved.roleDefId);
        }
        for (const [principalId, wanted] of desiredByPrincipal) {
          const resolved = { principalId };
          let bindings = bindingsFor(resolved.principalId);
          if (bindings === null) {
            const raResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(scope.listTitle)}')${scope.suffix}/roleassignments/getbyprincipalid(${resolved.principalId})?$expand=RoleDefinitionBindings&$select=RoleDefinitionBindings/Id,RoleDefinitionBindings/Name`), {
              headers: { 'Accept': 'application/json;odata=verbose' },
            });
            if (raResp.ok) {
              const raJson = await raResp.json();
              bindings = (raJson.d && raJson.d.RoleDefinitionBindings && raJson.d.RoleDefinitionBindings.results) || [];
            } else if (raResp.status === 404) {
              bindings = [];
            } else {
              const text = await raResp.text();
              throw new Error(`role assignment probe failed: HTTP ${raResp.status} ${text}`);
            }
          }
          for (const binding of bindings) {
            if (binding.Name !== 'Limited Access' && !wanted.has(binding.Id)) {
              await removeBinding(principalId, binding.Id, 'stale');
            }
          }
        }
      }

      // NOT verified by re-reading the bindings here, deliberately. The
      // writes above answered HTTP 200, which is evidence the request was
      // accepted rather than that the scope now holds them, and nothing
      // downstream checks: verify.js reads lists, columns and views and
      // never role assignments. A read-back belongs here, but it cannot be
      // added on the assumption that this surface answers a write
      // immediately. The settle loop above exists because it does NOT:
      // MEASURED 2026-09-09, a library's HasUniqueRoleAssignments read false
      // on the first read after breakroleinheritance and true on the second.
      // A single post-write enumeration would turn that same lag into an
      // abort on a run that had in fact succeeded.
      // test/manual/library-access-probe.js already attaches a role
      // assignment and reads it back, but not after a batched ChangeSet and
      // not with the lag measured, which is what a settle loop here would
      // have to be sized from. Measure that before adding one.
    };

    // Folder policies may name a list whose own policy is absent, so the
    // batch is the union rather than `list_assignments` alone.
    const aclListTitles = [...new Set([
      ...SCHEMA.list_assignments.map(la => la.list),
      ...SCHEMA.folder_assignments.map(fa => fa.list),
    ])];

    for (const listTitle of aclListTitles) {
      log('INFO', `[Phase 4.2] Processing role assignments for '${listTitle}'...`);
      try {
        const la = SCHEMA.list_assignments.find(x => x.list === listTitle);
        const folderAssignments = SCHEMA.folder_assignments.filter(fa => fa.list === listTitle);
        const wantedFolders = folderAssignments.map(fa => fa.folder);
        const aclListId = aclOwned.get(listTitle);
        // Before the first READ, not just the first write: exact mode turns
        // the enumeration below into a removal list, so a snapshot taken from
        // the wrong object is as dangerous as a write to it.
        await ownedListIdentity(listTitle, aclListId, `before reading ACL state for '${listTitle}'`);
        const exact = (la && la.reconcile_mode === 'exact')
          || folderAssignments.some(fa => fa.reconcile_mode === 'exact');
        // Probe before *any* ACL mutation on this list. breakroleinheritance
        // with clearSubscopes=true would silently erase descendant exceptions
        // on an adopted/populated inheriting list before the old post-check
        // saw them. Exact mode always fails closed and leaves those scopes
        // untouched. A folder this bundle declares is not such a scope: it is
        // one this phase is about to write, so it is excluded by
        // `surveyDescendants` rather than by a second rule here.
        // The survey pages every item in the list, so it runs only when its
        // answer is read: exact mode needs the descendant guard, and a folder
        // policy needs the item id it resolves. A configured-mode list with no
        // folder policy would otherwise enumerate a populated production
        // library for a result nothing uses, and can meet the list view
        // threshold doing it. This is the condition the pre-folder code met
        // implicitly by surveying only in exact mode.
        const before = (exact || folderAssignments.length > 0)
          ? await surveyDescendants(listTitle, wantedFolders)
          : { folderIds: new Map(), undeclared: [] };
        if (exact) assertNoUndeclaredScopes(listTitle, before.undeclared);
        if (la) {
          await reconcileScope({
            // The empty suffix IS the list: every endpoint below hangs off
            // the same literal base, so the folder path is visibly a
            // sub-path of the list rather than a second URL family.
            listTitle, listId: aclListId, label: listTitle, suffix: '',
            assignments: la.assignments,
            break_inheritance: la.break_inheritance,
            reconcile_mode: la.reconcile_mode,
            settle: (SCHEMA.lists.find((l) => l.title === listTitle) || {}).is_library === true,
          });
        }
        // After the list, never before: the folder breaks from the list's
        // ACL, so reconciling the parent first is what the folder inherits
        // from in the window between the two.
        for (const fa of folderAssignments) {
          await reconcileScope({
            listTitle, listId: aclListId,
            label: `${listTitle}/${fa.folder}`,
            suffix: `/items(${before.folderIds.get(fa.folder)})`,
            assignments: fa.assignments,
            break_inheritance: fa.break_inheritance,
            reconcile_mode: fa.reconcile_mode,
            // A folder is only ever in a library, so it takes the same
            // settle wait the library's own break takes.
            settle: true,
          });
        }
        if (exact) {
          // List-level exact reconciliation is insufficient when a prior run
          // or manual change left item/folder scopes behind. SharePoint does
          // not clear descendant scopes when BreakRoleInheritance is called
          // again on a list that is already unique. Detect those scopes and
          // fail closed for operator review; never erase a potentially
          // deliberate exception automatically. Re-surveyed rather than
          // reusing `before`, because the folder pass above has just created
          // the scopes this run does declare.
          assertNoUndeclaredScopes(
            listTitle,
            (await surveyDescendants(listTitle, wantedFolders)).undeclared,
          );
        }

      } catch (err) {
        log('ERROR', `[Phase 4.2] '${listTitle}': ${err.message}`);
        summary.errors.push({ phase: '4.2', list: listTitle, error: err.message });
      }
    }
  }

  // A partial schema or ACL deployment must never be made to look activated
  // by seeding AppSettings. The error summary remains the operator's
  // repair checklist and the rerunnable deployment can be attempted again.
  if (summary.errors.length > 0) {
    log('ERROR', 'Deployment has unresolved schema or ACL errors; aborting before seed items.');
    return { ...summary, aborted: 'pre-seed-errors' };
  }
