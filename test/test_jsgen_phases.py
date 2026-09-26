# test/test_jsgen_phases.py
"""The emitted run: phase order, the guards inside it, and the exit path.

Ownership rechecked at each write, the fail-closed preflight, the
adoptability wrapper, per-list lanes and the batched reads that feed them,
the seal and unseal pair, the lifted save rule, and the cleanup in the
`finally` that has to run on every exit including the ones that abort.
"""

import json
import re
from pathlib import Path
from typing import Any, ClassVar, override

from _builders import ID_PK, TITLE, table
from _packs import blocks, entities, pack
from _paths import FIXTURES
from test_jsgen import _FIXED_ARGS, _generate_simple_js, _generate_views_js

from dbml_sharepoint.analysis.phases import phase_number as pn
from dbml_sharepoint.analysis.resolve import resolve
from dbml_sharepoint.analysis.validator import validate_all
from dbml_sharepoint.extension import BaseExtension, NullExtension, SiteContext
from dbml_sharepoint.generators.assessgen import assess_targets
from dbml_sharepoint.generators.jsgen import build_schema_json, generate_deploy_js
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import CrossSiteRef, MappingBundle
from dbml_sharepoint.model.parser import Schema, parse_dbml
from dbml_sharepoint.model.release import load_release


def test_title_keyed_deploy_state_has_no_object_prototype() -> None:
    js = _generate_simple_js()

    assert "const preflightListShapes = Object.create(null)" in js
    assert "let fieldShapesByList = Object.create(null)" in js
    assert "const listGuids = Object.create(null)" in js


def test_maintenance_records_reseal_cleanup_before_unseal_request() -> None:
    js = _generate_simple_js()
    maintenance = js.split("// === Maintenance unseal", 1)[1].split(
        "// === Group", 1,
    )[0]

    # The unseal batches, so the ordering is against the QUEUING of the part
    # rather than against a request. It is the same requirement: a ChangeSet
    # SharePoint commits without answering has to be re-sealable on exit.
    assert maintenance.index("fieldsUnsealedForRun.set") < maintenance.index(
        "await unsealBatch.add",
    )


def test_exit_reseal_requires_original_owned_list_and_field_ids() -> None:
    js = _generate_simple_js()
    restore = js.split("async function restoreUnsealedFields", 1)[1].split(
        "function syntheticTitleField", 1,
    )[0]
    maintenance = js.split("// === Maintenance unseal", 1)[1].split(
        "// === Group", 1,
    )[0]

    assert "[listTitle, field.title, currentList.Id, shape.Id]" in maintenance
    # By-Id in the batched spelling too: fieldMergePath builds the same
    # /lists(guid)/fields(guid) address patchFieldById sends to.
    assert "fieldMergePath(currentList.Id, shape.Id)" in maintenance
    ownership = restore.index("assertListAdoptable(list, currentList)")
    list_id = restore.index("currentList.Id !== listId", ownership)
    field_id = restore.index("shape.Id !== fieldId", list_id)
    reseal = restore.index("await patchFieldById(", field_id)
    readback = restore.index("const verify = await readFieldShape", reseal)
    verified = restore.index("verify.Id !== fieldId || verify.Sealed !== true", readback)
    assert ownership < list_id < field_id < reseal < readback < verified


def test_maintenance_checks_field_existence_before_lookup_target() -> None:
    js = _generate_simple_js()
    maintenance = js.split("// === Maintenance unseal", 1)[1].split(
        "// === Group", 1,
    )[0]

    field_read = maintenance.index("const shape = await readFieldShape")
    # `continue`, not `return`: a lane now holds every column of one list, so
    # skipping an absent field must not abandon the list's other columns.
    missing_skip = maintenance.index("if (!shape) continue", field_read)
    target_check = maintenance.index("if (field.target_list)", field_read)
    assert field_read < missing_skip < target_check


def test_list_validation_rechecks_ownership_before_merge() -> None:
    js = _generate_simple_js()
    validation = js.split("async function reconcileListValidation", 1)[1].split(
        "async function reconcileListDeletionBlock", 1,
    )[0]

    live_read = validation.index("const actual = await readListShape")
    ownership = validation.index("assertListAdoptable(list, actual)", live_read)
    merge = validation.index("await patchListById(actual.Id", ownership)
    assert live_read < ownership < merge


def test_wave_one_list_writes_bind_fresh_owned_list_id() -> None:
    js = _generate_simple_js()
    settings = js.split("async function reconcileListShape", 1)[1].split(
        "async function expectedLookupFieldInternalName", 1,
    )[0]
    description = js.split("async function reconcileListDescription", 1)[1].split(
        "async function reconcileListShape", 1,
    )[0]
    deletion = js.split("async function reconcileListDeletionBlock", 1)[1].split(
        "async function reconcileListDescription", 1,
    )[0]

    assert "actual = await assertDeclaredListOwnedNow(list.title)" in settings
    assert "await patchListById(actual.Id" in settings
    assert "actual = await assertDeclaredListOwnedNow(list.title)" in description
    assert "await patchListById(actual.Id" in description
    assert "const owned = await assertDeclaredListOwnedNow(list.title)" in deletion
    assert "await patchListById(owned.Id" in deletion


def test_field_reconcile_rechecks_ownership_after_its_reads() -> None:
    js = _generate_simple_js()
    reconcile = js.split("async function reconcileDeclaredField", 1)[1].split(
        "// === Preflight", 1,
    )[0]

    last_shape_check = reconcile.index("await assertFieldImmutableShape")
    ownership = reconcile.index(
        "await assertDeclaredFieldTargetNow(listName, field, targetGuid)",
        last_shape_check,
    )
    merge = reconcile.index("await patchField", ownership)
    assert last_shape_check < ownership < merge


def test_field_formula_merges_bind_fresh_lookup_target_identity() -> None:
    js = _generate_simple_js()
    formulas = js.split("async function enforceDeclaredFormulas", 1)[1].split(
        "async function reconcileDeclaredField", 1,
    )[0]
    assert formulas.count(
        "await assertDeclaredFieldTargetNow(listName, field, targetGuid)",
    ) == 2


def test_phase_one_lookup_refreshes_owned_target_before_reconcile() -> None:
    js = _generate_simple_js()
    wave_two = js.split("// Wave 2 is field provisioning", 1)[1].split(
        "if (summary.errors.length > 0)", 1,
    )[0]

    target_read = wave_two.index(
        "await assertDeclaredListOwnedNow(col.target_list)",
    )
    target_guid = wave_two.index("return targetOwned.Id", target_read)
    # The decide pass resolves the target before it reads the column back and
    # before it queues the create, so the LookupListId a ChangeSet part carries
    # is one this run has just proved it still owns.
    resolved = wave_two.index(
        "const targetGuid = await resolveTargetGuid(col)", target_guid,
    )
    reconcile = wave_two.index("await reconcileDeclaredField", resolved)
    create = wave_two.index(
        "declaredFieldCreateOp(list.title, col, targetGuid)", reconcile,
    )
    assert target_read < target_guid < resolved < reconcile < create
    # The verify pass resolves again rather than reusing what the decide pass
    # held. The batch is in flight in between, and the immutable-shape check
    # compares the readback's LookupList against this GUID: reusing the stale
    # one would compare a swapped target against itself and pass.
    verify_resolved = wave_two.index("await resolveTargetGuid(col) : null", create)
    verify_reconcile = wave_two.index("await reconcileDeclaredField", verify_resolved)
    assert verify_resolved < verify_reconcile


def test_the_deploy_carries_the_assessment_inputs_assess_js_uses() -> None:
    """One spelling, or the two scripts disagree about the same site.

    A re-derived copy in `jsgen` would emit the same key names, so this
    compares the emitted values against the function both scripts import.
    """
    js = _generate_simple_js()
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    expected = assess_targets(
        schema, bundle, _FIXED_ARGS["site_role"], resolved=resolve(schema, bundle.mapping),
    )
    # `tojson(indent=2)` indents the members but leaves the closing brace in
    # column 0, so that is the terminator, not the assignment's indent.
    match = re.search(r"const ASSESS_TARGETS = (\{.*?\n\});", js, re.DOTALL)
    assert match is not None, "ASSESS_TARGETS is not emitted as an object literal"
    # Round-trip the expectation too: `list_markers` holds tuples, which JSON
    # has no way to distinguish from lists once emitted.
    assert json.loads(match.group(1)) == json.loads(json.dumps(expected))
    assert "const ASSESS_REQUIREMENTS = [" in js
    assert "const ASSESS_NOT_ASSESSABLE = [" in js


def test_the_assessment_runs_before_the_preflight_and_can_abort() -> None:
    """A separate assess.js.txt only protects the operators who paste it.

    Carrying the assessment inside deploy.js.txt is what makes it
    unskippable, so both abort codes must appear before the preflight banner.
    """
    js = _generate_simple_js()
    assert js.index(f"Starting Phase {pn('assess')}") < js.index(
        f"Starting Phase {pn('preflight')}",
    )
    for code in ("assessment-blocked", "assessment-degraded-unacknowledged"):
        assert js.index(code) < js.index(f"Starting Phase {pn('preflight')}"), code


def test_the_acknowledgement_flag_defaults_to_refusing() -> None:
    """An unedited paste must stop on a degraded site, as every probe does."""
    assert "const ACKNOWLEDGE_DEGRADED = false;" in _generate_simple_js()


def test_deploy_js_phase1_reliability_hardening() -> None:
    """A4: the generated deploy.js must (a) carry a Retry-After-aware retry
    helper, (b) refresh the request digest inside the Phase 2.1 list loop, (c)
    guard each Phase 2.1 field POST in its own try/catch, and (d) reconcile stale
    role bindings in Phase 4.2 (remove-before-add)."""
    js = _generate_simple_js()
    # (a) retry helper honouring Retry-After
    assert "fetchWithRetry" in js
    assert "Retry-After" in js
    # (b) per-list digest refresh: getDigest() must be called inside the
    # Phase 2.1 `for (const list of SCHEMA.lists)` loop, not only once before it.
    phase1 = js.split(f"Starting Phase {pn('lists')}")[1].split(
        f"Starting Phase {pn('lookups')}")[0]
    assert "for (const list of SCHEMA.lists)" in phase1
    assert "digest = await getDigest()" in phase1
    # (c) per-field guard marker
    assert f"Phase {pn('lists')} field" in js
    # (d) Phase 4.2 reconcile
    assert "roleassignments?$expand=RoleDefinitionBindings" in js
    assert "removeroleassignment" in js


def test_existing_schema_shape_preflight_is_fail_closed() -> None:
    """Same-name lists/fields are not accepted as idempotency evidence."""
    js = _generate_simple_js()

    assert f"Starting Phase {pn('preflight')}: read-only preflight" in js
    assert "$select=${select}" in js
    assert "BaseTemplate" in js
    assert "ContentTypesEnabled" in js
    assert "EnableVersioning" in js
    assert "EnableMinorVersions" in js
    assert "MajorVersionLimit" in js
    assert "SharePoint list/library templates are immutable" in js
    assert "getbyinternalnameortitle" in js
    assert "TypeAsString" in js
    assert "EnforceUniqueValues" in js
    assert "ReadOnlyField" in js
    assert "Sealed" in js
    assert "DefaultValue" in js
    assert "derived-shape probe" in js
    for property_name in (
        "MaxLength",
        "RichText",
        "NumberOfLines",
        "AppendOnly",
        "Choices",
        "FillInChoice",
        "DisplayFormat",
        "SelectionMode",
    ):
        assert property_name in js
    assert "existing-schema-shape-errors" in js
    assert "no deployment writes were attempted" in js
    assert js.index(f"Starting Phase {pn('preflight')}: read-only preflight") < js.index(
        f"Starting Phase {pn('security')}",
    )
    assert js.index("existing-schema-shape-errors") < js.index(f"Starting Phase {pn('security')}")


def test_the_delta_report_is_printed_before_the_abort_returns() -> None:
    """A printer placed after the return prints nothing and stays green.

    The abort still returns the same code and logs the same failure line, so
    no other test moves when the report is emitted too late. Ordering is the
    only assertion that catches it.
    """
    js = _generate_simple_js()

    assert "aborted: 'existing-schema-shape-errors'" in js
    assert (
        "Existing-schema shape preflight failed; no deployment writes were attempted."
    ) in js
    assert js.index("Existing-schema shape delta:") < js.index(
        "aborted: 'existing-schema-shape-errors'",
    )


def test_existing_lookup_shape_requires_exact_target_and_display_field() -> None:
    """An existing lookup cannot silently retain another list/field target."""
    js = _generate_simple_js()

    assert "?$select=LookupList,LookupField" in js
    assert "normalizeGuid(actual.LookupList)" in js
    assert "expectedLookupFieldInternalName" in js
    assert "actual.LookupField !== expectedLookupField" in js
    assert "Lookup targets are immutable" in js
    assert "declared target list" in js


def test_dependent_lookup_verifies_the_projected_field_not_the_primary() -> None:
    """A dependent field projects `proj.show_field` (a field on the target
    list), so its `LookupField` readback must match that -- not the primary
    lookup column's own name. Regression: the check compared against the
    primary's title, which refused every correctly-shaped site because a
    dependent field's LookupField is its ShowField, never its primary."""
    js = _generate_simple_js()

    assert "s.LookupField === showField" in js
    assert "verifyDependentField(list.title, proj.name, proj.show_field" in js
    assert "verifyDependentField(lookup.list, proj.name, proj.show_field" in js
    assert "verifyDependentField(list.title, proj.name, col.title" not in js
    assert "verifyDependentField(lookup.list, proj.name, lookup.field.title" not in js


def test_mutable_list_and_field_shape_is_reconciled_and_read_back() -> None:
    """Mutable properties are MERGEd only after ownership and immutable checks."""
    js = _generate_simple_js()

    assert "assertListAdoptable(list, actual)" in js
    assert "await patchList" in js
    assert "did not retain declared setting(s)" in js
    assert "await assertFieldImmutableShape" in js
    assert "patchBody.Description = desired.description" in js
    assert "patchBody.Required = desired.required" in js
    assert "patchBody.EnforceUniqueValues = desired.enforceUniqueValues" in js
    assert "patchBody.Indexed = desired.indexed" in js
    assert "patchBody.DefaultValue = desired.defaultValue" in js
    assert "sameDerivedValue" in js
    assert "patchBody[name] = value" in js
    assert "fields/getbyinternalnameortitle('${odataName(columnName)}')" in js
    assert "fields/getbytitle('${odataName(columnName)}')" not in js
    assert "is sealed; expected an unsealed declared field" in js
    assert "DefaultValue readback did not match" in js
    assert "Send only drifted writable properties" in js
    assert "did not retain declared mutable setting(s)" in js
    assert js.index("await assertFieldImmutableShape") < js.index(
        "await patchField(listName, field.title",
    )
    assert "phase-1-schema-errors" in js
    assert "phase-2-schema-errors" in js
    assert js.index("phase-1-schema-errors") < js.index(f"Starting Phase {pn('lookups')}")
    assert js.index("phase-2-schema-errors") < js.index(f"Starting Phase {pn('indexes')}")


def _without_line_comments(js: str) -> str:
    """The emitted script with its whole-line `//` comments removed.

    Only lines whose first non-whitespace characters are `//` are dropped, so a
    `//` inside a string literal or a URL can never truncate a line of code. A
    trailing comment after code on the same line therefore still counts, which is
    the one hole left in the counter below.
    """
    return "\n".join(
        line for line in js.splitlines() if not line.lstrip().startswith("//")
    )


def _call_count(js: str, name: str) -> int:
    """Occurrences of `name(` in the emitted code, less its one declaration.

    Counted over `_without_line_comments`: a comment naming the function reads
    as a call site, so a disarmed site could be replaced by a line of prose
    mentioning it and the count would not move.
    """
    code = _without_line_comments(js)
    declarations = code.count(f"function {name}(")
    assert declarations == 1, f"{name} is not declared exactly once"
    return code.count(f"{name}(") - declarations


def test_every_list_write_region_uses_the_adoptability_wrapper() -> None:
    """The count is the only attribution available, and it has to hold.

    `assertListAdoptable` combines exact ownership with immutable shape. A site
    switched back to the shape-only wrapper can stamp a foreign list, while a
    site switched to a collector stops throwing. Two sites verify read-back, so
    one that stops throwing is indistinguishable from one that passed.

    The counts below pin every current write-region assertion. Preflight's two
    lanes call the collectors directly,
    because a throw reported one property and hid the rest: a list whose own
    shape is wrong still has columns worth reporting, and a column's other
    mismatches are still worth reporting when its lookup target is unreadable.
    Every remaining site is a write or a post-write read-back, where throwing is
    the point. One of them is a phase boundary rather than a single write: the
    deferred-lookup phase re-surveys every list it is about to touch, because
    the field wave is long enough for a marker to disappear after being read.
    Lowering either number again means a write-region site stopped throwing,
    which is the failure this test exists to catch.

    The post-schema phases reach the same assertions through the shared guard
    (#305), so their sites are counted on the guard rather than on
    `assertDeclaredListOwnedNow` directly: `ownedListIdentity` binds a proven
    list to a captured Id, `surveyOwnedListsForWrites` gates a whole write
    batch, and `ownedFieldIdentity` adds the field Id a by-Id MERGE is
    addressed with. Counting those separately is what keeps the attribution:
    routing a phase back through a bare title write drops one of these numbers
    without touching the two above.

    The index read-back is the one site that verifies without going through
    `ownedFieldIdentity`, and it is pinned separately below rather than left to
    that count. It reads its columns as one batch of query parts, so the list
    half of the check comes from the phase's second survey and the field half
    from the batched read. What makes that equivalent is the spelling of the
    read: each column is addressed THROUGH ITS LIST TITLE, so a list swapped
    between two columns' read-backs answers with a different field Id, or with
    none, and still fails that column's comparison. Losing either assertion
    below is a read-back that stopped proving the field it wrote to.

    Whole-line `//` comments are excluded from the count, so a disarmed site
    cannot be papered over with a line of prose naming the function. A trailing
    comment on a line of code is still counted, which is the remaining hole.
    """
    js = _generate_simple_js()

    assert _call_count(js, "assertFieldImmutableShape") == 3
    # 12 since the folder phase: it reads the library's shape to lift and put
    # back the save rule that refuses a folder create, which is a list write
    # region like any other and is held to the same wrapper.
    assert _call_count(js, "assertListAdoptable") == 12
    # Two more than assertListAdoptable: reconcileListItemSecurity and
    # reconcileListAttachments are settings MERGEs on an already-adopted list,
    # so each re-proves ownership without a second adoptability pass, the same
    # shape reconcileListDeletionBlock has.
    assert _call_count(js, "assertDeclaredListOwnedNow") == 13
    assert _call_count(js, "assertDeclaredFieldOwnedNow") == 1
    assert _call_count(js, "assertDeclaredFieldTargetNow") == 3
    # One survey per post-schema write phase: unseal, indexes, defaults, views,
    # forms, seal, ACLs, seeds. The index and form phases survey TWICE, because
    # each has a read-back that is a second write-region boundary: the objects
    # are read back after the last write lands, so the ownership the pre-write
    # survey proved is no longer current by then and is re-proved for the whole
    # batch rather than per object.
    assert _call_count(js, "surveyOwnedListsForWrites") == 10
    # 16 counted the unbatched unseal, which re-proved the list before every
    # single field MERGE and so needed only the one call site. Batching a
    # lane's unseals into one ChangeSet removes those intermediate re-proves,
    # so the phase gained a second site after the flush: a marker lost between
    # two parts of one envelope has no next write to abort at.
    assert _call_count(js, "ownedListIdentity") == 17
    assert _call_count(js, "ownedFieldIdentity") == 2
    # Every place a phase reads an Id back out of a survey it ran with
    # `allowAbsent` false: the seven pre-write lookups, one per such phase,
    # the form phase's re-comparison of its own survey Id after the layouts
    # land, and the index and form read-back surveys. A `Map.get` in place of
    # any of them answers `undefined` on a miss, and the signature check in
    # `ownedListIdentity` would then abort naming the list but not the reason;
    # this helper is what says the survey never proved the title. The unseal
    # phase surveys with `allowAbsent` true and branches on absence itself, so
    # it is not among them.
    assert _call_count(js, "surveyedListId") == 10
    code = _without_line_comments(js)
    # The index read-back, the form phase's two (its content-type resolution
    # and its layout read-back), and the assessment's own `probeMany`, which
    # the deploy carries because it includes `_assess_body.js.j2` for its
    # gate. The last one reads and never writes, which is why the read half of
    # the transport is its own partial.
    assert code.count("new BatchReader(") == 4
    assert "fieldShapePath(idx.list, idx.field)" in code


def test_generated_js_contains_phase_0_and_phase_4() -> None:
    """deploy.js must include Phase 1.3 (level/group creation) and Phase 4.2
    (break inheritance + role assignments) markers and SP REST calls (R6)."""
    js = _generate_simple_js()

    assert f"Phase {pn('security')}" in js
    assert f"Phase {pn('acls')}" in js
    assert "breakroleinheritance" in js
    assert "addroleassignment" in js


def test_seed_items_empty_with_null_extension() -> None:
    """With no extension (NullExtension default), the schema
    view exposes an empty ``seed_items`` list and carries NO organisation-specific
    keys. Seeding belongs to extensions."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")

    sj = build_schema_json(schema, bundle, "default", resolved=resolve(schema, bundle.mapping))

    assert sj["seed_items"] == []
    assert "app_settings_seed" not in sj


class _SeedExtension(BaseExtension):
    """Stub extension that seeds one list item into a titled list."""

    name: ClassVar[str] = "seedstub"

    @override
    def seed_lists(
        self, bundle: Any, schema: Any, site_context: SiteContext,
    ) -> dict[str, dict[str, Any]]:
        return {
            "APP_AppSettings": {
                "Title": "App Settings",
                "UnitName": "Zeta Unit",
            },
        }


def test_stub_extension_seed_rendered_in_generic_phase_5() -> None:
    """An extension's ``seed_lists`` entry ({title: fields}) surfaces as a
    ``seed_items`` element and drives the generic Phase 5.1 loop: the rendered
    deploy.js contains the list title, the field payload, and fetches
    ``ListItemEntityTypeFullName`` (no hardcoded ``SP.Data.*`` literal)."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")

    sj = build_schema_json(
        schema, bundle, "default",
        site_url="https://example.sharepoint.com/sites/t1",
        release=release,
        extension=_SeedExtension(), resolved=resolve(schema, bundle.mapping),
    )
    assert sj["seed_items"] == [
        {
            "title": "APP_AppSettings",
            "fields": {
                "Title": "App Settings",
                "UnitName": "Zeta Unit",
            },
            "skip_if_has_rows": True,
        },
    ]

    js = generate_deploy_js(
        schema=schema,
        bundle=bundle,
        release=release,
        site_url="https://example.sharepoint.com/sites/t1",
        site_role="default",
        source_dbml="simple.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
        extension=_SeedExtension(), resolved=resolve(schema, bundle.mapping),
    )
    assert f"Phase {pn('seeds')}" in js
    assert "SCHEMA.seed_items" in js
    assert "ListItemEntityTypeFullName" in js
    assert "readSeedSingleton" in js
    assert "assertSeedSingletonMatches" in js
    assert "APP_AppSettings" in js
    assert "Zeta Unit" in js
    # The old hardcoded item type literal must be gone.
    assert "SP.Data.APP_AppSettingsListItem" not in js


def test_cross_site_column_without_extension_is_error_finding() -> None:
    """A column declared in ``cross_site_reference_columns`` requires an
    extension whose ``expand_column`` handles it. With NullExtension
    (expand_column returns None), validate_all must surface an error
    Finding rather than silently emitting an unexpanded column."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.cross_site_reference_columns.append(
        CrossSiteRef(entity="Task", column="Project"),
    )

    findings = validate_all(schema, bundle, NullExtension())

    assert any(
        f.severity == "error" and "expand_column" in f.message for f in findings
    )


# --- UI hardening: sealed columns + list deletion block ----------------------


def _hardening_inputs(tmp_path: Path) -> tuple[Schema, MappingBundle]:
    return pack(
        tmp_path,
        dbml=table("Risk", ID_PK, TITLE, "Detail nvarchar"),
        mapping=blocks(entities("Risk"), """
            seal_columns: true
            prevent_list_deletion: true
        """),
    )


def test_hardening_flags_flow_to_schema(tmp_path: Path) -> None:
    schema, bundle = _hardening_inputs(tmp_path)
    risk = next(
        lst for lst in build_schema_json(
            schema, bundle, "default", resolved=resolve(schema, bundle.mapping),
        )["lists"]
        if lst["title"] == "APP_Risk"
    )
    assert risk["prevent_deletion"] is True
    assert all(f["seal"] is True for f in risk["fields_phase1"])


def test_template_brackets_writes_with_unseal_and_seal_phases(tmp_path: Path) -> None:
    """Sealed columns block UI schema edits even for site admins, the
    strongest defense available when team owners are unavoidably site
    collection admins (group-connected sites). Design: a maintenance unseal
    after Phase 1.3 leaves every existing write path untouched, and Phase 4.1
    re-seals and verifies after all field writes (3/3b/3d) are done. The
    immutable-shape gate tolerates sealed only for declared-seal fields."""
    schema, bundle = _hardening_inputs(tmp_path)
    js = generate_deploy_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z", resolved=resolve(schema, bundle.mapping),
    )
    assert "Maintenance unseal" in js
    assert f"Starting Phase {pn('seal')}: seal declared columns" in js
    assert "Sealed: false" in js
    assert "Sealed: true" in js
    assert "did not retain sealed state" in js
    assert "actual.Sealed && !field.seal" in js
    assert js.index(f"Starting Phase {pn('security')}") < js.index("Maintenance unseal") < js.index(
        f"Starting Phase {pn('lists')}",
    )
    assert js.index(f"Starting Phase {pn('forms')}") < js.index(
        f"Starting Phase {pn('seal')}",
    ) < js.index(f"Starting Phase {pn('acls')}")


def test_exit_restores_every_field_the_run_unsealed(tmp_path: Path) -> None:
    """Every declared field is opened during PREPARE, not only Title. An
    abort before PROTECTION must restore every list/column pair this run
    changed, while leaving fields it found open untouched."""
    schema, bundle = _hardening_inputs(tmp_path)
    js = generate_deploy_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z", resolved=resolve(schema, bundle.mapping),
    )

    assert "const fieldsUnsealedForRun = new Map();" in js
    assert "fieldsUnsealedForRun.set(" in js
    assert "[listTitle, columnTitle]" in js
    assert "async function restoreUnsealedFields()" in js
    assert "for (const [listTitle, columnTitle] of fieldsUnsealedForRun.values())" in js
    finally_block = js.rsplit("} finally {", 1)[1]
    assert "await restoreUnsealedFields();" in finally_block
    assert "await removeSelfEnrollments();" in finally_block


def test_a_cleanup_failure_is_corrected_after_the_summary_line() -> None:
    """#384. The [DONE] line is printed by the last phase, inside the try, so
    every exit cleanup runs after the operator's last authoritative sentence:
    one live run logged `errors 0` and then failed 56 re-seals. The re-seal
    cannot move ahead of that line, because it also has to run on the abort
    paths that never print it, so the correction goes last instead and every
    cleanup feeds the count it reports.
    """
    js = _generate_simple_js()
    finally_block = js.rsplit("} finally {", 1)[1]

    assert js.index("Deployment complete.") < js.index("Exit cleanup failed")
    baseline = finally_block.index("const errorsBeforeCleanup = summary.errors.length;")
    correction = finally_block.index("const cleanupErrors = summary.errors.length")
    assert baseline < finally_block.index("await restoreUnsealedFields();") < correction
    # Every cleanup, not only the re-seal: a wrapper that logs an error and
    # does not record it is invisible to the count all over again.
    for cleanup in (
        "restore field protection", "write the run's stop record",
        "remove the enterprise reader", "remove the operator's run-scoped enrolment",
    ):
        assert f"summary.errors.push({{ phase: 'exit', error: `{cleanup}" in finally_block, cleanup
    assert correction < finally_block.index("Exit cleanup failed")


def test_template_blocks_list_deletion_when_declared(tmp_path: Path) -> None:
    """AllowDeletion=false makes the LIST object undeletable through the UI
    even for admins (friction, not enforcement, honestly labeled). Isolated
    probe/MERGE so an unsupported tenant surface fails only this step."""
    schema, bundle = _hardening_inputs(tmp_path)
    js = generate_deploy_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z", resolved=resolve(schema, bundle.mapping),
    )
    assert "list.prevent_deletion" in js
    assert "$select=AllowDeletion" in js
    assert "AllowDeletion: false" in js
    assert "did not retain AllowDeletion" in js


def test_view_existence_check_enumerates_per_list(tmp_path: Path) -> None:
    """views/getbytitle on an absent view answers HTTP 400, handled by
    isAbsent400, but the browser paints the failed request red and
    operators read it as a deployment error (seen live). The existence
    check must come from ONE views?$select enumeration per list (always
    200); getbytitle remains only for post-create reads, when the view
    exists."""
    js = _generate_views_js(tmp_path)
    assert "/views?$select=" in js
    assert "async function listViewShapes" in js
    assert "await listViewShapes(listPath)" in js
    # The existence decision must NOT come from a per-title shape probe.
    existence = js.split("const deployView = async (view)")[1]
    creating = existence.split("Creating view")[0]
    assert "readViewShape(viewUrl)" not in creating


def test_field_shapes_served_from_per_list_enumeration(tmp_path: Path) -> None:
    """Two live findings, one mechanism: absent-field by-name GETs answer 400
    (painted red, read as failures), and bulk probe loops paid one GET per
    column per phase. Base shapes now come from ONE fields enumeration per
    list; probes reflect phase-start state (each field-touching phase
    invalidates); verify-after-write reads pass fresh=true and bypass the
    cache."""
    js = _generate_views_js(tmp_path)
    assert "async function listFieldShapes" in js
    assert "fields?$select=${_FIELD_SHAPE_SELECT}" in js
    assert "const invalidateFieldShapes" in js
    # Phase starts + both field-creation sites re-snapshot.
    assert js.count("invalidateFieldShapes();") >= 7
    probe = js.split("async function readFieldShape")[1].split("if (!shape")[0]
    assert "listFieldShapes(listName)" in probe
    assert "fresh" in probe
    # Post-write verifies bypass the cache.
    assert "readFieldShape(listName, field.title, field, true)" in js


def test_seal_phases_run_lanes_and_verify_via_enumeration(tmp_path: Path) -> None:
    """Live DEBUG timing: seal 13.3s + unseal 7.6s of a 52s run. Both now
    lane per list (same-list field MERGEs race into save conflicts). Seal
    verification never trusts phase-start state, but it no longer pays one
    fresh GET per column: the lane invalidates ITS list's snapshot after
    writing and one fresh enumeration serves every column's readback."""
    js = _generate_views_js(tmp_path)
    assert "mapLanes([...sealByList.entries()]" in js
    assert "invalidateFieldShapes(listTitle);  // verify from post-write state" in js
    # Per-list (argument) invalidation must exist alongside the full reset.
    assert "delete fieldShapesByList[listName];" in js
    # Unseal lanes per list too, and by the same grouping now that its lane
    # boundary is also a batch boundary.
    assert "mapLanes([...unsealByList.entries()], ([listTitle]) => listTitle" in js
    # Preflight (read-only) lanes both waves; field wave waits on shapes.
    assert "mapLanes(SCHEMA.lists, (list) => list.title" in js
    assert "SCHEMA.lists.filter((list) => preflightListShapes[list.title])" in js


def test_view_verify_rides_one_fresh_readback(tmp_path: Path) -> None:
    """Steady-state views paid three decision GETs per view (formatting
    current, preFlag, viewfields readback) on top of the fail-closed verify.
    Decision reads now reuse the phase-start enumeration shape; the verify
    stays fresh and carries ViewFields via $expand (one GET, same gate)."""
    js = _generate_views_js(tmp_path)
    assert "const current = existing || await readViewShape(viewUrl);" in js
    assert "const preFlag = existing || await readViewShape(viewUrl);" in js
    assert "(actual.ViewFields && actual.ViewFields.Items && actual.ViewFields.Items.results)" in js


def test_digest_is_cached_until_near_expiry(tmp_path: Path) -> None:
    js = _generate_views_js(tmp_path)
    assert "digestExpiresAt" in js
    assert "FormDigestTimeoutSeconds" in js


def test_view_fields_ride_the_enumeration(tmp_path: Path) -> None:
    js = _generate_views_js(tmp_path)
    assert "$expand=ViewFields" in js
    assert "existing.ViewFields.Items.results" in js


def test_deploy_runs_per_list_lanes(tmp_path: Path) -> None:
    """Concurrent schema writes to the SAME list race into save conflicts;
    different lists are independent. So the parallelism unit is the list:
    mapLanes runs one strictly-sequential lane per list, lanes concurrent."""
    js = _generate_views_js(tmp_path)
    assert "async function mapLanes" in js
    assert "mapLanes(SCHEMA.views, (view) => view.list" in js
    # Lists phase: wave 1 sequential (lookup targets need GUIDs), wave 2
    # field provisioning in per-list lanes.
    assert "mapLanes(fieldWork, (list) => list.title" in js


def test_a_lifted_save_rule_is_restored_on_every_exit_path() -> None:
    """MEASURED 2026-09-13, `library.folder.add-with-list-validation` in
    folder-under-schema-probe.js: a list save rule refuses a folder create on
    a library, so the folder phase lifts it and puts it back.

    The same guarantee the re-seal carries, and for the same reason: every
    phase between the lift and the restore can return early by design, and
    each of those returns would otherwise end the run with a library
    accepting saves its declaration forbids. So the backstop sits on the exit
    path, which is the only path every abort shares, and it is guarded
    separately from the re-seal so neither can skip the other.
    """
    js = _generate_simple_js()

    assert "const listValidationLiftedForRun = new Map();" in js
    assert "listValidationLiftedForRun.set(" in js
    assert "async function restoreLiftedListValidation()" in js
    finally_block = js.rsplit("} finally {", 1)[1]
    baseline = finally_block.index("const errorsBeforeCleanup = summary.errors.length;")
    correction = finally_block.index("const cleanupErrors = summary.errors.length")
    restore = finally_block.index("await restoreLiftedListValidation();")
    assert baseline < restore < correction
    assert "summary.errors.push({ phase: 'exit', error: `restore list save rules" in finally_block


def test_a_lifted_save_rule_is_registered_before_the_lift_is_verified() -> None:
    """The same ordering the unseal batch carries. A MERGE SharePoint commits
    and whose response is lost has to be put back by exit cleanup, so the
    registration is a fact about the request rather than about its answer."""
    js = _generate_simple_js()
    folders = next(
        part for part in js.split("// === Phase ") if part.startswith(
            f"{pn('folders')}: declared folders",
        )
    )
    assert folders.index("listValidationLiftedForRun.set(") < folders.index(
        "const cleared = await readListShape",
    )


def test_a_restored_save_rule_is_read_back_and_compared_canonically() -> None:
    """SharePoint strips removable brackets on save, so `[Status]` is stored
    and read back as `Status`. A byte comparison would report a restore that
    landed as a restore that failed, and the operator would be sent to repair
    a list that is already correct."""
    js = _generate_simple_js()
    restore = js.split("async function restoreListValidation", 1)[1].split(
        "async function restoreLiftedListValidation", 1,
    )[0]

    patch = restore.index("await patchListById(")
    readback = restore.index("const after = await readListShape", patch)
    identity = restore.index("after.Id !== listId", readback)
    compared = restore.index("canonicalFormula(after.ValidationFormula", identity)
    cleared = restore.index("listValidationLiftedForRun.delete(listTitle)", compared)
    assert patch < readback < identity < compared < cleared
