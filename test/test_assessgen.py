# test/test_assessgen.py
import json
import re
import textwrap
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from _model import bundle as make_bundle
from _model import column
from _model import schema as make_schema
from _model import table as make_table
from _node import NODE, run_node
from _paths import EXPECTED, FIXTURES, write_golden

from dbml_sharepoint.analysis.list_description import family_for, marker_for
from dbml_sharepoint.generators.assessgen import (
    assess_targets,
    derive_requirements,
    generate_assess_js,
)
from dbml_sharepoint.generators.jsgen import build_schema_json
from dbml_sharepoint.model.conditions import Leaf
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import (
    ColumnValidation,
    EntitySection,
    ListPermissionPolicy,
    MappingBundle,
    PermissionsConfig,
    Principal,
    RoleAssignment,
    SiteGroup,
    Versioning,
)
from dbml_sharepoint.model.parser import Schema, parse_dbml
from dbml_sharepoint.model.release import load_release


def _simple() -> tuple[Schema, MappingBundle]:
    return (
        parse_dbml(FIXTURES / "simple.dbml"),
        load_mapping(FIXTURES / "sharepoint-mapping.yaml"),
    )


def test_always_requirements_present() -> None:
    schema, bundle = _simple()
    keys = {r.key for r in derive_requirements(schema, bundle, "default")}
    assert {"manage_lists_bit", "site_not_locked"} <= keys
    assert "collision:APP_Project" in keys
    assert "collision:APP_Task" in keys


def test_base_template_requirements_from_entities() -> None:
    schema, bundle = _simple()
    keys = {r.key for r in derive_requirements(schema, bundle, "default")}
    assert "list_template_100" in keys


def test_conditional_requirements_absent_on_bare_mapping() -> None:
    schema = make_schema(make_table("Risk", column("Title", required=True)))
    bundle = make_bundle(entities=["Risk"])
    keys = {r.key for r in derive_requirements(schema, bundle, "default")}
    assert "manage_permissions_bit" not in keys
    assert "process_query" not in keys
    assert "sealed_surface" not in keys
    t = assess_targets(schema, bundle, "default")
    assert t["list_titles"] == ["APP_Risk"]
    assert t["base_templates"] == [100]
    assert t["declares_groups"] is False


def test_styled_pack_requirements() -> None:
    # `versioning_default` is spelled out even though it repeats the loader's
    # own default: this test is about what a mapping DECLARES, and a silent
    # default would make `version_trim_mode` below look derived from nothing.
    #
    # `column_formatting` carries an inline formatter rather than the
    # `{style: severity}` shorthand the YAML form used. `derive_requirements`
    # reads only `bool(mapping.column_formatting)`, and the shorthand's whole
    # effect is the expansion the loader performs into exactly that field.
    schema = make_schema(make_table("Risk", column("Title", required=True)))
    bundle = make_bundle(
        entities=["Risk"],
        seal_columns=True,
        prevent_list_deletion=True,
        versioning_default=Versioning(
            enable_versioning=True, major_version_limit=500, enable_minor_versions=False,
        ),
        column_formatting={"Risk": {"Title": {"elmType": "div"}}},
        permissions=PermissionsConfig(
            levels=[],
            groups=[
                SiteGroup(
                    name="G",
                    description="d",
                    owner_group="Site Owners",
                    allow_members_edit_membership=False,
                    allow_request_to_join_leave=False,
                    auto_accept_request_to_join_leave=False,
                    only_allow_members_view_membership=False,
                ),
            ],
            default_policy=None,
            overrides={},
        ),
    )
    reqs = {r.key: r for r in derive_requirements(schema, bundle, "default")}
    assert reqs["manage_permissions_bit"].level_on_fail == "BLOCKED"
    assert reqs["process_query"].level_on_fail == "WARN"
    assert reqs["sealed_surface"].level_on_fail == "WARN"
    assert reqs["allow_deletion_surface"].level_on_fail == "WARN"
    assert reqs["custom_formatter_surface"].level_on_fail == "WARN"
    assert reqs["version_trim_mode"].level_on_fail == "WARN"


def test_version_trim_is_not_probed_when_no_list_here_versions() -> None:
    """The versioning question is asked of the lists THIS SCRIPT provisions.

    It used to be asked of the whole mapping: `default.enable_versioning or
    any(override.get("enable_versioning") for every override)`. Both halves
    were wrong in the same direction. The `any` looked at entities belonging
    to other site roles, which this script never touches; and it read the raw
    override with bare truthiness, so a YAML `"false"` counted as on.

    Either way assess.js probed for a version surface on a site where nothing
    versions -- a WARN nobody can act on, which is how a warning stops being
    read. `Mapping.versioning_for` merges the override onto the default the
    same way jsgen deploys it, and the entity is filtered by role first.
    """
    schema = make_schema(make_table("Risk", column("Title", required=True)))
    bundle = make_bundle(
        entities=["Risk"],
        versioning_default=Versioning(enable_versioning=False),
        # An override that turns versioning on -- for an entity that is not
        # in the schema at all, and so is provisioned by no site role.
        versioning_overrides={"SomeOtherRoleEntity": {"enable_versioning": True}},
    )

    assert assess_targets(schema, bundle, "default")["declares_versioning"] is False
    assert "version_trim_mode" not in {
        r.key for r in derive_requirements(schema, bundle, "default")
    }


def test_version_trim_is_probed_when_an_override_turns_versioning_on() -> None:
    """The other direction: the default is off and one deployed list opts in.

    Pinned beside the negative case so the rule above cannot be satisfied by
    a `declares_versioning` that is simply always False.
    """
    schema = make_schema(make_table("Risk", column("Title", required=True)))
    bundle = make_bundle(
        entities=["Risk"],
        versioning_default=Versioning(enable_versioning=False),
        versioning_overrides={"Risk": {"enable_versioning": True}},
    )

    assert assess_targets(schema, bundle, "default")["declares_versioning"] is True


def test_manage_permissions_required_even_with_inheritance_left_alone() -> None:
    """#166 item 5: a per-list ACL policy that leaves inheritance intact
    (`break_inheritance: false`) still BINDS role assignments on the list, so
    it still needs ManagePermissions -- deploy.js's own preflight
    (`_field_reconcile.js.j2`) and the manifest (`manifest.md.j2`) already
    agreed on that. assess_targets used to test `declares_break_inheritance`
    instead of "a policy exists", so a mapping with zero custom permission
    levels/groups but a `break_inheritance: false` default policy made
    assess.js predict no requirement while deploy.js aborted with
    `insufficient-permissions` -- assess.js exists precisely to predict what
    deploy.js will refuse. Reproduced against the real loader with zero
    validator findings before this test was written; see the PR body for
    #166 for the full repro.

    Built-in level ("Contribute") and built-in associated group deliberately
    -- no custom `permission_levels` or `groups` declared -- so this fixture
    is the minimal one that isolates the `declares_break_inheritance` defect
    from `declares_groups`/`declares_permission_levels`, which were already
    correct.
    """
    schema = make_schema(make_table("Risk", column("Title", required=True)))
    bundle = make_bundle(
        entities=["Risk"],
        permissions=PermissionsConfig(
            levels=[],
            groups=[],
            default_policy=ListPermissionPolicy(
                break_inheritance=False,
                assignments=[
                    RoleAssignment(
                        principal=Principal(kind="associated_member_group"),
                        level="Contribute",
                    ),
                ],
            ),
            overrides={},
        ),
    )
    t = assess_targets(schema, bundle, "default")
    assert t["declares_groups"] is False
    assert t["requires_manage_permissions"] is True
    keys = {r.key for r in derive_requirements(schema, bundle, "default")}
    assert "manage_permissions_bit" in keys


def _assess_js() -> str:
    from dbml_sharepoint.generators.assessgen import generate_assess_js
    from dbml_sharepoint.model.release import load_release
    schema, bundle = _simple()
    return generate_assess_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default", source_dbml="simple.dbml",
        generated_at="2026-05-04T00:00:00Z",
    )


def test_simple_assess_js_matches_golden() -> None:
    """The only byte-level check on assess.js.j2.

    Every other test here covers the generator's inputs or asserts that a
    string is present in the output, so a probe could be dropped from a tier
    and every gate would stay green.
    """
    golden_path = EXPECTED / "simple-assess.js"
    assert golden_path.exists(), f"Golden file missing: {golden_path}"
    expected = golden_path.read_text(encoding="utf-8")
    assert _assess_js() == expected, (
        "the emitted assess script changed. Review the diff, then regenerate "
        "with `uv run python test/test_assessgen.py`."
    )


def test_assess_is_read_only() -> None:
    js = _assess_js()
    assert "'X-HTTP-Method'" not in js and '"X-HTTP-Method"' not in js
    posts = re.findall(r"method:\s*'POST'", js)
    for m in re.finditer(r"method:\s*'POST'", js):
        window = js[max(0, m.start() - 400): m.start() + 400]
        assert any(tok in window for tok in ("contextinfo", "ProcessQuery")), window
    assert posts, "expected at least the contextinfo POST"


def test_assess_tier1_probes_present() -> None:
    js = _assess_js()
    assert "GetAvailableTagsForSite" in js
    assert "EffectiveBasePermissions" in js
    assert "web/listtemplates" in js.lower()
    assert "ReadOnly" in js and "LockIssue" in js
    assert "WebTemplate" in js
    assert "[SP-ASSESS]" in js
    assert "apiUrl" in js and "odataName" in js


def test_assess_derived_probes_present() -> None:
    js = _assess_js()
    assert "APP_Project" in js and "APP_Task" in js
    assert "list_template_100" in js
    assert "_spPageContextInfo" in js
    assert "site-mismatch" in js


def test_assess_verdict_line() -> None:
    js = _assess_js()
    assert "COMPATIBLE" in js and "DEGRADED" in js and "BLOCKED" in js
    assert "pack:" in js


def test_assess_manifest_lists_requirements_and_honesty() -> None:
    from dbml_sharepoint.generators.assessgen import generate_assess_manifest
    schema, bundle = _simple()
    md = generate_assess_manifest(
        schema=schema, bundle=bundle,
        site_url="https://x.sharepoint.com/sites/t", site_role="default",
    )
    assert "# Site assessment" in md
    assert "manage_lists_bit" in md
    assert "APP_Project" in md
    assert "## Not assessable" in md
    assert "Power Automate" in md


def test_assess_header_carries_full_provenance() -> None:
    """Same traceability contract as deploy.js/rollback.js headers."""
    js = _assess_js()
    assert "Release tag:  0.1.0-test" in js
    assert "Schema:       v0.8" in js
    assert "Deployer:     vdbml-sharepoint/0.1.0" in js
    assert "Generated at: 2026-05-04T00:00:00Z" in js


# === The provenance marker (read-only) ======================================
#
# Every test above this line is string presence against the generated text.
# That cannot tell a probe that RUNS from one that throws, reads the wrong
# property, or never fires. The marker check is exactly the kind of rule this
# repository's evidence rule is about -- it would emit, lint, and stay silent
# forever -- so it is asserted by executing the emitted script.


def _declared_descriptions(
    pack: tuple[Schema, MappingBundle] | None = None,
) -> dict[str, str]:
    """List title -> the Description a real deploy leaves on that list.

    Read out of the DEPLOY generator, not out of assess's own `list_markers`.
    Building the "correct" fixture from the code under test would make the
    quiet run agree with whatever assess happens to believe; taking it from
    `build_schema_json` is the point -- it is what the site actually holds
    after a deploy, so this pins assess against the deploy.

    Defaults to the simple pack; `pack` reads another schema and mapping.
    """
    schema, bundle = pack if pack is not None else _simple()
    schema_json = build_schema_json(schema, bundle, "default")
    return {entry["title"]: entry["description"] for entry in schema_json["lists"]}


def test_assess_targets_carry_the_marker_from_the_shared_speller() -> None:
    """Imported, never re-spelled.

    A second spelling of the marker would let assess.js disagree with
    deploy.js about the very same list: the deploy writes one string, assess
    looks for another, and the operator is told a correctly provisioned list
    has lost its provenance (or, worse, is told nothing about one that has).
    Compared against `marker_for` itself rather than against a literal, so a
    deliberate change to the marker moves both sides together.
    """
    schema, bundle = _simple()
    family = family_for(schema)
    assert assess_targets(schema, bundle, "default")["list_markers"] == [
        ("APP_Project", marker_for(family, "Project")),
        ("APP_Task", marker_for(family, "Task")),
        # The settings list the mapping adds. Every list this pack provisions
        # needs a marker, not only the ones the DBML declares.
        ("APP_AppSettings", marker_for(family, "AppSettings")),
    ]


def test_every_provisioned_list_has_a_blocking_marker_requirement() -> None:
    """A list with no exact marker has no ownership evidence. Ordinary deploy
    must not manufacture that evidence by stamping a title collision.

    Over EVERY list the deploy provisions, not over two named ones: a rule
    that covers all but one list is indistinguishable from a rule that works,
    right up until the uncovered list is the one that collides.
    """
    schema, bundle = _simple()
    reqs = {r.key: r for r in derive_requirements(schema, bundle, "default")}
    for title in _declared_descriptions():
        key = f"{_MARKER_KEY}{title}"
        assert key in reqs, f"no marker requirement for '{title}': {sorted(reqs)}"
        assert reqs[key].level_on_fail == "BLOCKED", reqs[key]


# The key prefix the marker check owns. Findings are selected by KEY, never by
# the word "marker" turning up in a detail string: an unrelated WARN that
# happens to mention one would otherwise join the set and fail assertions
# about keys it has nothing to do with.
_MARKER_KEY = "provenance_marker:"

# A site whose declared lists all exist. Everything the assessment asks for
# beyond that answers as an empty, healthy shape -- the thin-mock findings
# that follow from it are not what these tests measure.
_ASSESS_HARNESS = textwrap.dedent(r"""
    globalThis.window = { location: { origin: 'https://example.sharepoint.com' } };
    // A healthy site reports its time zone, and this "browser" sits in it:
    // UTC on both sides, so the time_zone finding cannot depend on the
    // machine running the tests.
    Date.prototype.getTimezoneOffset = () => 0;
    globalThis._spPageContextInfo = {
      webServerRelativeUrl: '/sites/test',
      userLoginName: 'probe@example.com',
      userId: 1,
    };
    // What each declared list HOLDS in its Description before the run. A
    // title absent from this map is a list that does not exist, answered 404
    // exactly as SharePoint would. Rewritten by _run_assess.
    //
    // A Map, for the same reason the emitted script uses one: an object
    // literal drops a `__proto__` key, so the mock would answer 404 for the
    // one list whose title this suite most needs to hold.
    const LIST_DESCRIPTIONS = new Map([]);
    // The list title out of a URL, back in the spelling the declaration uses.
    // Non-greedy to the first `')`, then undo odataName's two encodings in
    // the order it applied them: percent first, apostrophe-doubling second.
    // `[^']+` would stop at the first apostrophe of an OData-escaped title
    // and bucket its state under the wrong key -- silently, and in the
    // direction where a check looks like it passed.
    const listOf = (url) => {
      const raw = (url.match(/getbytitle\('(.*?)'\)/) || [])[1];
      return raw == null ? raw : decodeURIComponent(raw).replace(/''/g, "'");
    };
    // A GET of the LIST OBJECT itself: the path ends at getbytitle(...) with
    // nothing after it. `[^/]*` and the `$` anchor together. `.*` would
    // backtrack across `')/fields/getbyinternalnameortitle('`, so a field
    // enumeration would be answered with the LIST payload -- and a check that
    // read Description off the wrong response would still appear to work. A
    // SharePoint list title cannot contain `/`, and encodeURIComponent would
    // percent-encode one anyway.
    const LIST_OBJECT = /\/lists\/getbytitle\('[^/]*'\)$/;
    const respond = (status, payload) => ({
      ok: status < 400, status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });
    const body = (url) => {
      if (url.includes('contextinfo')) {
        return { d: { GetContextWebInformation: {
          FormDigestValue: 'digest', FormDigestTimeoutSeconds: 1800,
          LibraryVersion: '16.0.0.0' } } };
      }
      if (url.toLowerCase().includes('effectivebasepermissions')) {
        return { d: { EffectiveBasePermissions: { High: 4294967295, Low: 4294967295 } } };
      }
      return { d: { results: [] } };
    };
    globalThis.fetch = async (url) => {
      const u = String(url);
      const path = u.split('?')[0];
      if (LIST_OBJECT.test(path)) {
        const title = listOf(path);
        if (!LIST_DESCRIPTIONS.has(title)) {
          return respond(404, { error: { message: { value: `List '${title}' not found` } } });
        }
        return respond(200, { d: {
          Title: title, BaseTemplate: 100, Description: LIST_DESCRIPTIONS.get(title),
        } });
      }
      // The list-title enumeration (web/lists?$select=Title...). Answers every
      // EXISTING list's Title so the assess collision probe reads absence from
      // a 200 with an empty set, exactly as a real tenant does -- not a
      // getbytitle 404.
      if (path.endsWith('/lists')) {
        return respond(200, {
          d: { results: [...LIST_DESCRIPTIONS.keys()].map((t) => ({ Title: t })) },
        });
      }
      if (path.toLowerCase().endsWith('/regionalsettings/timezone')) {
        // Spelled with a bracket key: `_description_absent_harness` strips
        // every description key to model a list whose description is not
        // reported, and the zone's own description must survive that.
        const zone = { Id: 93, Information: { Bias: 0, StandardBias: 0, DaylightBias: 0 } };
        zone['Description'] = '(UTC) Coordinated Universal Time';
        return respond(200, { d: zone });
      }
      return respond(200, body(u));
    };
""")


def test_the_assess_harness_matcher_separates_a_list_from_what_nests_under_it() -> None:
    """The harness's own matcher, pinned in BOTH directions.

    It decides which response a probe gets, so getting it wrong does not look
    like a broken mock -- it looks like a passing check. `[^']+` cannot match
    an OData-escaped apostrophe (`odataName` doubles `'` and
    encodeURIComponent leaves it alone), and `.*` backtracks far enough to
    answer a field enumeration with the list payload.
    """
    matcher = re.compile(r"/lists/getbytitle\('[^/]*'\)$")
    escaped = "/sites/x/_api/web/lists/getbytitle('O''Brien%20Register')"
    plain = "/sites/x/_api/web/lists/getbytitle('APP_Project')"
    assert matcher.search(escaped), "an escaped apostrophe was not matched"
    assert matcher.search(plain)
    for nested in (
        f"{escaped}/fields",
        f"{plain}/fields/getbyinternalnameortitle('Note')",
        f"{plain}/contenttypes",
    ):
        assert not matcher.search(nested), f"a nested path read as the list object: {nested}"
    assert _ASSESS_HARNESS.count(r"/\/lists\/getbytitle\('[^/]*'\)$/") == 1, (
        "the harness no longer uses the matcher this test pins"
    )


def _locked_harness() -> str:
    """Return the harness above with the same site answering as locked.

    Only `site?$select=ReadOnly,LockIssue` carries `ReadOnly` in its URL, so
    this one branch reaches the BLOCKED arm. The splice is asserted here
    rather than at import, so a harness edit that breaks it fails the one test
    that uses it instead of erasing the whole module from the run.
    """
    locked = _ASSESS_HARNESS.replace(
        "const body = (url) => {\n",
        "const body = (url) => {\n"
        "  if (url.includes('ReadOnly')) {\n"
        "    return { d: { ReadOnly: true, LockIssue: 'Locked for migration' } };\n"
        "  }\n",
    )
    assert locked != _ASSESS_HARNESS, "the locked branch was not spliced in"
    return locked


def _run_assess(
    list_description: str | Mapping[str, str | None],
    *,
    harness: str = _ASSESS_HARNESS,
    js: str | None = None,
) -> dict[str, Any]:
    """Execute the emitted assess.js against a site holding `list_description`.

    One string applies to every declared list; a mapping sets them per title.
    `harness` swaps the mocked site for a variant, such as a locked one, and
    `js` for a script generated from another pack. Returns the summary the
    script resolves with.
    """
    held = (
        dict.fromkeys(_declared_descriptions(), list_description)
        if isinstance(list_description, str) else dict(list_description)
    )
    js = _assess_js() if js is None else js
    assert js.count("})();") == 1, "the IIFE terminator is no longer unique"
    mocked = harness.replace(
        "const LIST_DESCRIPTIONS = new Map([]);",
        f"const LIST_DESCRIPTIONS = new Map({json.dumps(list(held.items()))});",
    )
    script = mocked + "\n" + js.replace(
        "})();", "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    ).replace("(async () => {", "((async () => {", 1)
    output = run_node(script)
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert line is not None, f"assess.js did not return a summary:\n{output[-3000:]}"
    summary: dict[str, Any] = json.loads(line.removeprefix("__RESULT__"))
    # Without this, "no marker warning was raised" would also be true of a run
    # that aborted in the site guard and probed nothing at all.
    assert summary.get("verdict"), f"assess.js reached no verdict:\n{output[-3000:]}"
    return summary


def _marker_findings(
    summary: dict[str, Any], *, levels: set[str],
) -> list[dict[str, Any]]:
    """The marker check's own findings at `levels`, selected by key.

    WARN and BLOCKED are the levels the verdict consumes; PASS and INFO are
    not. See `_MARKER_KEY` for why the key rather than the detail.
    """
    return [
        f for f in summary["findings"]
        if f["key"].startswith(_MARKER_KEY) and f["level"] in levels
    ]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_assess_reports_a_provisioned_list_whose_marker_is_missing() -> None:
    """Between deploys nothing else can see this.

    The deploy repairs a drifted description at the NEXT run. Until then the
    fleet query returns fewer rows and cannot know it should have returned
    more, so this read-only check is the only thing standing between an
    edited description and a silently short report.
    """
    titles = list(_declared_descriptions())
    summary = _run_assess("an owner rewrote this")
    blocked = _marker_findings(summary, levels={"WARN", "BLOCKED"})
    assert blocked, (
        "a declared list carrying no provenance marker drew no finding: "
        f"{summary['findings']}"
    )
    # EVERY list, not the first one. A `break` in the collision loop leaves a
    # site where list one is checked and lists two through forty are not, and
    # an `any(...)` assertion cannot tell that from a working check.
    for title in titles:
        assert any(title in f["detail"] for f in blocked), (
            f"'{title}' lost ownership evidence and nothing said so; the finding "
            f"must name every affected list: {blocked}"
        )
    assert all(f["level"] == "BLOCKED" for f in blocked), blocked
    assert summary["verdict"] == "BLOCKED"
    # And it must actually REACH the verdict. That loop walks the requirement
    # keys, so a WARN nobody declared a requirement for is logged and then
    # ignored -- the operator reads COMPATIBLE on a site that is not.
    schema, bundle = _simple()
    declared = {r.key for r in derive_requirements(schema, bundle, "default")}
    assert {f["key"] for f in blocked} <= declared, (
        "blocked on keys no requirement covers, so the verdict ignores them: "
        f"{sorted({f['key'] for f in blocked} - declared)}"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_assess_is_quiet_when_every_marker_is_present() -> None:
    """A check that always fires is noise, and noise gets ignored."""
    declared = _declared_descriptions()
    # Without this the run is vacuous: if the deploy generator stopped
    # emitting markers altogether, an empty description would also draw no
    # complaint and nothing here would notice.
    assert declared and all(
        "Provisioned by dbml-sharepoint" in value for value in declared.values()
    ), declared
    summary = _run_assess(declared)
    noisy = _marker_findings(summary, levels={"WARN", "BLOCKED"})
    assert not noisy, f"a correctly marked list was reported as drifted: {noisy}"
    # Silence has to come from the check PASSING, not from its never having
    # run: deleting it outright would satisfy the assertion above. Per list,
    # for the same reason the sibling test is -- a check that stops after the
    # first list is silent about the rest, which looks exactly like this.
    passed = _marker_findings(summary, levels={"PASS"})
    for title in declared:
        assert any(title in f["detail"] for f in passed), (
            f"the marker check never ran for '{title}': {summary['findings']}"
        )


def _description_absent_harness() -> str:
    """`_ASSESS_HARNESS` answering the list object without a `Description`.

    The list still exists and still answers 200. Only the property the marker
    check reads is missing, which is the shape that made every declared list
    look drifted.
    """
    absent = _ASSESS_HARNESS.replace(
        " Description: LIST_DESCRIPTIONS.get(title),", "",
    )
    assert absent != _ASSESS_HARNESS, "the Description was not dropped"
    assert "Description:" not in absent, "the mock still answers with one"
    return absent


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_unreported_description_is_not_a_lost_marker() -> None:
    """An unreported Description used to raise a WARN that was simply wrong.

    It told an operator that fleet reporting could not see a list, for every
    declared list on the site, on the strength of a property the probe never
    reported. Since #279 the WARN degrades the verdict and stops the deploy.
    """
    titles = list(_declared_descriptions())
    summary = _run_assess(
        _declared_descriptions(), harness=_description_absent_harness(),
    )
    assert not _marker_findings(summary, levels={"WARN", "BLOCKED"}), summary["findings"]
    # Silence has to come from saying nobody could tell, not from the check
    # having been deleted: every declared list still gets its own finding.
    unchecked = _marker_findings(summary, levels={"NOT-ASSESSABLE"})
    assert len(unchecked) == len(titles), unchecked
    for title in titles:
        assert any(title in f["detail"] for f in unchecked), (title, unchecked)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_description_reported_as_empty_still_loses_its_marker() -> None:
    """A Description reported as empty sits on the other side of this line.

    A list whose Description SharePoint reported as empty has genuinely lost
    the marker, and a fix that treated absent and empty alike would silence
    the rule it was meant to leave alone.
    """
    summary = _run_assess("")
    blocked = _marker_findings(summary, levels={"BLOCKED"})
    assert {f["key"] for f in blocked} == {
        f"{_MARKER_KEY}{title}" for title in _declared_descriptions()
    }, blocked
    assert summary["verdict"] == "BLOCKED"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_description_reported_as_null_is_blocked_not_unassessable() -> None:
    held = dict.fromkeys(_declared_descriptions(), None)

    summary = _run_assess(held)

    blocked = _marker_findings(summary, levels={"BLOCKED"})
    assert {finding["key"] for finding in blocked} == {
        f"{_MARKER_KEY}{title}" for title in held
    }
    assert summary["verdict"] == "BLOCKED"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_missing_generated_marker_contract_blocks_assessment() -> None:
    schema, bundle = _simple()
    title, marker = assess_targets(schema, bundle, "default")["list_markers"][0]
    js = _assess_js()
    mutated, count = js.replace(json.dumps(marker), "null", 1), js.count(json.dumps(marker))
    assert count == 1, "the selected marker was not emitted exactly once"

    summary = _run_assess(_declared_descriptions(), js=mutated)

    finding = next(
        item
        for item in summary["findings"]
        if item["key"] == f"{_MARKER_KEY}{title}"
    )
    assert finding["level"] == "BLOCKED"
    assert summary["verdict"] == "BLOCKED"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_list_named_proto_still_gets_its_marker_checked() -> None:
    """A title of `__proto__` used to make the marker check return silently.

    `list_markers` was emitted as a JS object literal. `{"__proto__": "..."}`
    invokes the prototype setter instead of creating an own property, so the
    guard's `hasOwnProperty` was false, `markerFinding` returned before
    emitting PASS or WARN, and a list with no provenance marker still
    assessed as compatible. The check added to catch a missing marker was the
    one that stayed quiet.

    The prefix is empty because #190 made it optional, which is what lets a
    declared title be exactly `__proto__`.

    The WHOLE emitted script is run under Node, in both directions, rather
    than a Python-side probe that re-spells how the script builds its lookup.
    Re-spelling it covers only the emission side, and the same defect
    reintroduced on the consumption side leaves such a probe green.
    """
    import _model

    from dbml_sharepoint.generators.assessgen import generate_assess_js
    from dbml_sharepoint.model.release import load_release

    schema = _model.schema(_model.table("__proto__", "Title"))
    bundle = _model.bundle(entities=["__proto__"], prefix="")
    js = generate_assess_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default", source_dbml="simple.dbml",
        generated_at="2026-05-04T00:00:00Z",
    )
    declared = _declared_descriptions((schema, bundle))
    assert list(declared) == ["__proto__"], declared

    drifted = _run_assess({"__proto__": "an owner rewrote this"}, js=js)
    assert [
        (f["key"], f["level"])
        for f in _marker_findings(drifted, levels={"WARN", "BLOCKED"})
    ] == [("provenance_marker:__proto__", "BLOCKED")], (
        f"a list named __proto__ lost its marker and nothing said so: "
        f"{drifted['findings']}"
    )

    marked = _run_assess(declared, js=js)
    assert [
        (f["key"], f["level"]) for f in _marker_findings(marked, levels={"PASS"})
    ] == [("provenance_marker:__proto__", "PASS")], (
        f"the marker check never ran for a list named __proto__: "
        f"{marked['findings']}"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_assessment_records_every_finding_in_order() -> None:
    """Every finding the run records, in order, with the detail it carries.

    A sampled assertion cannot see a dropped probe, which is what moving the
    whole body into a partial is most likely to introduce.

    `detail` is projected as well as the triple. The Tier 3 entries all share
    one key, so `(tier, key, level)` alone would pin their count and let a
    reworded item through.

    One tab-separated line per finding rather than a list of tuples: the
    failure then reads as a line diff naming the probe that moved, instead of
    a truncated dump of two thirty-four element lists.
    """
    summary = _run_assess(_declared_descriptions())
    recorded = "".join(
        f"{f['tier']}\t{f['key']}\t{f['level']}\t{f['detail']}\n"
        for f in summary["findings"]
    )
    # Emission order, not tier order: `list_template_100` is raised from inside
    # the Tier 1 block of `_assess_body.js.j2` but carries tier 2.
    assert recorded == (
        "1\tweb_template\tINFO\tTemplate (not reported)#(not reported), LCID "
        "(not reported).\n"
        "1\tsite_not_locked\tNOT-ASSESSABLE\tThe site answered without ReadOnly or "
        "LockIssue, so whether it is locked is unknown.\n"
        "1\tplatform_build\tINFO\tSharePoint build 16.0.0.0.\n"
        "1\tmanage_lists_bit\tPASS\tOperator holds ManageLists.\n"
        "1\tmanage_permissions_bit\tPASS\tOperator holds ManagePermissions (or is a site "
        "collection admin).\n"
        "1\tnoscript\tINFO\tCustom scripting allowed (AddAndCustomizePages present).\n"
        "2\tlist_template_100\tWARN\tBase template 100 not listed by web/listtemplates "
        "(creation may still work).\n"
        "1\tregional_settings\tINFO\tSite LocaleId (not reported).\n"
        "1\ttime_zone\tINFO\tSite time zone \"(UTC) Coordinated Universal Time\" (UTC +0 "
        "min); this browser is UTC +0 min. They agree, so dates and times on this site "
        "read the same day this browser does.\n"
        "1\tlanguages\tINFO\tMultilingual (not reported); UI languages (none reported).\n"
        "1\tstorage\tINFO\tsite/usage did not report storage figures.\n"
        "1\thub\tINFO\tHub site (not reported); hub id (not reported).\n"
        "1\tretention_labels\tINFO\tNo retention labels available to this site.\n"
        "1\tapp_catalog\tINFO\tTenant app catalog not reported by this site.\n"
        "1\tcustom_actions\tINFO\t0 web custom action(s) / SPFx extension(s) registered.\n"
        "1\tsearch\tINFO\tSearch service responds.\n"
        "2\tcollision:APP_Project\tINFO\t'APP_Project' already exists (BaseTemplate 100); the "
        "ownership check below decides whether deploy may reconcile it.\n"
        "2\tprovenance_marker:APP_Project\tPASS\t'APP_Project' carries its provenance marker.\n"
        "2\tcollision:APP_Task\tINFO\t'APP_Task' already exists (BaseTemplate 100); the ownership "
        "check below decides whether deploy may reconcile it.\n"
        "2\tprovenance_marker:APP_Task\tPASS\t'APP_Task' carries its provenance marker.\n"
        "2\tcollision:APP_AppSettings\tINFO\t'APP_AppSettings' already exists (BaseTemplate "
        "100); the ownership check below decides whether deploy may reconcile it.\n"
        "2\tprovenance_marker:APP_AppSettings\tPASS\t'APP_AppSettings' carries its provenance "
        "marker.\n"
        "2\tcustom_formatter_surface\tPASS\tProperty surface present.\n"
        "2\tform_formatter_surface\tPASS\tProperty surface present.\n"
        "2\tversion_trim_mode\tNOT-ASSESSABLE\tThe list answered without "
        "VersionPolicies/DefaultTrimMode, so whether service-managed auto-trim overrides the "
        "declared MajorVersionLimit is unknown.\n"
        "2\tprocess_query\tPASS\tCSOM ProcessQuery responds (group owner correction available).\n"
        "3\tnot_assessable\tNOT-ASSESSABLE\tPower Automate / Power Apps inventory (lives in "
        "Power Platform APIs, no SharePoint REST surface from site context)\n"
        "3\tnot_assessable\tNOT-ASSESSABLE\tAudit settings (SSOM-only; not exposed via CSOM/REST)\n"
        "3\tnot_assessable\tNOT-ASSESSABLE\tInformation-barrier segments and mode (tenant-admin "
        "only)\n"
        "3\tnot_assessable\tNOT-ASSESSABLE\tAuthoritative tenant sharing capability and storage "
        "quota ceilings (tenant-admin SiteProperties)\n"
        "3\tnot_assessable\tNOT-ASSESSABLE\tRetention POLICY coverage of the site (only "
        "inferable via the Preservation Hold Library signal)\n"
        "3\tnot_assessable\tNOT-ASSESSABLE\tWebhook subscription enumeration (bound to the "
        "creating app identity)\n"
        "3\tnot_assessable\tNOT-ASSESSABLE\tEdit-form column-description suppression "
        "(SharePoint platform behaviour)\n"
        "3\tnot_assessable\tNOT-ASSESSABLE\t[$Created] view-field resolution in formatters "
        "(tenant/locale dependent)\n"
        "3\tnot_assessable\tNOT-ASSESSABLE\tFormat-pane JSON display encoding (renders "
        "identically either way)\n"
    )
    # DEGRADED rather than COMPATIBLE because the mock answers
    # `web/listtemplates` with an empty result set, so `list_template_100`
    # WARNs, and because two more required keys are answered by a payload
    # carrying none of the properties they select. `_healthy_harness` is what
    # answers all three.
    assert summary["verdict"] == "DEGRADED"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_locked_site_blocks_the_verdict() -> None:
    """DEGRADED alone leaves the verdict arithmetic under-exercised.

    BLOCKED has to win over the WARN the same run still raises.
    """
    summary = _run_assess(_declared_descriptions(), harness=_locked_harness())
    assert summary["verdict"] == "BLOCKED"
    assert [
        (f["tier"], f["key"], f["detail"])
        for f in summary["findings"] if f["level"] == "BLOCKED"
    ] == [
        (1, "site_not_locked", "Site is read-only/locked: Locked for migration."),
    ]
    # Pinned because a run that raised no warning at all would also be BLOCKED.
    assert [f["level"] for f in summary["findings"] if f["key"] == "list_template_100"] == [
        "WARN",
    ]


# The three permission keys one probe answers for. Named once, because the
# defect this covers was exactly that two of them went unmentioned.
_PERMISSION_KEYS = ("manage_lists_bit", "manage_permissions_bit", "noscript")


def _unreadable_permissions_harness() -> str:
    """`_ASSESS_HARNESS` answering 200 with no `EffectiveBasePermissions`.

    The request succeeds, so `.ok` is true and only the payload says nothing.
    That is the shape a site produces when it does not carry the property,
    and it is not the same as a request that failed.
    """
    unreadable = _ASSESS_HARNESS.replace(
        "{ d: { EffectiveBasePermissions: { High: 4294967295, Low: 4294967295 } } }",
        "{ d: {} }",
    )
    assert unreadable != _ASSESS_HARNESS, "the permissions payload was not emptied"
    return unreadable


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_unreadable_permissions_leave_no_required_key_unspoken() -> None:
    """One finding for three keys let a BLOCKED requirement pass unchecked.

    The `else` arm raised `manage_lists_bit` alone, so `manage_permissions_bit`
    and `noscript` reached the verdict loop with no finding at all, and
    `if (!f) continue;` treats a key nobody answered for as nothing to say.
    This pack requires `manage_permissions_bit` at BLOCKED.
    """
    schema, bundle = _simple()
    required = {r.key: r for r in derive_requirements(schema, bundle, "default")}
    assert required["manage_permissions_bit"].level_on_fail == "BLOCKED"

    summary = _run_assess(
        _declared_descriptions(), harness=_unreadable_permissions_harness(),
    )
    spoken = {
        f["key"]: f["level"] for f in summary["findings"] if f["key"] in _PERMISSION_KEYS
    }
    assert spoken == dict.fromkeys(_PERMISSION_KEYS, "NOT-ASSESSABLE"), spoken
    # The phantom status: `.ok` is true, so neither `status` nor `error` is set
    # and the arm used to print `HTTP undefined` at operator level.
    assert not any(
        "undefined" in f["detail"]
        for f in summary["findings"] if f["key"] in _PERMISSION_KEYS
    ), summary["findings"]
    # This harness also raises the `list_template_100` WARN, so the verdict
    # here cannot separate the two causes. `_healthy_harness` is what measures
    # the unread permissions on their own.
    assert summary["verdict"] == "DEGRADED"


#: The lock answer `_healthy_harness` splices in. Named once, because the
#: harness that takes it out again must not drift from the one that puts it in.
_LOCK_ANSWER = (
    "  if (url.includes('ReadOnly')) {\n"
    "    return { d: { ReadOnly: false, LockIssue: null } };\n"
    "  }\n"
)

#: The version-policy answer `_healthy_harness` splices in, named for the same
#: reason. It goes in ahead of the generic list payload rather than into
#: `body`, because the probe reads the list object itself with an `$expand`.
_VERSION_POLICY_ANSWER = (
    "  if (u.includes('VersionPolicies')) {\n"
    "    return respond(200, { d: { VersionPolicies: { DefaultTrimMode: 0 } } });\n"
    "  }\n"
)


def _healthy_harness(base: str = _ASSESS_HARNESS) -> str:
    """`base` with every question the thin mock leaves unanswered answered.

    `web/listtemplates` replies `{d: {results: []}}` to everything it does not
    name, and the site and version-policy probes are handed a payload carrying
    none of the properties they selected. Three requirement keys therefore
    degrade on every harness built from `_ASSESS_HARNESS`. A test whose verdict
    is meant to come from something else has to answer all three first.
    """
    stocked = base.replace(
        "const body = (url) => {\n",
        "const body = (url) => {\n"
        "  if (url.includes('listtemplates')) {\n"
        "    return { d: { results: [{ ListTemplateTypeKind: 100 }] } };\n"
        "  }\n"
        + _LOCK_ANSWER,
        1,
    )
    assert stocked != base, "the list-template branch was not spliced in"
    versioned = stocked.replace(
        "  if (LIST_OBJECT.test(path)) {\n",
        _VERSION_POLICY_ANSWER + "  if (LIST_OBJECT.test(path)) {\n",
        1,
    )
    assert versioned != stocked, "the version-policy branch was not spliced in"
    return versioned


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_healthy_site_is_compatible() -> None:
    """The control for every test that reads a DEGRADED off this harness.

    A DEGRADED there proves nothing unless a run answering every probe comes
    out COMPATIBLE, and no other harness in this module does: they degrade, or
    they block. It also pins that the Tier 3 honesty block, which is
    NOT-ASSESSABLE on every run, does not itself degrade, since its key
    `not_assessable` is not a requirement.
    """
    summary = _run_assess(_declared_descriptions(), harness=_healthy_harness())
    assert summary["verdict"] == "COMPATIBLE", [
        f for f in summary["findings"] if f["level"] in {"WARN", "BLOCKED"}
    ]
    assert any(f["key"] == "not_assessable" for f in summary["findings"]), (
        "the Tier 3 block stopped emitting, so this control proves nothing"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_requirement_nobody_could_assess_degrades_the_verdict() -> None:
    """A requirement nobody could check must not read as one that passed.

    Emitting NOT-ASSESSABLE per key stopped the verdict loop skipping the key
    entirely, and then the loop skipped the level instead: an otherwise
    healthy site whose permissions could not be read came out COMPATIBLE,
    which is weaker than the single WARN that preceded it. DEGRADED rather
    than BLOCKED, because nothing here says the requirement is unmet.
    """
    schema, bundle = _simple()
    required = {r.key for r in derive_requirements(schema, bundle, "default")}
    assert "manage_lists_bit" in required

    summary = _run_assess(
        _declared_descriptions(),
        harness=_healthy_harness(_unreadable_permissions_harness()),
    )
    assert summary["verdict"] == "DEGRADED", summary["findings"]
    # Nothing WARNed, so the DEGRADED can only have come from the level this
    # test is about.
    assert not [
        f for f in summary["findings"] if f["level"] in {"WARN", "BLOCKED"}
    ], summary["findings"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_unassessable_marker_degrades_the_verdict_too() -> None:
    """An unreadable Description is uncertainty, not proof of foreign ownership.

    It cannot pass the ownership requirement, but it also cannot honestly say
    the marker is absent. The deploy's fresh preflight read makes the decision.
    """
    summary = _run_assess(
        _declared_descriptions(),
        harness=_healthy_harness(_description_absent_harness()),
    )
    assert summary["verdict"] == "DEGRADED", summary["findings"]
    assert not [
        f for f in summary["findings"] if f["level"] in {"WARN", "BLOCKED"}
    ], summary["findings"]


def _unreported_lock_state_harness() -> str:
    """`_healthy_harness` with the site answering 200 and no lock properties.

    The request succeeds, so `.ok` is true and only the payload says nothing.
    That is the shape a site produces when it does not return the selected
    properties, and it is not the same as a request that failed.
    """
    answered = _healthy_harness()
    unreported = answered.replace(_LOCK_ANSWER, "", 1)
    assert unreported != answered, "the lock answer was not removed"
    return unreported


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_site_that_reports_no_lock_state_is_not_read_as_writable() -> None:
    """A PASS here is the strongest claim the assessment makes.

    `site_not_locked` is required at BLOCKED, and the claim was being made on a
    payload that carried neither `ReadOnly` nor `LockIssue`.

    The positive half is asserted with the negative: a repair that silenced
    the false PASS by never reporting the requirement at all would satisfy
    the first assertion on its own.
    """
    schema, bundle = _simple()
    required = {r.key: r for r in derive_requirements(schema, bundle, "default")}
    assert required["site_not_locked"].level_on_fail == "BLOCKED"

    summary = _run_assess(
        _declared_descriptions(), harness=_unreported_lock_state_harness(),
    )
    assert [
        f["level"] for f in summary["findings"] if f["key"] == "site_not_locked"
    ] == ["NOT-ASSESSABLE"], summary["findings"]
    assert summary["verdict"] == "DEGRADED", summary["findings"]
    # Nothing else degraded, so the verdict can only have come from this key.
    assert not [
        f for f in summary["findings"] if f["level"] in {"WARN", "BLOCKED"}
    ], summary["findings"]

    answered = _run_assess(_declared_descriptions(), harness=_healthy_harness())
    assert [
        f["level"] for f in answered["findings"] if f["key"] == "site_not_locked"
    ] == ["PASS"], answered["findings"]


def _unreported_version_policy_harness() -> str:
    """`_healthy_harness` with the list answering without `VersionPolicies`.

    The list object still answers 200, and the `$expand` the probe asked for
    is simply not in the payload, which is what a tenant without the surface
    returns through a request that did not fail.
    """
    answered = _healthy_harness()
    unreported = answered.replace(_VERSION_POLICY_ANSWER, "", 1)
    assert unreported != answered, "the version-policy answer was not removed"
    return unreported


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_list_that_reports_no_trim_mode_is_not_read_as_untrimmed() -> None:
    """An absent `DefaultTrimMode` is not a trim mode of none.

    `version_trim_mode` is a requirement at WARN, and reading the absence as
    a PASS told the operator that service-managed auto-trim does not override
    the declared MajorVersionLimit, which nothing had checked.
    """
    schema, bundle = _simple()
    required = {r.key: r for r in derive_requirements(schema, bundle, "default")}
    assert required["version_trim_mode"].level_on_fail == "WARN"

    summary = _run_assess(
        _declared_descriptions(), harness=_unreported_version_policy_harness(),
    )
    assert [
        f["level"] for f in summary["findings"] if f["key"] == "version_trim_mode"
    ] == ["NOT-ASSESSABLE"], summary["findings"]
    assert summary["verdict"] == "DEGRADED", summary["findings"]
    assert not [
        f for f in summary["findings"] if f["level"] in {"WARN", "BLOCKED"}
    ], summary["findings"]

    answered = _run_assess(_declared_descriptions(), harness=_healthy_harness())
    assert [
        f["level"] for f in answered["findings"] if f["key"] == "version_trim_mode"
    ] == ["PASS"], answered["findings"]


def _reporting_variants_harness() -> str:
    """`_ASSESS_HARNESS` is made to answer the surfaces that carry a value.

    The thin mock replies `{d: {results: []}}` to everything it does not name,
    which reaches only one side of each of these checks. Nothing else in this
    suite makes them answer, and emitted JS has no reachability gate, so an
    unfired branch here is invisible.
    """
    variants = _ASSESS_HARNESS.replace(
        "const body = (url) => {\n",
        "const body = (url) => {\n"
        "  if (url.includes('GetAvailableTagsForSite')) { return { d: {} }; }\n"
        "  if (url.includes('site/usage')) {\n"
        "    return { d: { Storage: 262144000, StoragePercentageUsed: 0.25 } };\n"
        "  }\n"
        "  if (url.includes('SP_TenantSettings_Current')) {\n"
        "    return { d: { CorporateCatalogUrl: '' } };\n"
        "  }\n",
        1,
    )
    assert variants != _ASSESS_HARNESS, "the reporting branches were not spliced in"
    return variants


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_reporting_branches_the_thin_mock_cannot_reach_all_fire() -> None:
    """Each of these branches separates "not reported" from "reported as none".

    That distinction is what the change introducing them was for, and the
    default harness reaches only the side that was already there.
    """
    summary = _run_assess(
        _declared_descriptions(), harness=_reporting_variants_harness(),
    )
    detail = {f["key"]: f["detail"] for f in summary["findings"]}
    assert detail["retention_labels"] == "Retention labels not reported by this site."
    assert detail["storage"] == "Storage used 250 MB (25% of quota)."
    assert detail["app_catalog"] == "No tenant app catalog configured."


#: Findings whose detail may still interpolate a value the thin mock does not
#: supply. A ratchet: entries come out, and one going in needs a reason in the
#: pull request.
_MAY_REPORT_UNDEFINED: frozenset[str] = frozenset()


def _bare_list_object_harness() -> str:
    """`_ASSESS_HARNESS` answering an existing list with its `Title` alone.

    The default mock hands the collision probe a `BaseTemplate` and a
    `Description`, so the gate below ran over the one payload whose properties
    are all present and could not see the collision finding interpolate one
    that was not.
    """
    bare = _ASSESS_HARNESS.replace(
        "Title: title, BaseTemplate: 100, Description: LIST_DESCRIPTIONS.get(title),",
        "Title: title,",
    )
    assert bare != _ASSESS_HARNESS, "the list payload was not stripped"
    assert "BaseTemplate" not in bare, "the mock still answers with one"
    return bare


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_no_finding_reports_the_literal_word_undefined() -> None:
    """The mock answers 200 with no selected properties on purpose.

    That is the shape a real tenant produces when it does not carry one.
    Findings printed `undefined` at operator level on every green run of this
    suite before the guard existed, and nothing asserted on them. One survived
    the first pass of this gate, because the only payload the gate ran over was
    the one the mock fills in completely.
    """
    for label, harness in (
        ("the default mock", _ASSESS_HARNESS),
        ("a list object carrying only its Title", _bare_list_object_harness()),
    ):
        summary = _run_assess(_declared_descriptions(), harness=harness)
        # Without this the run could reach no collision finding at all and
        # still report nothing leaking.
        assert [
            f["key"] for f in summary["findings"] if f["key"].startswith("collision:")
        ] == [f"collision:{title}" for title in _declared_descriptions()], (
            label, summary["findings"],
        )
        leaking = [
            f["key"] for f in summary["findings"]
            if "undefined" in f["detail"] and f["key"] not in _MAY_REPORT_UNDEFINED
        ]
        assert leaking == [], (label, leaking)


# A site answering 200 with a null payload for every call, which is what
# `probeGet` turns into `{ok: true, d: null}`. Nothing about the declared
# lists is set up, because the first probe throws long before they are read.
_NULL_BODY_HARNESS = textwrap.dedent(r"""
    globalThis.window = { location: { origin: 'https://example.sharepoint.com' } };
    globalThis._spPageContextInfo = {
      webServerRelativeUrl: '/sites/test',
      userLoginName: 'probe@example.com',
      userId: 1,
    };
    // Unused here, and present because _run_assess rewrites this exact line.
    const LIST_DESCRIPTIONS = new Map([]);
    globalThis.fetch = async () => ({
      ok: true, status: 200,
      headers: { get: () => null },
      json: async () => ({ d: null }),
      text: async () => '{"d":null}',
    });
""")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_null_payload_still_reaches_a_verdict() -> None:
    """A run that reaches no verdict tells the operator nothing.

    An operator who gets none cannot tell a healthy site from an unreadable
    one, and the standalone script has nothing that catches a throw. A null
    body is the cheapest payload that produces one.
    """
    summary = _run_assess(_declared_descriptions(), harness=_NULL_BODY_HARNESS)
    assert summary["verdict"] in {"COMPATIBLE", "DEGRADED", "BLOCKED"}, summary
    # From `probeGet` refusing the payload, not from the `try` catching a
    # throw. The `try` is the second guard and would satisfy the line above
    # on its own, which would leave the first one untested.
    assert summary.get("aborted") is None, summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_throw_inside_the_standalone_assessment_still_names_a_verdict() -> None:
    """The second guard is exercised here on its own.

    `probeGet` cannot refuse every throw the body can raise, and this script
    had nothing around `assessSite` at all: an operator got a stack trace and
    no verdict, which reads exactly like a script that never ran. The deploy
    gate has carried this guard since it was written.
    """
    js = _assess_js().replace('"base_templates"', '"base_templates_typo"', 1)
    assert '"base_templates_typo"' in js, "the targets key was not renamed"
    summary = _run_assess(_declared_descriptions(), js=js)
    assert summary["verdict"] == "BLOCKED", summary
    assert summary["aborted"] == "assessment-failed", summary


# Synthetic verbose-OData error body for contextinfo parser diagnostics (#282).
_ACCESS_DENIED = {
    "error": {
        "code": "-2147024891, System.UnauthorizedAccessException",
        "message": {
            "lang": "en-US",
            "value": "Access denied. You do not have permission to perform this action.",
        },
    },
}


def _refused_contextinfo_harness() -> str:
    """`_ASSESS_HARNESS` answering contextinfo 403, with every call logged.

    That one request changes and nothing else does, so a finding this
    produces comes from the refusal rather than from a site the mock stopped
    serving. The log is what proves the assessment stayed read-only through
    it: contextinfo is the only POST the script is allowed to make.
    """
    assert "const respond = (status, payload)" in _ASSESS_HARNESS, (
        "the harness no longer exposes the respond() this wrapper reuses"
    )
    wrapper = textwrap.dedent("""
        const calls = [];
        const siteFetch = globalThis.fetch;
        globalThis.fetch = async (url, opts = {}) => {
          calls.push({ url: String(url), method: (opts && opts.method) || 'GET' });
          if (!String(url).includes('contextinfo')) return siteFetch(url, opts);
          return respond(403, __DENIED__);
        };
        globalThis.__calls = calls;
    """).replace("__DENIED__", json.dumps(_ACCESS_DENIED))
    return _ASSESS_HARNESS + wrapper


def _run_assess_refused(harness: str) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    """Run the emitted assess.js and hand back its summary, calls and transcript.

    `_run_assess` asserts its way to a summary, which is the wrong shape for a
    test that has to prove the script did NOT throw and did NOT write.
    """
    js = _assess_js()
    assert js.count("})();") == 1, "the IIFE terminator is no longer unique"
    script = harness + "\n" + js.replace(
        "})();",
        "}))().then("
        "(r) => console.log('__RESULT__' + JSON.stringify(r)),"
        " (e) => console.log('__THROWN__' + JSON.stringify(String((e && e.message) || e))))"
        ".then(() => console.log('__CALLS__' + JSON.stringify(globalThis.__calls)))",
    ).replace("(async () => {", "((async () => {", 1)
    output = run_node(script)

    def _marker(name: str) -> Any:
        line = next((ln for ln in output.splitlines() if ln.startswith(name)), None)
        return None if line is None else json.loads(line.removeprefix(name))

    thrown = _marker("__THROWN__")
    assert thrown is None, f"assess.js rejected instead of reporting: {thrown}"
    summary = _marker("__RESULT__")
    assert summary is not None, f"assess.js returned no summary:\n{output[-3000:]}"
    calls = _marker("__CALLS__")
    assert calls is not None, f"the harness produced no call log:\n{output[-3000:]}"
    return summary, calls, output


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_refused_contextinfo_is_named_rather_than_reported_as_a_type_error() -> None:
    """The standalone assessment made its own contextinfo POST and read
    `j.d.GetContextWebInformation` off it without checking the response, so a
    403 reached the operator as `Cannot read properties of undefined` under a
    finding that says the build version could not be read. That is #282
    surviving the fix to the shared digest helper, on the one script an
    operator runs FIRST.
    """
    summary, calls, output = _run_assess_refused(_refused_contextinfo_harness())
    assert "GetContextWebInformation" not in output, (
        f"the refusal still surfaces as a property-access error:\n{output[-3000:]}"
    )
    # A refused digest degrades the assessment without preventing other reads.
    assert summary["verdict"] in {"COMPATIBLE", "DEGRADED", "BLOCKED"}, summary
    assert summary.get("aborted") is None, summary
    named = [f for f in summary["findings"] if "contextinfo" in str(f["detail"])]
    assert named, f"no finding names the refused request: {summary['findings']}"
    assert any(f["key"] == "platform_build" for f in named), named
    for finding in named:
        assert "403" in str(finding["detail"]), finding
        assert "Access denied" in str(finding["detail"]), finding
    # Contextinfo remains the only POST after the refusal.
    writes = [c for c in calls if c["method"] == "POST" and "contextinfo" not in c["url"]]
    assert not writes, f"the read-only assessment wrote: {writes}"


def _refused_enumeration_harness() -> str:
    """`_ASSESS_HARNESS` refusing the list-title enumeration, calls logged.

    The enumeration is the happy path that lets a first deploy read absence
    from a 200 rather than painting getbytitle 404s. Refusing it forces the
    collision probe onto its per-title fallback, which is where the "absent
    list degrades to WARN" regression lived.
    """
    wrapper = textwrap.dedent("""
        const calls = [];
        const siteFetch = globalThis.fetch;
        globalThis.fetch = async (url, opts = {}) => {
          calls.push({ url: String(url), method: (opts && opts.method) || 'GET' });
          // web/lists (the enumeration) ends with /lists; getbytitle does not.
          if (String(url).split('?')[0].endsWith('/lists')) {
            return respond(403, __DENIED__);
          }
          return siteFetch(url, opts);
        };
        globalThis.__calls = calls;
    """).replace("__DENIED__", json.dumps(_ACCESS_DENIED))
    return _ASSESS_HARNESS + wrapper


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_refused_enumeration_still_reads_a_404_as_absence() -> None:
    """A refused title enumeration must not turn absent lists into warnings.

    With the enumeration unavailable the collision probe falls back to
    per-title getbytitle, and an absent list's 404 is the only signal. It must
    still read "clean provision target" (PASS) -- reading it as a probe
    failure degrades every first deploy whose tenant refuses the enumeration.
    """
    summary, _calls, _output = _run_assess_refused(_refused_enumeration_harness())
    collisions = {
        f["key"]: f["level"]
        for f in summary["findings"]
        if f["key"].startswith("collision:")
    }
    for title in _declared_descriptions():
        assert collisions.get(f"collision:{title}") == "PASS", (
            f"refused enumeration turned absent '{title}' into "
            f"{collisions.get(f'collision:{title}')!r} instead of PASS"
        )


if __name__ == "__main__":  # pragma: no cover
    # Regenerate the golden. Deliberately not a pytest flag: see
    # test_simple_assess_js_matches_golden. Uses the SAME renderer the test
    # does, so the two cannot drift.
    _target = EXPECTED / "simple-assess.js"
    write_golden(_target, _assess_js())
    print(f"wrote {_target}")  # noqa: T201


# --- The site's time zone is what every `today` evaluates in ----------------
#
# The site's regional time zone is the one every date and time is stored
# and shown in, and the one a `today` view window is read against. A site
# left in a zone other than its users' shifts every time they see. Nothing
# read that zone before this. (The validation clock is separate: measured
# 2026-09-02, TODAY() and NOW() ran 16 to 20 hours behind an AUS Eastern
# site whatever the setting, so date rules compare with the save instant;
# see analysis/save_rules.py.)


def _today_pack() -> tuple[Schema, MappingBundle]:
    schema = make_schema(
        make_table("Project", column("Title", required=True), column("DueDate", "date")),
    )
    bundle = make_bundle(
        entities=["Project"],
        column_validation={
            "Project": EntitySection(columns={
                "DueDate": ColumnValidation(
                    when=Leaf(field="DueDate", op="leq", value="today"),
                    message="Not in the future.",
                ),
            }),
        },
    )
    return schema, bundle


def test_assess_targets_report_whether_the_pack_uses_today() -> None:
    schema, bundle = _today_pack()
    assert assess_targets(schema, bundle, "default")["uses_today"] is True
    plain = make_bundle(entities=["Project"])
    assert assess_targets(schema, plain, "default")["uses_today"] is False
    # A `[today]` default is a use as well: it is filled in the site's zone.
    dated = make_schema(
        make_table(
            "Project", column("Title", required=True),
            column("Raised", "date", default="[today]"),
        ),
    )
    assert assess_targets(dated, plain, "default")["uses_today"] is True


def test_a_pack_that_uses_today_requires_the_site_time_zone() -> None:
    schema, bundle = _today_pack()
    levels = {r.key: r.level_on_fail for r in derive_requirements(schema, bundle, "default")}
    assert levels["time_zone"] == "WARN"
    plain = make_bundle(entities=["Project"])
    assert "time_zone" not in {r.key for r in derive_requirements(schema, plain, "default")}


# The site runs in AUS Eastern (Bias -600, daylight bias -60) and the
# "browser" sits wherever the test says.
_ZONE_HARNESS = _ASSESS_HARNESS + textwrap.dedent(r"""
    Date.prototype.getTimezoneOffset = () => -(BROWSER_OFFSET_MIN);
    const _siteFetch = globalThis.fetch;
    globalThis.fetch = async (url) => {
      if (String(url).toLowerCase().includes('regionalsettings/timezone')) {
        const zone = { Id: 76, Information: { Bias: -600, StandardBias: 0, DaylightBias: -60 } };
        zone['Description'] = '(UTC+10:00) Canberra, Melbourne, Sydney';
        return respond(200, { d: zone });
      }
      return _siteFetch(url);
    };
""")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_time_zone_finding_warns_when_the_browser_is_ahead_of_the_site() -> None:
    schema, bundle = _today_pack()
    js = generate_assess_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default", source_dbml="simple.dbml",
        generated_at="2026-05-04T00:00:00Z",
    )

    def zone_finding(browser_offset_min: int) -> dict[str, Any]:
        harness = _ZONE_HARNESS.replace("BROWSER_OFFSET_MIN", str(browser_offset_min))
        summary = _run_assess("", harness=harness, js=js)
        return next(f for f in summary["findings"] if f["key"] == "time_zone")

    same = zone_finding(600)
    assert same["level"] == "INFO", same
    assert "Canberra" in same["detail"]
    # Daylight time is the same site, so it is not a mismatch.
    assert zone_finding(660)["level"] == "INFO"
    apart = zone_finding(0)
    assert apart["level"] == "WARN", apart
    assert "site's zone" in apart["detail"]
    assert "Regional settings" in apart["detail"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_pack_without_today_only_reports_the_site_time_zone() -> None:
    schema = make_schema(make_table("Project", column("Title", required=True)))
    bundle = make_bundle(entities=["Project"])
    js = generate_assess_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default", source_dbml="simple.dbml",
        generated_at="2026-05-04T00:00:00Z",
    )
    harness = _ZONE_HARNESS.replace("BROWSER_OFFSET_MIN", "0")
    finding = next(
        f for f in _run_assess("", harness=harness, js=js)["findings"]
        if f["key"] == "time_zone"
    )
    assert finding["level"] == "INFO"
    assert "Canberra" in finding["detail"]


def test_a_renamed_entity_is_a_blocking_requirement_with_its_previous_titles() -> None:
    """The assessment predicts the rename decision the deploy will make: it
    needs the previous titles and their markers, and a wrong answer must
    block the verdict rather than warn."""
    from dbml_sharepoint.analysis.list_description import family_for
    from dbml_sharepoint.model.mapping_types import EntityMapping

    schema = make_schema(
        make_table("Risk", "Title", note="Risks."),
        make_table("Action", "Title", note="Actions."),
    )
    bundle = make_bundle(entities={
        "Risk": EntityMapping(
            name="Risk", kind="List", base_template=100, site_role="default",
            renamed_from=("ProgramRisk",),
        ),
        "Action": EntityMapping(
            name="Action", kind="List", base_template=100, site_role="default",
        ),
    })
    family = family_for(schema)
    targets = assess_targets(schema, bundle, "default")
    assert targets["list_renames"] == [
        ["APP_Risk", [["APP_ProgramRisk", marker_for(family, "ProgramRisk")]]],
    ]
    reqs = {r.key: r for r in derive_requirements(schema, bundle, "default")}
    assert reqs["rename:APP_Risk"].level_on_fail == "BLOCKED"
    assert "rename:APP_Action" not in reqs


def test_group_and_level_renames_are_blocking_requirements_with_their_previous_names(
    tmp_path: Path,
) -> None:
    from _packs import write_mapping

    from dbml_sharepoint.analysis.group_description import marker_for_group
    from dbml_sharepoint.analysis.list_description import family_for
    from dbml_sharepoint.analysis.role_definition_description import marker_for_level
    from dbml_sharepoint.model.mapping_loader import load_mapping

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
          - name: "{prefix} Request Handlers"
            description: "Handlers."
    """)
    bundle = load_mapping(tmp_path / "m.yaml")
    schema = make_schema(make_table("Risk", "Title", note="Risks."))
    family = family_for(schema)
    targets = assess_targets(schema, bundle, "default")
    level = marker_for_level(family, "ADOPT Submit Only")
    group = marker_for_group("ADOPT Request Handlers", family)
    assert targets["level_renames"] == [["GOV Submit Only", [["ADOPT Submit Only", level]]]]
    assert targets["group_renames"] == [
        ["GOV Request Handlers", [["ADOPT Request Handlers", group]]],
    ]
    reqs = {r.key: r for r in derive_requirements(schema, bundle, "default")}
    assert reqs["rename_level:GOV Submit Only"].level_on_fail == "BLOCKED"
    assert reqs["rename_group:GOV Request Handlers"].level_on_fail == "BLOCKED"
