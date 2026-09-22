# test/test_jsgen_security.py
"""Permission levels, site groups, ACLs, and the markers that identify them.

A matching name is not evidence that this tool made the object, so the
deploy adopts a level or a group by the marker in its description and fails
closed otherwise. The same phases break inheritance, reconcile exact-mode
allowlists and enrol the operator, and every one of them is a write against
somebody's live site.
"""

import dataclasses
from pathlib import Path
from typing import Any

from _builders import ID_PK, TITLE, table
from _packs import blocks, pack, write_mapping
from _paths import FIXTURES
from test_jsgen import _generate_simple_js, _schema_json_for

from dbml_sharepoint.analysis.group_description import marker_for_group
from dbml_sharepoint.analysis.groups import declared_groups
from dbml_sharepoint.analysis.list_description import family_for
from dbml_sharepoint.analysis.phases import phase_number as pn
from dbml_sharepoint.analysis.provenance import MARKER_PREFIX
from dbml_sharepoint.analysis.role_definition_description import marker_for_level
from dbml_sharepoint.generators.jsgen import build_schema_json, generate_deploy_js
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import (
    EntityMapping,
    GroupsFromEnum,
    PermissionsConfig,
    SiteGroup,
)
from dbml_sharepoint.model.parser import parse_dbml
from dbml_sharepoint.model.release import load_release


def test_schema_json_has_permission_keys() -> None:
    """SCHEMA literal in generated JS must include permission_levels, groups,
    acl_scopes keys (R5)."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    schema_json = build_schema_json(schema, bundle, "default")

    assert "permission_levels" in schema_json
    assert "groups" in schema_json
    assert "acl_scopes" in schema_json

    # Fixture has one custom level and one group.
    assert len(schema_json["permission_levels"]) == 1
    assert schema_json["permission_levels"][0]["name"] == "Schema Manager"
    assert "high" in schema_json["permission_levels"][0]["base_permissions"]
    assert "low" in schema_json["permission_levels"][0]["base_permissions"]

    assert len(schema_json["groups"]) == 1
    assert schema_json["groups"][0]["name"] == "List Maintainer"
    assert schema_json["groups"][0]["require_empty_at_deploy"] is True

    # All default-role lists should have assignments.
    list_scopes = [s for s in schema_json["acl_scopes"] if not s.get("folder")]
    assert len(list_scopes) == 3
    assert all(item["reconcile_mode"] == "exact" for item in list_scopes)
    list_names = {la["list"] for la in list_scopes}
    assert "APP_Project" in list_names
    assert "APP_Task" in list_names
    assert "APP_AppSettings" in list_names

    # The single boolean deploy.js's own preflight and the manifest both
    # key off (#166 item 5) -- this fixture declares levels, groups AND
    # assignments, so it must be True regardless of which one drove it.
    assert schema_json["requires_manage_permissions"] is True


def test_acl_scopes_emits_each_list_scope_before_its_own_folder_scopes(
    tmp_path: Path,
) -> None:
    """One collection, and the order is the contract: a list scope, then that
    list's folders, in list creation order. A consumer reading the rows in
    order sees a library before anything inside it."""
    schema, bundle = pack(
        tmp_path,
        dbml=(
            'Enum division {\n  "Clinical services"\n  "Corporate services"\n}\n'
            + table("Docs", ID_PK, TITLE, "Division division")
        ),
        mapping="""
            entities:
              Docs:
                kind: DocumentLibrary
                base_template: 101
                site_role: default
                folders: {from_enum: division}

            permission_levels:
              - name: "Folder Editor"
                description: "Edit inside one folder."
                base_permissions: [ViewListItems, AddListItems, EditListItems]

            groups:
              - name: "Librarians"
                description: "Library maintainers."
                owner_group: "Site Owners"
              - from_enum: division
                name: "{member} Editors"
                description: "Editors for {member}."
                owner_group: "Site Owners"

            list_permissions:
              overrides:
                Docs:
                  break_inheritance: true
                  reconcile: exact
                  assignments:
                    - principal: { kind: group, name: "Librarians" }
                      level: "Folder Editor"
              folders:
                Docs:
                  break_inheritance: true
                  reconcile: exact
                  assignments:
                    - principal: { kind: group, name: "{member} Editors" }
                      level: "Folder Editor"
        """,
    )

    out = build_schema_json(schema, bundle, "default")

    assert "list_assignments" not in out
    assert "folder_assignments" not in out

    docs = bundle.mapping.list_title("Docs")
    shape = [(row["list"], row.get("folder")) for row in out["acl_scopes"]]
    assert shape == [
        (docs, None),
        (docs, "Clinical services"),
        (docs, "Corporate services"),
    ], shape
    # Absent, not null: every JavaScript consumer filters on `!s.folder`.
    assert "folder" not in out["acl_scopes"][0]


def _schema_json_for_risk_register() -> dict[str, Any]:
    """Build SCHEMA for the shipped risk-register family, whose mapping
    declares all three group shapes: a family-owned group and both
    tool-owned ones."""
    return _schema_json_for("risk-register")


def test_every_emitted_group_description_carries_the_marker() -> None:
    """#211: nothing on a group recorded that this tool made it."""
    schema_json = _schema_json_for_risk_register()
    groups = schema_json["groups"]
    assert groups, "fixture declares no groups; the assertion would be vacuous"
    for grp in groups:
        assert MARKER_PREFIX in grp["description"], grp["name"]


def test_the_shared_group_marker_names_no_family() -> None:
    schema_json = _schema_json_for_risk_register()
    shared = next(g for g in schema_json["groups"] if g["name"] == "dbml Enterprise Readers")
    assert shared["description"].endswith(
        "Provisioned by dbml-sharepoint for group dbml Enterprise Readers."
    )


def test_a_family_group_marker_names_its_family() -> None:
    schema_json = _schema_json_for_risk_register()
    owned = next(g for g in schema_json["groups"] if g["name"] == "RR Risk Managers")
    assert owned["description"].endswith(
        "Provisioned by dbml-sharepoint from risk-register for group RR Risk Managers.",
    )


def test_each_group_carries_its_own_expected_marker() -> None:
    """The deploy gate compares this per group, not the shared prefix every
    family's marker happens to start with."""
    schema_json = _schema_json_for_risk_register()
    for grp in schema_json["groups"]:
        assert grp["expected_marker"] == marker_for_group(grp["name"], "risk-register")


def test_every_emitted_level_description_carries_the_marker() -> None:
    """risk-register declares no permission levels, so this loads
    change-register, which declares 'CH Submit Only'."""
    schema_json = _schema_json_for("change-register")
    levels = schema_json["permission_levels"]
    assert levels, "fixture declares no permission levels; the assertion would be vacuous"
    for lvl in levels:
        assert lvl["description"].endswith(
            "Provisioned by dbml-sharepoint from change-register for level " + lvl["name"] + ".",
        ), lvl["name"]


def test_each_level_carries_its_own_expected_marker() -> None:
    schema_json = _schema_json_for("change-register")
    levels = schema_json["permission_levels"]
    assert levels, "fixture declares no permission levels; the assertion would be vacuous"
    for lvl in levels:
        assert lvl["expected_marker"] == marker_for_level("change-register", lvl["name"])


def _acl_phase(js: str) -> str:
    """Phase 4.2's own text, from its banner to the next phase's.

    A search over the whole script answers for templates this one has nothing
    to do with: `_reader_enrolment.js.j2` names `roleassignments/getbyprincipalid`
    in a comment, and the simple fixture omits it only for want of an
    enterprise reader.
    """
    return js.split(f"Starting Phase {pn('acls')}")[1].split(
        f"Starting Phase {pn('seeds')}")[0]


def test_exact_acl_reconciliation_removes_unlisted_principals() -> None:
    """Exact mode is a real allowlist, not just stale-level cleanup for the
    principals that happen to be declared in the mapping."""
    js = _generate_simple_js()
    assert "reconcile_mode" in js
    assert "roleassignments?$expand=RoleDefinitionBindings" in js
    assert "const desired = new Set" in js
    assert "removeBinding(row.principalId, row.roleDefId, 'unlisted')" in js
    assert "row.name === 'Limited Access'" in js
    assert "const next = validatedNextPage(json.d," in js
    assert "cannot resolve desired assignment" in js
    assert js.index("addroleassignment") < js.index(
        "Exact mode treats the mapping as an allowlist",
    )
    assert "failed before reconciliation" in js


def test_role_assignment_writes_keep_their_named_parameters() -> None:
    """SharePoint's add and remove methods take named parameters. The
    positional read method they were paired against is gone: every read now
    goes through the one collection enumeration."""
    js = _generate_simple_js()

    assert "roleassignments/getbyprincipalid" not in _acl_phase(js)
    assert "addroleassignment(principalid=${resolved.principalId}" in js
    assert "removeroleassignment(principalid=${principalId}" in js


# === New tests for Feature A (owner verification) and Feature B (Phase 5.1 seed) ===


def test_deploy_js_hardens_permission_and_role_checks() -> None:
    """Template hardening guards:
    - permission preflight demands ManagePermissions only when the schema has
      ACL work (needsPermissions), not unconditionally;
    - Phase 1.3 role-definition / site-group existence probes surface non-404
      responses as errors rather than treating them as "already exists";
    - Phase 4.2 addroleassignment / breakroleinheritance and the Phase 1.3 group
      owner reads all validate the HTTP result (fetch does not throw on 4xx/5xx).
      The adds travel as one $batch, so the status each part came back with is
      what BatchWriter inspects, and its refusal has to stay fatal here.
    """
    js = _generate_simple_js()
    assert "needsPermissions" in js
    assert "Probe for permission level" in js
    assert "Probe for site group" in js
    assert "addroleassignment batch failed before reconciliation" in js
    assert "failed before reconciliation" in js
    assert "breakroleinheritance failed" in js
    assert "/owner?$select=Id,Title,PrincipalType" in js
    assert "Cannot read owner for group" in js


def test_group_owner_is_verified_read_only_and_mismatch_fails_closed() -> None:
    """Never write read-only OwnerTitle or guess a REST Owner POST payload."""
    js = _generate_simple_js()

    assert "Manual owner action required for group" in js
    assert f"Phase {pn('lists')} will not start while this mismatch exists" in js
    assert "owner verified as" in js
    assert "OwnerTitle:" not in js
    assert "owner MERGE failed" not in js
    assert js.index("Manual owner action required for group") < js.index(
        "phase-0-security-errors",
    )


def test_deploy_js_reconciles_named_security_objects_and_fails_closed() -> None:
    """A matching name is not sufficient security evidence.

    Existing custom role definitions and groups must have their declared
    permissions/membership controls reconciled. Any Phase 1.3 failure must stop
    before list creation, and any later schema/ACL failure must stop before a
    seed row can make a partial deployment appear activated.
    """
    js = _generate_simple_js()

    assert "Permission level '${lvl.name}' MERGE failed" in js
    assert "declared permissions reconciled" in js
    assert "Group '${grp.name}' settings MERGE failed" in js
    assert "declared membership controls reconciled" in js
    assert "phase-0-security-errors" in js
    assert js.index("phase-0-security-errors") < js.index(f"Starting Phase {pn('lists')}")
    assert "pre-seed-errors" in js
    assert js.index("pre-seed-errors") < js.index(f"Starting Phase {pn('seeds')}")


def test_required_empty_group_is_paginated_and_fails_before_phase_1() -> None:
    """The optional bootstrap gate observes membership without mutating it."""
    js = _generate_simple_js()

    assert '"require_empty_at_deploy": true' in js
    assert "/users?$select=Id&$top=5000" in js
    assert "while (membersUrl)" in js
    assert "const next = validatedNextPage(membersJson.d," in js
    assert "membersUrl = next;" in js
    assert "requires empty membership at deploy" in js
    assert "membership enumeration failed" in js
    assert "is empty as required for deployment" in js
    assert js.index("const currentOwner =") < js.index(
        "if (grp.require_empty_at_deploy)",
    )
    assert js.index("while (membersUrl)") < js.index("phase-0-security-errors")
    assert js.index("phase-0-security-errors") < js.index(f"Starting Phase {pn('lists')}")
    # The gate itself observes without mutating: no member removal between
    # the gate's guard and its success log. (Member removal DOES exist
    # elsewhere in the script, the run-scoped operator self-enrolment
    # cleanup, which never touches pre-existing members.)
    gate_block = js[
        js.index("if (grp.require_empty_at_deploy)"):js.index("is empty as required for deployment")
    ]
    assert "/users/removebyid" not in gate_block
    assert "/users/removebyloginname" not in js
    # Two now, both unconditional: the operator's run-scoped cleanup and the
    # enterprise-reader drain, which deploy.js.j2 declares regardless of
    # whether --enterprise-reader was passed (task 6, security-phase
    # atomicity) so it exists on every build, not just one that emits the
    # reader-enrolment phase itself.
    assert js.count("/users/removebyid(") == 2
    assert js.index("removeSelfEnrollments") < js.index("/users/removebyid(")
    assert "removeReaderEnrollments" in js


def test_exact_lists_break_inheritance_immediately_in_phase_1() -> None:
    """Exact-mode lists must not inherit Team rights until the ACL phase."""
    js = _generate_simple_js()
    phase1 = js.split(f"Starting Phase {pn('lists')}")[1].split(
        f"Starting Phase {pn('lookups')}")[0]

    assert "earlyIsolationLists" in phase1
    assert "!s.folder && s.break_inheritance && s.reconcile_mode === 'exact'" in phase1
    assert "early HasUniqueRoleAssignments probe failed" in phase1
    assert "early breakroleinheritance failed" in phase1
    break_call = (
        "breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false)"
    )
    assert break_call in phase1
    assert js.count(break_call) == 2  # early isolation plus full Phase 4.2 guard
    assert "clearSubscopes=true" not in phase1
    # The batched field wave opens with the decide pass, so that loop is still
    # the first thing in the phase that touches a declared column: nothing is
    # queued, sent or read back before it, and the calculated tail is behind it.
    assert phase1.index("listGuids[list.title] = listShape.Id") < phase1.index(
        "if (earlyIsolationLists.has(list.title))",
    ) < phase1.index("for (const col of batchedFields)")


def test_new_exact_list_must_remain_empty_after_early_isolation() -> None:
    """A row raced into the create/break gap must block fields and seeding."""
    js = _generate_simple_js()
    phase1 = js.split(f"Starting Phase {pn('lists')}")[1].split(
        f"Starting Phase {pn('lookups')}")[0]

    assert "let createdThisRun = false" in phase1
    assert "createdThisRun = true" in phase1
    assert "$select=ItemCount" in phase1
    assert "post-isolation ItemCount probe failed" in phase1
    assert "post-isolation ItemCount probe returned an invalid response" in phase1
    assert "contains ${itemCount} item(s) after early isolation" in phase1
    assert "remains empty after early isolation" in phase1
    assert "summary.errors.push({ phase: '2.1'" in phase1
    assert phase1.index("early breakroleinheritance failed") < phase1.index(
        "$select=ItemCount",
    ) < phase1.index("for (const col of batchedFields)")
    assert js.index("contains ${itemCount} item(s) after early isolation") < js.index(
        "pre-seed-errors",
    )


def test_singleton_seed_existing_row_must_match_exactly() -> None:
    """Seed idempotency verifies the singleton; it never trusts any row."""
    js = _generate_simple_js()
    phase5 = js.split(f"Starting Phase {pn('seeds')}")[1]

    assert "exactSeedValueEqual" in phase5
    assert "actual === null && expected === ''" in phase5
    assert "do not coerce any other scalar values" in phase5
    assert "key !== '__metadata'" in phase5
    assert "readSeedSingleton" in phase5
    assert "?$top=2&$select=${selectFields}" in phase5
    assert "Object.prototype.hasOwnProperty.call(existing, field)" in phase5
    assert "does not exactly match declared field(s)" in phase5
    assert "contains multiple rows" in phase5
    assert "Verified existing singleton row" in phase5
    assert "Seeded and verified" in phase5
    assert "phase-5-seed-errors" in phase5
    assert "deployment is not activation-ready" in phase5
    assert phase5.count("await readSeedSingleton(seed)") == 2
    assert "already has a row, skipping seed" not in phase5
    assert "not present (HTTP" not in phase5


def test_exact_acl_reconciliation_detects_descendant_unique_scopes() -> None:
    """Exact list ACLs must not conceal stale item/folder permission scopes.

    The deployer enumerates all items (including document-library folders/files)
    before any break/reconciliation, follows paging, uses
    clearSubscopes=false, and fails closed for explicit operator review.
    """
    js = _generate_simple_js()

    # FileSystemObjectType and FileRef ride along so the one enumeration also
    # resolves each DECLARED folder to its item id; see
    # test_declared_folder_scopes_are_excluded_from_the_guard below.
    assert (
        "$select=Id,HasUniqueRoleAssignments,FileSystemObjectType,FileRef&$top=5000"
        in js
    )
    assert "while (itemsUrl)" in js
    assert "const next = validatedNextPage(itemsJson.d," in js
    assert "itemsUrl = next;" in js
    assert "undeclared item/folder unique permission scope(s) remain" in js
    assert "never erase" in js
    assert (
        "breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false)" in js
    )
    assert (
        "breakroleinheritance(copyRoleAssignments=false,clearSubscopes=true)" not in js
    )
    descendant_probe = "await surveyDescendants(listTitle, wantedFolders)"
    assert js.count(descendant_probe) == 2, "survey once before the writes, once after"

    # Asserted over the DRIVER, not over the whole phase. The reconciliation
    # body is a function now, so it is defined above the loop and the break
    # call appears earlier in the text than the survey while still running
    # after it. Position in the driver is what actually orders the two.
    phase4 = js.split(f"Starting Phase {pn('acls')}")[1].split(f"Starting Phase {pn('seeds')}")[0]
    driver = phase4.split("for (const listTitle of aclListTitles)")[1]
    assert driver.index("assertNoUndeclaredScopes(listTitle, before.undeclared)") < \
        driver.index("await reconcileScope("), \
        "the guard must run before the first securable is written"


def test_folder_acls_address_the_folder_as_a_list_item() -> None:
    """A folder is not itself a SecurableObject; its list item is, which is why
    every folder endpoint is the list's own base plus `/items(<id>)`.

    Addressed by id rather than by server-relative path deliberately. The id
    comes from the same enumeration the descendant-scope guard already runs,
    so it costs no request, it keeps every folder write inside the
    `withOwnedList` bracket that proves the title still resolves to the
    surveyed list, and it sidesteps path-literal quoting for folder names
    carrying `&` or a comma, which the shipped division folders do.
    """
    js = _generate_simple_js()
    phase4 = js.split(f"Starting Phase {pn('acls')}")[1].split(f"Starting Phase {pn('seeds')}")[0]
    assert "suffix: `/items(${before.folderIds.get(fa.folder)})`" in phase4
    # One literal base for both securables, so the endpoint inventory in
    # test_template_lint.py sees one family rather than an opaque variable.
    assert (
        "web/lists/getbytitle('${odataName(scope.listTitle)}')${scope.suffix}"
        "/breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false)"
    ) in phase4
    assert "${scope.base}" not in phase4


def test_declared_folder_scopes_are_excluded_from_the_guard() -> None:
    """The guard aborts on an UNDECLARED descendant scope only.

    Without this, a deliberate folder ACL would abort every redeploy after the
    one that created it: the phase would find the scope it had just written
    and refuse to continue. The exclusion is computed from the folder ids the
    same survey resolved, never from a second lookup, because a guard and a
    writer that disagreed about which folders are declared would either erase
    nothing and abort forever or wave through a scope nobody declared.
    """
    js = _generate_simple_js()
    assert "const declared = new Set(folderIds.values());" in js
    assert (
        "undeclared: rows.filter(r => r.HasUniqueRoleAssignments "
        "&& !declared.has(r.Id))" in js
    )
    # Matched on the full path, never the leaf: a subfolder may share a leaf
    # name with a root folder and securing the wrong one reads back clean.
    assert "r.FileSystemObjectType === ACL_FOLDER_OBJECT_TYPE && r.FileRef === wanted" in js
    # Own constant: the folder phase's is another phase body's scope (#454).
    assert "const ACL_FOLDER_OBJECT_TYPE = 1;" in js


def test_other_role_build_does_not_apply_scoped_default_policy() -> None:
    """Regression: with a role-scoped default policy, a build for another role
    must emit NO acl_scopes for that role's lists (previously the default fell
    back onto every entity, re-ACLing them with the other role's groups)."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    assert bundle.mapping.permissions is not None
    assert bundle.mapping.permissions.default_policy_site_role == "default"
    bundle.mapping.entities["Task"] = EntityMapping(
        name="Task", kind="HubOnlyList", base_template=100, site_role="admin",
    )

    hub_json = build_schema_json(schema, bundle, "admin")
    assert [lst["title"] for lst in hub_json["lists"]] == ["APP_Task"]
    assert hub_json["acl_scopes"] == []

    default_json = build_schema_json(schema, bundle, "default")
    assert {la["list"] for la in default_json["acl_scopes"]} == {
        "APP_Project", "APP_AppSettings",
    }


def test_permission_level_probe_uses_filter_not_getbyname() -> None:
    """SP's roledefinitions/getbyname returns HTTP 500 (not 404) for a missing
    role definition, so a getbyname existence probe fails Phase 1.3 on every
    clean site (first real-tenant paste). The probe must use the $filter form,
    which returns 200 + empty results when absent; getbyname remains only on
    the MERGE path for an existing level. Description is selected alongside
    Id: #224's adoption gate reads it, and Id alone would give that gate
    nothing to test."""
    js = _generate_simple_js()
    assert "web/roledefinitions?$select=Id,Description&$filter=Name eq" in js


def test_group_management_automation_rendered(tmp_path: Path) -> None:
    """The generated script must carry (a) the CSOM ProcessQuery owner-set
    fallback for mismatched group owners and (b) the operator self-enrolment
    machinery keyed by groups[].enroll_operator_during_deploy."""
    mapping_path = write_mapping(
        tmp_path,
        blocks((FIXTURES / "calculated-mapping.yaml").read_text(encoding="utf-8"), """
            groups:
              - name: GH List Administrators
                description: Test admin group
                owner_group: Site Owners
                allow_members_edit_membership: false
                allow_request_to_join_leave: false
                auto_accept_request_to_join_leave: false
                only_allow_members_view_membership: false
                enroll_operator_during_deploy: true
        """),
        # The fixture already declares its own `prefix:`.
        prefix=None,
    )
    schema = parse_dbml(FIXTURES / "calculated.dbml")
    bundle = load_mapping(mapping_path)
    release = load_release(FIXTURES / "release.yaml")
    js = generate_deploy_js(
        schema=schema, bundle=bundle, release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="calculated.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert '"enroll_operator_during_deploy": true' in js
    assert "ProcessQuery" in js          # owner-set fallback endpoint
    assert "SetProperty" in js           # CSOM payload
    assert "removeSelfEnrollments" in js # end-of-run cleanup helper


def test_operator_effective_rights_diagnostic_after_cleanup() -> None:
    """List ACLs can LOOK correct while the signed-in operator still deletes
    happily. Site collection admins and Full Control holders bypass list
    ACLs entirely (seen live: the deploying owner could delete despite a
    no-delete working level). After self-enrolment cleanup the script probes
    the operator's EffectiveBasePermissions per ACL'd list and logs
    delete/manage rights with the bypass explanation, so the operator knows
    member-level verification needs an ordinary member account."""
    js = _generate_simple_js()
    assert "/effectivebasepermissions" in js
    assert "Operator effective rights on" in js
    assert "bypass list ACLs" in js
    assert "ordinary member account" in js
    # Group-connected sites make every group owner a site collection admin
    # (invisible in Check Permissions, bypasses every list ACL). Say so.
    assert "_spPageContextInfo.isSiteAdmin" in js
    assert "site collection admin = " in js
    assert "owners of a group-connected site are site collection admins" in js
    # After cleanup, before DONE, since enrolment would otherwise inflate rights.
    diagnostic = js.index("Operator effective rights on")
    assert js.rfind("await removeSelfEnrollments()", 0, diagnostic) >= 0
    assert diagnostic < js.index("Deployment complete.")


def test_one_enumeration_answers_every_role_assignment_question() -> None:
    """Three reads of a scope's bindings drifted apart once already: the
    read-back added days after the allowlist enumeration did not paginate,
    did not verify removals, and ran after the pruning. One read cannot.

    Asserted on the generated source rather than by running it: a shape that
    only the exact-mode branch reaches is invisible to a run whose fixture
    declares no exact policy. Over Phase 4.2's own text rather than the whole
    script, for the reason `_acl_phase` gives.
    """
    js = _generate_simple_js()
    assert js.count("roleassignments?$expand=RoleDefinitionBindings") == 1, (
        "every read of a scope's bindings must go through scopeBindings"
    )
    assert "getbyprincipalid" not in _acl_phase(js), (
        "a per-principal probe is a second way to read the same thing"
    )


def test_groups_and_levels_carry_their_previous_names_and_markers(tmp_path: Path) -> None:
    """Each previous name pairs with the marker its own name produces, so the
    security phase adopts a previous name only when the site holds the
    marker that name would have been stamped with."""
    write_mapping(tmp_path, """
        prefix: "GOV_"
        previous_prefixes: ["ADOPT_"]
        entities:
          Risk: { kind: List, base_template: 100, site_role: default }
        permission_levels:
          - name: "{prefix} Submit Only"
            description: "Add and read."
            base_permissions: [AddListItems]
        groups:
          - name: "{prefix} Programme Leads"
            description: "Leads."
            renamed_from: ["{prefix} Program Governance"]
    """)
    bundle = load_mapping(tmp_path / "m.yaml")
    schema = parse_dbml(FIXTURES / "simple.dbml")
    family = family_for(schema)
    built = build_schema_json(schema, bundle, "default")
    level = marker_for_level(family, "ADOPT Submit Only")
    assert built["permission_levels"][0]["previous_names"] == [
        {"name": "ADOPT Submit Only", "expected_marker": level},
    ]
    assert built["groups"][0]["previous_names"] == [
        {"name": name, "expected_marker": marker_for_group(name, family)}
        for name in ("ADOPT Programme Leads", "GOV Program Governance", "ADOPT Program Governance")
    ]


def _group(name: str, owner_group: str = "Site Owners") -> SiteGroup:
    """A SiteGroup with the membership controls every declaration must set."""

    return SiteGroup(
        name=name,
        description="Declared by a test.",
        owner_group=owner_group,
        allow_members_edit_membership=False,
        allow_request_to_join_leave=False,
        auto_accept_request_to_join_leave=False,
        only_allow_members_view_membership=False,
    )


def test_a_mapping_with_no_permissions_still_emits_acl_scopes() -> None:
    """`Mapping.permissions` is optional and the schema key is not.

    `acl_scopes_out` was only ever assigned inside the `permissions is
    not None` branch while the returned dict read it unconditionally, so a
    Mapping composed through the public Python API with no permissions raised
    `UnboundLocalError` from a generator that used to work.
    """
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    stripped = dataclasses.replace(
        bundle, mapping=dataclasses.replace(bundle.mapping, permissions=None),
    )

    schema_json = build_schema_json(schema, stripped, "default")

    assert schema_json["acl_scopes"] == []
    assert schema_json["groups"] == []


def test_generated_groups_keep_the_position_they_were_declared_in() -> None:
    """The deploy creates groups in this order and resolves a custom
    `owner_group` right after creating the group that names it, so a
    generated group declared before the literal group that names it as owner
    has to stay there. Sorting every literal group to the front moved it.
    """

    owner = _group("{member} Owners")
    literal = _group("Coordinators", owner_group="Clinical Owners")
    perms = PermissionsConfig(
        levels=[], default_policy=None, overrides={},
        groups=[literal],
        # Declared BEFORE the literal group, which is what `after=0` records.
        group_sources=(GroupsFromEnum(enum="division", template=owner, after=0),),
    )

    names = [g.name for g in declared_groups(perms, {"division": ("Clinical",)})]

    assert names == ["Clinical Owners", "Coordinators"], names


def test_a_group_source_with_no_recorded_position_still_follows_the_literals() -> None:
    """`after=None` is what a caller composing the type by hand gets, and it
    has to keep the order those callers already relied on."""

    perms = PermissionsConfig(
        levels=[], default_policy=None, overrides={},
        groups=[_group("Coordinators")],
        group_sources=(
            GroupsFromEnum(enum="division", template=_group("{member} Owners")),
        ),
    )

    names = [g.name for g in declared_groups(perms, {"division": ("Clinical",)})]

    assert names == ["Coordinators", "Clinical Owners"], names


def test_the_descendant_survey_only_runs_when_its_answer_is_read() -> None:
    """The survey pages every item in the list.

    Exact mode is the only mode that reads `undeclared`, and reading it costs
    a full enumeration. Running it unconditionally meant a `reconcile:
    configured` library enumerated every document to learn the ids of a
    handful of declared folders, which can meet the list view threshold
    before any ACL work begins.
    """
    js = _generate_simple_js()
    region = js[js.index("const aclListTitles"):]
    guard = region.index("const before = exact")
    survey = region.index("await surveyDescendants(listTitle, wantedFolders)")
    cheap = region.index("await declaredFolderIds(listTitle, wantedFolders)")

    assert guard < survey, "the enumeration must sit behind the exact test"
    assert guard < cheap, "so must the per-folder lookup that replaces it"


def test_a_folder_grant_counts_as_a_grant_on_that_entity(tmp_path: Path) -> None:
    """`lists_granting_group` reports what the deploy will bind, and where.

    The deploy binds an entity's folder assignments exactly as it binds its
    list ones, so a group granted only there does hold a grant on that
    entity. Counted as no grant at all it contradicted the validator, which
    counts a folder policy when deciding whether a group has any grant: the
    build passed validation and the CLI then refused the same reader for
    holding none. Reported as `folder_only` rather than `granted`, because
    the deploy binds it to the declared folders and not to the library, and
    the manifest said "Read on every list here" of exactly this case.
    """
    from dbml_sharepoint.analysis.permissions import lists_granting_group
    from dbml_sharepoint.model.mapping_types import (
        ListPermissionPolicy,
        Principal,
        RoleAssignment,
    )

    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    folder_only = ListPermissionPolicy(
        break_inheritance=True, reconcile_mode="exact",
        assignments=[RoleAssignment(
            principal=Principal(kind="group", name="dbml Enterprise Readers"),
            level="Read",
        )],
    )
    entity = next(iter(bundle.mapping.entities))
    perms = bundle.mapping.permissions
    assert perms is not None
    # The entity has to DECLARE folders: a policy on a library with none
    # binds nothing, which is `folder_permissions_without_folders`.
    patched = dataclasses.replace(
        bundle.mapping,
        entities={
            **bundle.mapping.entities,
            entity: dataclasses.replace(
                bundle.mapping.entities[entity], folder_source=("Cases",),
            ),
        },
        permissions=dataclasses.replace(
            perms, overrides={}, default_policy=None,
            folder_policies={entity: folder_only},
        ),
    )

    reach = lists_granting_group(patched, "dbml Enterprise Readers", [entity], {})

    assert reach.folder_only == [entity], reach
    assert reach.granted == [], reach
    assert reach.excluded == [], reach


def test_a_folder_principal_template_resolving_to_the_reader_counts() -> None:
    """A `{member}` principal is not necessarily a per-member group.

    `dbml Enterprise {member}` over a folder named Automation resolves to a
    literal group, and the deploy binds it. Compared unexpanded, the CLI
    refused the enrolment and the manifest called the list excluded while the
    emitted script granted the reader on every folder of it.
    """
    from dbml_sharepoint.analysis.permissions import lists_granting_group
    from dbml_sharepoint.model.mapping_types import (
        FoldersFromEnum,
        ListPermissionPolicy,
        Principal,
        RoleAssignment,
    )

    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    entity = next(iter(bundle.mapping.entities))
    perms = bundle.mapping.permissions
    assert perms is not None
    patched = dataclasses.replace(
        bundle.mapping,
        entities={
            **bundle.mapping.entities,
            entity: dataclasses.replace(
                bundle.mapping.entities[entity],
                folder_source=FoldersFromEnum(enum="area"),
            ),
        },
        permissions=dataclasses.replace(
            perms, overrides={}, default_policy=None,
            folder_policies={entity: ListPermissionPolicy(
                break_inheritance=True, reconcile_mode="exact",
                assignments=[RoleAssignment(
                    principal=Principal(kind="group", name="dbml Enterprise {member}"),
                    level="Read",
                )],
            )},
        ),
    )

    reach = lists_granting_group(
        patched, "dbml Enterprise Readers", [entity], {"area": ["Readers"]},
    )

    assert (reach.granted, reach.folder_only, reach.excluded) == ([], [entity], [])


def test_a_folder_policy_over_an_entity_with_no_folders_grants_nothing() -> None:
    """`lists_granting_group` reports what the deploy BINDS, and a policy on
    an entity declaring no folders binds nothing: there is no folder to write
    it to. `folder_permissions_without_folders` is the finding for it."""
    from dbml_sharepoint.analysis.permissions import lists_granting_group
    from dbml_sharepoint.model.mapping_types import (
        ListPermissionPolicy,
        Principal,
        RoleAssignment,
    )

    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    entity = next(iter(bundle.mapping.entities))
    perms = bundle.mapping.permissions
    assert perms is not None
    patched = dataclasses.replace(
        bundle.mapping,
        permissions=dataclasses.replace(
            perms, overrides={}, default_policy=None,
            folder_policies={entity: ListPermissionPolicy(
                break_inheritance=True, reconcile_mode="exact",
                assignments=[RoleAssignment(
                    principal=Principal(kind="group", name="dbml Enterprise Readers"),
                    level="Read",
                )],
            )},
        ),
    )

    reach = lists_granting_group(patched, "dbml Enterprise Readers", [entity], {})

    assert (reach.granted, reach.folder_only, reach.excluded) == ([], [], [entity])


def test_a_folder_policy_off_this_build_does_not_demand_manage_permissions(
) -> None:
    """`requires_manage_permissions` is scoped by the entities in THIS build.

    A folder policy is keyed by entity, so counting it as a mapping-wide fact
    made a site_role that deploys none of those entities advertise a right it
    never exercises, and deploy.js then aborts an operator who correctly
    lacks it.
    """
    from dbml_sharepoint.analysis.permissions import requires_manage_permissions
    from dbml_sharepoint.model.mapping_types import (
        ListPermissionPolicy,
        Principal,
        RoleAssignment,
    )

    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    perms = bundle.mapping.permissions
    assert perms is not None
    policy = ListPermissionPolicy(
        break_inheritance=True, reconcile_mode="exact",
        assignments=[RoleAssignment(
            principal=Principal(kind="associated_owner_group", name=None),
            level="Read",
        )],
    )
    bare = dataclasses.replace(
        bundle.mapping,
        permissions=dataclasses.replace(
            perms, levels=[], groups=[], group_sources=(),
            default_policy=None, overrides={},
            folder_policies={"ElsewhereOnly": policy},
        ),
    )

    assert requires_manage_permissions(bare, ["ElsewhereOnly"], {}) is True
    assert requires_manage_permissions(bare, ["SomethingElse"], {}) is False


def test_a_group_source_over_an_empty_enum_does_not_demand_manage_permissions(
) -> None:
    """An empty enum is a warning, not a refusal, so a mapping whose only
    permission declaration is a `from_enum` source over one generates no
    groups and writes no ACL. Demanding the right anyway aborts an operator
    who correctly lacks it, which is the #166 item 5 failure again."""
    from dbml_sharepoint.analysis.permissions import requires_manage_permissions
    from dbml_sharepoint.model.mapping_types import GroupsFromEnum, SiteGroup

    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    perms = bundle.mapping.permissions
    assert perms is not None
    source = GroupsFromEnum(
        enum="division",
        template=SiteGroup(
            name="{member} Editors", description="", owner_group="Site Owners",
            allow_members_edit_membership=False, allow_request_to_join_leave=False,
            auto_accept_request_to_join_leave=False,
            only_allow_members_view_membership=False,
        ),
    )
    bare = dataclasses.replace(
        bundle.mapping,
        permissions=dataclasses.replace(
            perms, levels=[], groups=[], group_sources=(source,),
            default_policy=None, overrides={}, folder_policies={},
        ),
    )

    assert requires_manage_permissions(bare, [], {"division": []}) is False
    assert requires_manage_permissions(bare, [], {"division": ["Clinical"]}) is True
