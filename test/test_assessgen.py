# test/test_assessgen.py
import json
import re
import textwrap
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from _batch_mock import BATCH_MOCK
from _model import as_library, column
from _model import bundle as make_bundle
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


def test_library_folders_are_assessed_and_required() -> None:
    """A file standing where a folder is declared stops the folder phase, so
    the assessment carries the declared folders and a BLOCKED requirement
    for each library that declares any."""
    from dbml_sharepoint.generators.assessgen import assess_targets

    schema, bundle = _simple()
    bundle = as_library(bundle, "Task", ("Clinical services", "Corporate"))
    targets = assess_targets(schema, bundle, "default")
    assert targets["library_folders"] == [["APP_Task", ["Clinical services", "Corporate"]]]
    assert 101 in targets["base_templates"]
    keys = {r.key for r in derive_requirements(schema, bundle, "default")}
    assert "folder_shape:APP_Task" in keys
    assert "folder_shape:APP_Project" not in keys
    plain = assess_targets(*_simple(), "default")
    assert plain["library_folders"] == []


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
    """The no-write property, read off the emitted text.

    The script POSTs to `$batch` as well now, because an OData batch is a POST
    whatever its parts hold, so the POST audit on its own would also pass a
    script that batched WRITES. What rules that out is which transport partial
    assess includes: `_http_batch_read.js.j2` and not `_http_batch.js.j2`, so
    BatchWriter, `spHeaders` and the ChangeSet encoding are absent and the one
    request line this script can spell opens with GET.
    """
    js = _assess_js()
    assert "'X-HTTP-Method'" not in js and '"X-HTTP-Method"' not in js
    posts = re.findall(r"method:\s*'POST'", js)
    for m in re.finditer(r"method:\s*'POST'", js):
        window = js[max(0, m.start() - 400): m.start() + 400]
        assert any(
            tok in window for tok in ("contextinfo", "ProcessQuery", "$batch")
        ), window
    assert posts, "expected at least the contextinfo POST"
    # Spelled with the paren where one exists, so the assertion is about a
    # definition or a call rather than about the word appearing in a comment
    # that explains why the write half is absent.
    for absent in ("class BatchWriter", "spHeaders(", "${op.method}", "boundary=${inner}"):
        assert absent not in js, (
            f"the read-only assessment gained {absent!r}, which only the write "
            f"half of the batch transport carries. It must include "
            f"_http_batch_read.js.j2, never _http_batch.js.j2."
        )
    assert js.count("`GET ${op.url} HTTP/1.1\\r\\n`") == 1, (
        "the batch transport no longer spells every part GET, so the envelope "
        "this script sends is no longer auditable as read-only"
    )


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
    // What each declared list REPORTS as its ItemCount. A live site always
    // answers a selected property, so this is answered for every list that
    // exists; a title absent from the map reports an empty list. Rewritten by
    // _run_assess. A Map for the same reason the one above is.
    const LIST_ITEM_COUNTS = new Map([]);
    const itemCountOf = (t) => (LIST_ITEM_COUNTS.has(t) ? LIST_ITEM_COUNTS.get(t) : 0);
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
          ItemCount: itemCountOf(title),
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
    item_counts: Mapping[str, int] | None = None,
    wrap: str = "",
) -> dict[str, Any]:
    """Execute the emitted assess.js against a site holding `list_description`.

    One string applies to every declared list; a mapping sets them per title.
    `harness` swaps the mocked site for a variant, such as a locked one, and
    `js` for a script generated from another pack. `item_counts` sets what a
    list reports as its size, per title, where the default empty list is what
    the size checks read as comfortably under the threshold. `wrap` is spliced
    in OUTSIDE the batch mock, which is the only place a test can damage a
    `$batch` answer the mock has already assembled. Returns the summary the
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
    if item_counts is not None:
        counted = mocked.replace(
            "const LIST_ITEM_COUNTS = new Map([]);",
            f"const LIST_ITEM_COUNTS = new Map({json.dumps(list(item_counts.items()))});",
        )
        assert counted != mocked, "the item counts were not spliced in"
        mocked = counted
    # Outermost, so the site mock underneath answers each unpacked part as
    # the single GET it stands for. Without it every batched read is one
    # opaque POST the harness cannot answer and the whole tier degrades.
    script = mocked + BATCH_MOCK + wrap + "\n" + js.replace(
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


def _library_pack() -> tuple[Any, Any]:
    """The simple fixture with Task declared as a library holding one folder."""
    schema, bundle = _simple()
    return schema, as_library(bundle, "Task", ("Clinical services",))


def _library_assess_js() -> str:
    from dbml_sharepoint.generators.assessgen import generate_assess_js
    from dbml_sharepoint.model.release import load_release

    schema, bundle = _library_pack()
    return generate_assess_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default", source_dbml="simple.dbml",
        generated_at="2026-05-04T00:00:00Z",
    )


def _library_markers() -> dict[str, str]:
    """Every declared list present and carrying its marker, from the same
    speller the assessment reads."""
    from dbml_sharepoint.generators.assessgen import assess_targets

    schema, bundle = _library_pack()
    return dict(assess_targets(schema, bundle, "default")["list_markers"])


def _folder_harness(object_type: int | None, *, unreadable: bool = False) -> str:
    """`_ASSESS_HARNESS` answering the folder shape read with one row of
    `object_type` (1 a folder, 0 a file), no row, or a refusal, and Task
    as a library."""
    rows = (
        "[]" if object_type is None
        else f"[{{ Id: 7, FileSystemObjectType: {object_type}, "
        "FileLeafRef: 'Clinical services' }]"
    )
    body_head = "const body = (url) => {\n"
    shape_read = (
        f"{body_head}  if (url.includes('FileSystemObjectType')) {{\n"
        f"    return {{ d: {{ results: {rows} }} }};\n"
        "  }\n"
    )
    template_line = "Title: title, BaseTemplate: 100,"
    library_template = "Title: title, BaseTemplate: title === 'APP_Task' ? 101 : 100,"
    splices = [(body_head, shape_read), (template_line, library_template)]
    if unreadable:
        # The harness is dedented, so the dispatcher's lines sit two spaces in.
        answer_line = "  return respond(200, body(u));\n"
        refused_read = (
            f"  if (u.includes('FileSystemObjectType')) return respond(500, {{}});\n{answer_line}"
        )
        splices.append((answer_line, refused_read))
    harness = _ASSESS_HARNESS
    for old, new in splices:
        spliced = harness.replace(old, new, 1)
        assert spliced != harness, f"not spliced into the harness: {old[:40]!r}"
        harness = spliced
    return harness


def _folder_finding(summary: dict[str, Any]) -> dict[str, Any]:
    return next(f for f in summary["findings"] if f["key"] == "folder_shape:APP_Task")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_assess_blocks_a_file_where_a_folder_is_declared() -> None:
    """MEASURED 2026-09-03, `library.folder.filesystem-object-type`: a folder's
    item reads FileSystemObjectType 1, a file's 0. A file of a declared
    folder's name would stop the folder phase, so it blocks the verdict."""
    summary = _run_assess(_library_markers(), harness=_folder_harness(0), js=_library_assess_js())
    finding = _folder_finding(summary)
    assert finding["level"] == "BLOCKED" and "Clinical services" in finding["detail"]
    assert summary["verdict"] == "BLOCKED"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("object_type", [1, None])
def test_assess_passes_a_declared_folder_that_is_a_folder_or_absent(
    object_type: int | None,
) -> None:
    summary = _run_assess(
        _library_markers(), harness=_folder_harness(object_type), js=_library_assess_js(),
    )
    assert _folder_finding(summary)["level"] == "PASS"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_assess_passes_declared_folders_of_a_library_not_yet_created() -> None:
    present = {title: marker for title, marker in _library_markers().items() if title != "APP_Task"}
    summary = _run_assess(present, harness=_folder_harness(0), js=_library_assess_js())
    finding = _folder_finding(summary)
    assert finding["level"] == "PASS" and "will be created" in finding["detail"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_library_whose_folders_cannot_be_read_is_not_assessable() -> None:
    """NOT-ASSESSABLE, not WARN, and not a shape reported from no answer.

    The question is whether a file stands where a folder is declared. A read
    that did not answer did not answer it, and these reads now travel as one
    $batch, so a refusal covers every declared folder of the library at once.
    Both levels degrade the verdict; only this one says which way.
    """
    summary = _run_assess(
        _library_markers(), harness=_folder_harness(None, unreadable=True),
        js=_library_assess_js(),
    )
    finding = _folder_finding(summary)
    assert finding["level"] == "NOT-ASSESSABLE", finding
    assert "Could not read" in finding["detail"], finding
    assert summary["verdict"] in {"DEGRADED", "BLOCKED"}, summary["verdict"]


# === A batched read that did not answer =====================================
#
# Tier 2 reads every declared list and every declared folder through one
# `$batch` request each. The outer request answers HTTP 200 even when
# individual parts fail (measured 2026-09-04: 1000 operations came back 200
# with 363 of them failed inside the body), so the three refusals BatchReader
# makes are the only thing standing between a refused read and a finding
# recorded as settled. Each of these damages the answer a different way and
# asserts the same thing: nothing is reported, and the verdict degrades.

#: What each sabotage does to the `$batch` answer the batch mock assembled.
#: The mock spells every part status `HTTP/1.1 <n> Mocked` and separates parts
#: with `--batchresponse_1`, which is what these rewrite.
_BATCH_SABOTAGE = {
    # One part answers 404 while the envelope still says 200.
    "a part answers non-2xx": """
        const text = (await r.text()).replace('HTTP/1.1 200 Mocked', 'HTTP/1.1 404 Mocked');
        return { ...r, text: async () => text };
    """,
    # One part is dropped, so the answers can no longer be paired with the
    # paths that asked for them.
    "the part count does not match": """
        const parts = (await r.text()).split('--batchresponse_1');
        const text = [parts[0], ...parts.slice(2)].join('--batchresponse_1');
        return { ...r, text: async () => text };
    """,
    # The request itself is refused, so there is no envelope at all.
    "the request is refused outright": """
        return {
          ok: false, status: 500, url: String(url),
          headers: { get: () => null },
          json: async () => ({}),
          text: async () => '{"error":{"message":{"value":"Batch refused"}}}',
        };
    """,
}


def _sabotaged_batch(how: str) -> str:
    """A wrapper that damages every `$batch` answer the way `how` says.

    Installed outside the batch mock, so the mock still unpacks and answers
    the envelope and only its ANSWER is damaged. Non-batch requests pass
    through untouched, which is what keeps the rest of the assessment a
    control rather than a second variable.
    """
    return """
{
  const _batched = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    const r = await _batched(url, opts);
    if (!/\\/_api\\/\\$batch$/.test(String(url))) return r;
    __SABOTAGE__
  };
}
""".replace("__SABOTAGE__", _BATCH_SABOTAGE[how])


def _levels(summary: dict[str, Any]) -> dict[str, str]:
    """Finding level by key. The last wins, as the operator's console shows."""
    return {f["key"]: f["level"] for f in summary["findings"]}


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("how", sorted(_BATCH_SABOTAGE))
def test_a_batched_read_that_did_not_answer_settles_nothing(how: str) -> None:
    """The site is healthy, so every one of these keys would otherwise pass.

    `test_a_healthy_site_is_compatible` is the control: the same harness with
    the batch answers intact reaches COMPATIBLE. Damage the answer and the
    three findings that one read feeds must all read NOT-ASSESSABLE, because
    a list that did not answer is neither present, nor absent, nor of a known
    size. Recording any of them from this read is the failure these guards
    exist to prevent, and the verdict must degrade rather than pass.
    """
    summary = _run_assess(
        _declared_descriptions(), harness=_healthy_harness(), wrap=_sabotaged_batch(how),
    )
    levels = _levels(summary)
    for title in _declared_descriptions():
        for key in (f"collision:{title}", f"provenance_marker:{title}", f"item_count:{title}"):
            assert levels.get(key) == "NOT-ASSESSABLE", (
                f"{how}: '{key}' was recorded as {levels.get(key)!r} from a read "
                f"that did not answer"
            )
    assert summary["verdict"] == "DEGRADED", (
        f"{how}: the verdict is {summary['verdict']!r}. A site whose declared "
        f"lists could not be read is not a site reported compatible."
    )


#: contextinfo refused, spliced in outside the batch mock so the outer $batch
#: request BatchReader would send is the one thing that cannot go out.
_REFUSE_DIGEST = """
{
  const _under = globalThis.fetch;
  globalThis.fetch = async (url, opts) => {
    if (!String(url).includes('contextinfo')) return _under(url, opts);
    return {
      ok: false, status: 403, url: String(url),
      headers: { get: () => null },
      json: async () => ({}),
      text: async () => '{"error":{"message":{"value":"Access denied."}}}',
    };
  };
}
"""


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_refused_digest_reads_one_at_a_time_rather_than_reporting_nothing() -> None:
    """The one transport failure that says nothing about the paths.

    BatchReader's outer request needs X-RequestDigest even though every part
    is a read (measured 2026-09-04: without it the identical envelope came
    back HTTP 403), so a site that refuses contextinfo cannot be batched at
    all. That is a fact about the site rather than about its lists, and
    reporting every declared list unassessable over it would turn one refused
    POST into a whole degraded assessment. The reads fall back to one at a
    time, and every finding they feed still stands.
    """
    summary = _run_assess(
        _declared_descriptions(), harness=_healthy_harness(), wrap=_REFUSE_DIGEST,
    )
    levels = _levels(summary)
    for title in _declared_descriptions():
        assert levels.get(f"collision:{title}") == "INFO", (
            f"'{title}' was not read after the digest was refused: "
            f"{levels.get(f'collision:{title}')!r}"
        )
        assert levels.get(f"provenance_marker:{title}") == "PASS", (
            f"'{title}' carries its marker, and the read that would prove it "
            f"was never made: {levels.get(f'provenance_marker:{title}')!r}"
        )
    refused = [f for f in summary["findings"] if "batched read refused" in str(f["detail"])]
    assert not refused, f"a $batch went out without a usable digest: {refused}"


def _fields_harness(
    fields: list[dict[str, Any]], *, next_link: str | None = None,
) -> str:
    """`_ASSESS_HARNESS` answering every field enumeration with `fields`.

    The default harness answers `/fields` with an empty result set, which the
    display-title check reads as "not provisioned yet" and skips. That is the
    right default and it is also why a variant is needed to make the check
    fire at all.

    Each row is PROJECTED to what `$select` names, the way a live site answers.
    Handing back every property regardless made a check that reads one the
    script never selected pass here and read `undefined` on a real tenant,
    which is the silence a mock is supposed to expose rather than cover.

    `next_link` puts a `d.__next` beside the rows, which is a server paging
    below the asked-for `$top` rather than the `$top` itself truncating.
    """
    # Two-space indent: _ASSESS_HARNESS is dedented, so the source's own
    # indentation is not what this has to match at runtime.
    paged = (
        "" if next_link is None
        else f"    answer.__next = {json.dumps(next_link)};\n"
    )
    branch = (
        "  if (path.endsWith('/fields')) {\n"
        f"    const rows = {json.dumps(fields)};\n"
        "    const selected = ((u.split('$select=')[1] || '').split('&')[0] || '')\n"
        "      .split(',').filter(Boolean);\n"
        "    const projected = selected.length === 0 ? rows : rows.map((row) =>\n"
        "      Object.fromEntries(Object.entries(row)\n"
        "        .filter(([name]) => selected.includes(name))));\n"
        "    const answer = { results: projected };\n"
        + paged
        + "    return respond(200, { d: answer });\n"
        "  }\n"
    )
    marker = "  if (path.toLowerCase().endsWith('/regionalsettings/timezone')) {"
    assert _ASSESS_HARNESS.count(marker) == 1
    return _ASSESS_HARNESS.replace(marker, branch + marker, 1)


#: The page size the column enumeration asks for. A page that came back
#: holding this many rows may have ended before the list did, and `$top` is
#: client-driven paging, which returns no next link to say so.
_COLUMN_PAGE_SIZE = 500


def _filler_columns(count: int) -> list[dict[str, Any]]:
    """`count` columns no pack declares, for filling a page to its size."""
    return [
        {"InternalName": f"Filler{n}", "Title": f"Filler{n}",
         "EnforceUniqueValues": False}
        for n in range(count)
    ]


def test_the_column_page_size_this_suite_fills_is_the_one_the_script_asks_for(
) -> None:
    """Filling a page proves nothing if the script asks for a different one.

    A suite building a 500-row page against a script reading 1,000 would run
    green over a read that was never truncated, so the number is pinned to
    the emitted text rather than written twice.
    """
    js = _unique_assess_js()
    assert f"const COLUMN_PAGE_SIZE = {_COLUMN_PAGE_SIZE};" in js
    assert "$top=${COLUMN_PAGE_SIZE}" in js


_DISPLAY_KEY = "display_titles:"


def _display_findings(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [f for f in summary["findings"] if f["key"].startswith(_DISPLAY_KEY)]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_assess_reports_a_column_renamed_on_the_site() -> None:
    """Between deploys nothing else can see this either.

    Renaming a column needs Manage Lists, which Full Control, Design and Edit
    all carry, and the next deploy silently puts the declared name back. So a
    rename lives and dies with nobody told, and the column it matters most for
    is the built-in Title, which the maintenance sidecar's `isCustom` filter
    excludes for reading FromBaseType:true.
    """
    declared = _declared_descriptions()
    summary = _run_assess(
        declared,
        harness=_fields_harness([
            {"InternalName": "DueDate", "Title": "Renamed By Hand"},
            {"InternalName": "SortOrder", "Title": "Sort Order"},
        ]),
    )
    drifted = _display_findings(summary)
    assert drifted, f"a renamed column drew no finding: {summary['findings']}"
    detail = " ".join(f["detail"] for f in drifted)
    assert "DueDate" in detail and "Renamed By Hand" in detail and '"Due Date"' in detail
    # Named with BOTH values: a finding saying only that something differs
    # sends the reader back to the site to find out what.
    assert "SortOrder" not in detail, (
        "a column matching its declaration was reported as drifted: " + detail
    )
    # INFO, not WARN: the deploy repairs this, so it is a report and not a
    # gate, and a warning that always resolves itself stops meaning anything.
    assert all(f["level"] == "INFO" for f in drifted), drifted
    assert summary["verdict"] != "BLOCKED"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_assess_is_quiet_when_every_display_title_matches() -> None:
    """A check that always fires is noise, and noise gets ignored."""
    declared = _declared_descriptions()
    summary = _run_assess(
        declared,
        harness=_fields_harness([
            {"InternalName": "DueDate", "Title": "Due Date"},
            {"InternalName": "SortOrder", "Title": "Sort Order"},
        ]),
    )
    assert _display_findings(summary) == []


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_column_the_site_does_not_have_yet_is_not_reported_as_drifted() -> None:
    """A first deploy has provisioned none of them, and painting the console
    red over every declared column would bury the findings that matter."""
    summary = _run_assess(_declared_descriptions())  # the default: no fields
    assert _display_findings(summary) == []


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_full_column_page_names_the_display_titles_it_could_not_compare(
) -> None:
    """A column missing from a page that came back full was not compared.

    Reading it as "not provisioned yet" makes the check silent about a column
    that may be renamed on the site, which is the one thing it exists to
    report. The page holds APP_Task's declared column and not APP_Project's,
    so the two arms are separated by the same run.
    """
    summary = _run_assess(
        _declared_descriptions(),
        harness=_fields_harness([
            {"InternalName": "DueDate", "Title": "Due Date"},
            *_filler_columns(_COLUMN_PAGE_SIZE - 1),
        ]),
    )
    unseen = _display_findings(summary)
    assert [f["key"] for f in unseen] == ["display_titles:APP_Project"], (
        summary["findings"]
    )
    assert unseen[0]["level"] == "INFO", unseen
    detail = unseen[0]["detail"]
    assert "SortOrder" in detail and f"{_COLUMN_PAGE_SIZE}-row" in detail, detail
    # Not DueDate: it was in the page and it matched, so naming it would send
    # the operator to check a column this run actually compared.
    assert "DueDate" not in detail, detail


# --- Declared unique, against what the site actually carries ----------------
#
# #550 made a declared `unique` actually deploy its constraint, so a list
# provisioned before that fix holds the column unconstrained and the next
# field phase asks SharePoint for the constraint over data that never carried
# it. deploy.js says so in its preflight, which runs before any write but
# prints into a console the run then carries past; assess is read before the
# paste, which is the only point the operator can still act on it.

_UNIQUE_KEY = "pending_unique:"


def _unique_pack() -> tuple[Schema, MappingBundle]:
    """A one-list pack declaring one ordinary column unique."""
    return (
        make_schema(make_table(
            "Asset",
            column("Title", required=True),
            column("Reference", required=True, unique=True),
            column("Owner", "person"),
            note="Assets, each carrying one unique reference.",
        )),
        make_bundle(entities=["Asset"]),
    )


def _unique_title_pack() -> tuple[Schema, MappingBundle]:
    """A one-list pack declaring the BUILT-IN Title unique.

    Title never reaches the field-body builder (it is `list.title_patch`), and
    that divergence is exactly how a `[unique]` Title once deployed with no
    constraint at all (#307). A pack that only ever declares an ordinary
    column unique would not cover it.
    """
    return (
        make_schema(make_table(
            "Asset",
            column("Title", required=True, unique=True),
            note="Assets, each titled once.",
        )),
        make_bundle(entities=["Asset"]),
    )


def _identity_pack() -> tuple[Schema, MappingBundle]:
    """A pack whose auto-increment identity column declares `[unique]`.

    The deploy skips it on NAME, arity and increment alone, without consulting
    the type mapper, so a column SharePoint provides for itself and the deploy
    never creates would otherwise be reported as a constraint about to be
    asked for. Spelled here as `nvarchar` because `int` resolves to a kind the
    mapper already reports as never unique, which would make the case vacuous.
    """
    schema = make_schema(make_table("Asset", column("Title", required=True)))
    identity = schema.tables[0].columns[0]
    identity.type = "nvarchar"
    identity.unique = True
    return schema, make_bundle(entities=["Asset"])


def _deployed_unique_columns(
    pack: tuple[Schema, MappingBundle],
) -> dict[str, set[str]]:
    """List title -> the columns the DEPLOY sends EnforceUniqueValues for.

    Read out of `build_schema_json`, for the same reason
    `_declared_descriptions` is: building the expectation from assess's own
    payload would make it agree with whatever assess happens to believe.
    """
    schema, bundle = pack
    schema_json = build_schema_json(schema, bundle, "default")
    deployed: dict[str, set[str]] = {}
    for entry in schema_json["lists"]:
        names = {
            f["title"] for f in entry["fields_phase1"]
            if f["body"].get("EnforceUniqueValues") is True
        }
        if (entry["title_patch"] or {}).get("EnforceUniqueValues") is True:
            names.add("Title")
        if names:
            deployed[entry["title"]] = names
    for deferred in schema_json["phase2_lookups"]:
        if deferred["field"]["body"].get("EnforceUniqueValues") is True:
            deployed.setdefault(deferred["list"], set()).add(deferred["field"]["title"])
    return deployed


def test_assess_targets_name_the_columns_the_deploy_declares_unique() -> None:
    """Pinned against the deploy, never against assess's own belief.

    A second spelling of "declared unique" would let assess stay quiet about
    the one constraint the field phase is about to ask for, which is the
    silence this check exists to end. Sets rather than sequences: the deploy
    splits the built-in Title out into its own patch, so the two orders cannot
    be compared, and declaration order is asserted separately below.
    """
    for pack in (
        _simple(), _library_pack(), _unique_pack(), _unique_title_pack(),
        _identity_pack(),
    ):
        targets = assess_targets(pack[0], pack[1], "default")
        named = {title: set(columns) for title, columns in targets["list_unique_columns"]}
        assert named == _deployed_unique_columns(pack), targets["list_unique_columns"]


def test_declared_unique_columns_are_named_in_declaration_order() -> None:
    """The operator reads them beside the mapping, so they run in its order."""
    schema = make_schema(make_table(
        "Asset",
        column("Title", required=True, unique=True),
        column("Reference", required=True, unique=True),
        column("Serial", required=True),
        column("Tag", required=True, unique=True),
        note="Assets.",
    ))
    targets = assess_targets(schema, make_bundle(entities=["Asset"]), "default")
    assert targets["list_unique_columns"] == [
        ["APP_Asset", ["Title", "Reference", "Tag"]],
    ]


def test_a_pending_unique_requirement_warns_and_never_blocks() -> None:
    """What SharePoint does with this transition over existing duplicates is
    not established, so refusing a deploy on it would be a rule stronger than
    anything measured."""
    reqs = {
        r.key: r for r in derive_requirements(*_unique_pack(), "default")
    }
    assert reqs["pending_unique:APP_Asset"].level_on_fail == "WARN"
    assert "Reference" in reqs["pending_unique:APP_Asset"].description
    # And absent entirely for a pack that declares no unique column, rather
    # than a requirement every family carries and nothing ever files.
    plain = {r.key for r in derive_requirements(*_simple(), "default")}
    assert not [key for key in plain if key.startswith(_UNIQUE_KEY)]


def _unique_assess_js(pack: tuple[Schema, MappingBundle] | None = None) -> str:
    schema, bundle = pack if pack is not None else _unique_pack()
    return generate_assess_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default", source_dbml="unique.dbml",
        generated_at="2026-05-04T00:00:00Z",
    )


def _unique_findings(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """The pending-unique check's own findings, selected by key.

    By key and never by the word "unique" in a detail string: several other
    findings mention it, and they have nothing to do with this check.
    """
    return [f for f in summary["findings"] if f["key"].startswith(_UNIQUE_KEY)]


def _fields_refused_harness() -> str:
    """`_ASSESS_HARNESS` refusing every column enumeration.

    One non-2xx part refuses the whole envelope, which is what makes this the
    read that did not answer.
    """
    branch = (
        "  if (path.endsWith('/fields')) {\n"
        "    return respond(500, { error: { message: { value: 'Field read refused' } } });\n"
        "  }\n"
    )
    marker = "  if (path.toLowerCase().endsWith('/regionalsettings/timezone')) {"
    assert _ASSESS_HARNESS.count(marker) == 1
    return _ASSESS_HARNESS.replace(marker, branch + marker, 1)


def _run_unique_assess(
    fields: list[dict[str, Any]] | None = None,
    *,
    harness: str | None = None,
    present: bool = True,
    pack: tuple[Schema, MappingBundle] | None = None,
    wrap: str = "",
) -> dict[str, Any]:
    """Run the unique pack's assess script against a site holding `fields`.

    `present=False` leaves the declared list off the site altogether, which is
    a first deploy rather than drift.
    """
    pack = pack if pack is not None else _unique_pack()
    held = _declared_descriptions(pack)
    return _run_assess(
        held if present else {},
        js=_unique_assess_js(pack),
        harness=harness if harness is not None else _fields_harness(fields or []),
        wrap=wrap,
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_assess_warns_about_a_declared_unique_column_the_site_holds_unconstrained(
) -> None:
    """The whole point of saying it here: before the paste.

    deploy's preflight makes the same comparison, but by the time its console
    is read the renames, security, logging and list phases have written.
    """
    rows = [
        {"InternalName": "Title", "Title": "Title", "EnforceUniqueValues": True},
        {"InternalName": "Reference", "Title": "Reference", "EnforceUniqueValues": False},
        {"InternalName": "Owner", "Title": "Owner", "EnforceUniqueValues": False},
    ]
    # Healthy, so the DEGRADED below comes from this WARN and not from the
    # three keys a bare `_ASSESS_HARNESS` leaves unanswered. The control is
    # the test beneath, where the same harness reads COMPATIBLE.
    summary = _run_unique_assess(harness=_healthy_harness(_fields_harness(rows)))
    warned = [f for f in _unique_findings(summary) if f["level"] == "WARN"]
    assert warned, f"an unconstrained unique column drew no warning: {summary['findings']}"
    detail = warned[0]["detail"]
    assert "APP_Asset" in detail and "Reference" in detail
    # Not Owner: it is not declared unique, so the deploy asks nothing of it
    # and naming it would send the operator to check a column nobody touches.
    assert "Owner" not in detail, detail
    # Says what it did NOT do, so its silence is not read as a clean bill, and
    # claims nothing about how SharePoint answers the write.
    assert "did not count duplicate values" in detail, detail
    assert "cannot say whether the request will be accepted" in detail, detail
    assert summary["verdict"] == "DEGRADED", summary["verdict"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_declared_unique_column_already_constrained_is_not_warned_about() -> None:
    """A check that always fires is noise, and noise gets ignored.

    Also the control for the DEGRADED above: the same healthy site, differing
    only in what the one column reads back, comes out COMPATIBLE.
    """
    rows = [
        {"InternalName": "Title", "Title": "Title", "EnforceUniqueValues": True},
        {"InternalName": "Reference", "Title": "Reference", "EnforceUniqueValues": True},
    ]
    summary = _run_unique_assess(harness=_healthy_harness(_fields_harness(rows)))
    assert _levels(summary).get("pending_unique:APP_Asset") == "PASS", summary["findings"]
    assert summary["verdict"] == "COMPATIBLE", summary["findings"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_unique_column_the_site_does_not_have_yet_is_not_pending() -> None:
    """Absent is not unconstrained: the column is not provisioned yet, and the
    deploy creates it carrying the constraint."""
    summary = _run_unique_assess([
        {"InternalName": "Title", "Title": "Title", "EnforceUniqueValues": True},
    ])
    assert _levels(summary).get("pending_unique:APP_Asset") == "PASS", summary["findings"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_list_that_does_not_exist_yet_has_no_pending_constraint() -> None:
    """A first deploy is nothing but absent lists, and painting the console
    red over every one of them buries the findings that matter."""
    summary = _run_unique_assess(present=False)
    finding = _levels(summary).get("pending_unique:APP_Asset")
    assert finding == "PASS", summary["findings"]
    assert summary["verdict"] != "BLOCKED", summary["verdict"]


def _no_enumeration_harness() -> str:
    """`_ASSESS_HARNESS` refusing the list-title enumeration.

    With nothing enumerated the reads go out one at a time and a getbytitle
    404 is the only evidence of absence there is, which is the arm the
    enumeration otherwise hides. A column enumeration of a list that does not
    exist answers 404 here for that reason: the base harness answers every
    `/fields` read 200 with an empty set, which reads as a provisioned list
    holding no declared column and settles the question the wrong way.
    """
    marker = "  if (path.endsWith('/lists')) {"
    assert _ASSESS_HARNESS.count(marker) == 1
    spliced = (
        "  if (path.endsWith('/fields') && !LIST_DESCRIPTIONS.has(listOf(path))) {\n"
        "    return respond(404, { error: { message: { value: 'List not found' } } });\n"
        "  }\n"
        f"{marker}\n"
        "    return respond(500, { error: { message: { value: 'Enumeration refused' } } });\n"
        "  }\n"
    )
    return _ASSESS_HARNESS.replace(marker, spliced + marker, 1)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_404_is_absence_when_the_title_enumeration_was_refused() -> None:
    """Absent is still not unconstrained with nothing enumerated to filter on.

    The enumeration is what normally settles absence, and reporting a first
    deploy's every declared list as unassessable would degrade a verdict over
    lists that simply are not there yet.
    """
    summary = _run_unique_assess(present=False, harness=_no_enumeration_harness())
    assert _levels(summary).get("pending_unique:APP_Asset") == "PASS", summary["findings"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_column_read_that_did_not_answer_reports_no_pending_constraints(
) -> None:
    """Absence of evidence is not evidence: a refused read did not say these
    columns are constrained, so it must not settle the key as a pass."""
    summary = _run_unique_assess(harness=_fields_refused_harness())
    assert _levels(summary).get("pending_unique:APP_Asset") == "NOT-ASSESSABLE", (
        summary["findings"]
    )
    assert summary["verdict"] == "DEGRADED", summary["verdict"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_column_reporting_no_enforce_unique_values_settles_nothing() -> None:
    """A property the site did not report is not a false one.

    `!undefined` is true, so a guard testing only falsity reads a payload that
    never mentioned the property as a column declared unique and unconstrained
    -- a warning manufactured out of a row that answered nothing.
    """
    summary = _run_unique_assess([
        {"InternalName": "Title", "Title": "Title", "EnforceUniqueValues": True},
        {"InternalName": "Reference", "Title": "Reference"},
    ])
    findings = _unique_findings(summary)
    assert [f["level"] for f in findings] == ["NOT-ASSESSABLE"], findings
    assert "Reference" in findings[0]["detail"], findings


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_declared_unique_column_missing_from_a_full_page_is_not_absent(
) -> None:
    """A read that did not see every column established no absence.

    The enumeration asks for one page. A list holding more columns than that
    answers with the page it asked for, and a declared column on a later one
    is missing from the answer exactly as a column that is not provisioned
    yet is. Reading the second meaning passes the check on a list that may
    hold the column unconstrained, which is what the check exists to catch.
    """
    rows = [
        {"InternalName": "Title", "Title": "Title", "EnforceUniqueValues": True},
        *_filler_columns(_COLUMN_PAGE_SIZE - 1),
    ]
    assert len(rows) == _COLUMN_PAGE_SIZE, "the page is not full, so it may not be short"
    assert not [r for r in rows if r["InternalName"] == "Reference"], rows[:2]
    summary = _run_unique_assess(harness=_healthy_harness(_fields_harness(rows)))
    findings = _unique_findings(summary)
    assert [f["level"] for f in findings] == ["NOT-ASSESSABLE"], findings
    detail = findings[0]["detail"]
    assert "Reference" in detail and f"{_COLUMN_PAGE_SIZE}-row" in detail, detail
    assert summary["verdict"] == "DEGRADED", summary["verdict"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_column_page_carrying_a_next_link_is_not_a_whole_list() -> None:
    """The other truncation, where the server pages below the asked-for size.

    Learn's "PageSize, Top and MaxTop" documents both: `$top` returns no next
    link of its own, and a service whose own page size is smaller answers a
    short page WITH one. A short page is what an absent column looks like, so
    the link is the only thing separating them here.
    """
    summary = _run_unique_assess(harness=_healthy_harness(_fields_harness(
        [{"InternalName": "Title", "Title": "Title", "EnforceUniqueValues": True}],
        next_link=(
            "https://example.sharepoint.com/sites/test/_api/web/lists/"
            "getbytitle('APP_Asset')/fields?$skiptoken=Paged"
        ),
    )))
    findings = _unique_findings(summary)
    assert [f["level"] for f in findings] == ["NOT-ASSESSABLE"], findings
    assert "Reference" in findings[0]["detail"], findings
    assert summary["verdict"] == "DEGRADED", summary["verdict"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_full_page_holding_the_declared_column_still_answers_for_it() -> None:
    """The control: the guard withholds an absence, never a reading.

    A page that came back full is unreliable about what is NOT in it and
    exact about what is, so a declared column present in one is compared the
    way it always was. Without this, reporting every full page unassessable
    would satisfy the test above while telling the operator nothing.
    """
    rows = [
        {"InternalName": "Title", "Title": "Title", "EnforceUniqueValues": True},
        {"InternalName": "Reference", "Title": "Reference", "EnforceUniqueValues": False},
        *_filler_columns(_COLUMN_PAGE_SIZE - 2),
    ]
    assert len(rows) == _COLUMN_PAGE_SIZE
    summary = _run_unique_assess(harness=_healthy_harness(_fields_harness(rows)))
    findings = _unique_findings(summary)
    assert [f["level"] for f in findings] == ["WARN"], findings
    assert "Reference" in findings[0]["detail"], findings


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_built_in_title_declared_unique_is_compared_too() -> None:
    """Title is provisioned through its own patch rather than the field-body
    builder, and that divergence is how a `[unique]` Title once deployed with
    no constraint at all (#307)."""
    summary = _run_unique_assess(
        [{"InternalName": "Title", "Title": "Title", "EnforceUniqueValues": False}],
        pack=_unique_title_pack(),
    )
    warned = [f for f in _unique_findings(summary) if f["level"] == "WARN"]
    assert warned, summary["findings"]
    assert "Title" in warned[0]["detail"], warned


def _renamed_and_unique_pack() -> tuple[Schema, MappingBundle]:
    """One list carrying both a display rename and a column declared unique.

    Without both, a test of the shared enumeration is vacuous: the two checks
    would be reading it for different lists and could not collide.
    """
    return (
        make_schema(make_table(
            "Asset",
            column("Title", required=True),
            column("AssetTag", required=True),
            column("Reference", required=True, unique=True),
            note="Assets, tagged and referenced.",
        )),
        make_bundle(entities=["Asset"], display_name_mode="auto"),
    )


#: Fails the read the second time one list's columns are enumerated. Installed
#: outside the batch mock, which redispatches each part through
#: `globalThis.fetch`, so it sees the unpacked GETs rather than the envelope.
_ONE_FIELDS_READ_PER_LIST = r"""
{
  const _under = globalThis.fetch;
  const _seen = new Set();
  globalThis.fetch = async (url, opts) => {
    const u = String(url);
    if (u.includes('/fields?')) {
      const list = (u.match(/getbytitle\('(.*?)'\)/) || [])[1];
      if (_seen.has(list)) throw new Error(`the columns of '${list}' were read twice`);
      _seen.add(list);
    }
    return _under(url, opts);
  };
}
"""


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_one_column_enumeration_serves_both_column_checks() -> None:
    """Display titles and unique constraints read the same enumeration.

    A second request per list would undo the batching that brought tier 2 down
    to one request per loop, and on a large family that is the whole cost.
    """
    pack = _renamed_and_unique_pack()
    targets = assess_targets(pack[0], pack[1], "default")
    assert [title for title, _ in targets["list_display_titles"]] == ["APP_Asset"]
    assert [title for title, _ in targets["list_unique_columns"]] == ["APP_Asset"]
    summary = _run_unique_assess(
        [
            {"InternalName": "AssetTag", "Title": "Renamed By Hand",
             "EnforceUniqueValues": False},
            {"InternalName": "Reference", "Title": "Reference",
             "EnforceUniqueValues": False},
        ],
        pack=pack, wrap=_ONE_FIELDS_READ_PER_LIST,
    )
    levels = _levels(summary)
    assert levels.get("display_titles:APP_Asset") == "INFO", summary["findings"]
    assert levels.get("pending_unique:APP_Asset") == "WARN", summary["findings"]


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
        "2\titem_count:APP_Project\tINFO\t'APP_Project' currently reports 0 item(s), under the "
        "5,000-item list view threshold.\n"
        "2\tcollision:APP_Task\tINFO\t'APP_Task' already exists (BaseTemplate 100); the ownership "
        "check below decides whether deploy may reconcile it.\n"
        "2\tprovenance_marker:APP_Task\tPASS\t'APP_Task' carries its provenance marker.\n"
        "2\titem_count:APP_Task\tINFO\t'APP_Task' currently reports 0 item(s), under the "
        "5,000-item list view threshold.\n"
        "2\tcollision:APP_AppSettings\tINFO\t'APP_AppSettings' already exists (BaseTemplate "
        "100); the ownership check below decides whether deploy may reconcile it.\n"
        "2\tprovenance_marker:APP_AppSettings\tPASS\t'APP_AppSettings' carries its provenance "
        "marker.\n"
        "2\titem_count:APP_AppSettings\tINFO\t'APP_AppSettings' currently reports 0 item(s), "
        "under the 5,000-item list view threshold.\n"
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


# --- How full an existing declared list already is --------------------------
#
# A proximity signal rather than a gate, reported at four bands. WARN and
# DEGRADED at the two upper ones and BLOCKED at neither: `INDEX_CHANGE_CEILING`
# in `analysis/limits.py` carries the two Microsoft sources that disagree about
# whether an index change over the larger band is refused or queued, and what
# would license BLOCKED.
#
# The counts below are fixed literals rather than `LIST_VIEW_THRESHOLD` and
# `INDEX_CHANGE_CEILING` read back. An expectation derived from the constant it
# measures moves with a mutant and can never kill one, which is the rule the
# `limits.py` docstring records for its boundary tests.


def _item_count_findings(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """The size check's own findings, selected by key rather than by detail."""
    return [f for f in summary["findings"] if f["key"].startswith("item_count:")]


def _item_count_absent_harness() -> str:
    """`_ASSESS_HARNESS` answering the list object without an `ItemCount`.

    The list still exists and still answers 200. Only the property the size
    check reads is missing, which a live site does not do for a property it
    was asked for, and which is not the same answer as a list reporting none.
    """
    absent = _ASSESS_HARNESS.replace("ItemCount: itemCountOf(title),", "")
    assert absent != _ASSESS_HARNESS, "the ItemCount was not dropped"
    assert "ItemCount:" not in absent, "the mock still answers with one"
    return absent


def test_the_two_size_ceilings_travel_with_the_pack() -> None:
    """`LIST_VIEW_THRESHOLD` and `INDEX_CHANGE_CEILING`, in the emitted payload.

    The script quotes both numbers to the operator and spells neither, so the
    payload is the one place they could drift from `analysis.limits`.
    """
    targets = assess_targets(*_simple(), "default")
    assert targets["list_view_threshold"] == 5000
    assert targets["index_change_ceiling"] == 20000


def test_every_provisioned_list_has_a_size_requirement_that_only_warns() -> None:
    """A WARN degrades the verdict only where a requirement declares the key.

    The level is pinned as well as the key: a size finding that reached
    BLOCKED would stop a deploy on evidence that does not support stopping it.
    """
    schema, bundle = _simple()
    targets = assess_targets(schema, bundle, "default")
    sizes = {
        r.key: r.level_on_fail
        for r in derive_requirements(schema, bundle, "default")
        if r.key.startswith("item_count:")
    }
    assert sizes == {f"item_count:{title}": "WARN" for title in targets["list_titles"]}


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_absent_declared_list_reports_no_size_at_all() -> None:
    """A list nobody has created yet has no size to report.

    Satisfied by the verdict loop skipping a requirement key with no finding,
    which is why no arm of the size check special-cases absence.
    """
    summary = _run_assess({}, harness=_healthy_harness())
    assert _item_count_findings(summary) == [], summary["findings"]
    assert summary["verdict"] == "COMPATIBLE", [
        f for f in summary["findings"] if f["level"] in {"WARN", "BLOCKED"}
    ]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_list_well_under_the_threshold_is_reported_without_degrading() -> None:
    """The control for the three WARN bands below.

    A DEGRADED there proves nothing unless a list this size comes out
    COMPATIBLE against the same harness.
    """
    summary = _run_assess(
        _declared_descriptions(), harness=_healthy_harness(),
        item_counts={"APP_Project": 120},
    )
    reported = {f["key"]: f for f in _item_count_findings(summary)}
    assert reported["item_count:APP_Project"]["level"] == "INFO"
    assert "120 item(s)" in reported["item_count:APP_Project"]["detail"]
    assert summary["verdict"] == "COMPATIBLE", [
        f for f in summary["findings"] if f["level"] in {"WARN", "BLOCKED"}
    ]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_list_inside_the_proximity_band_warns_and_degrades_the_verdict() -> None:
    """The band exists so an operator hears about it while indexing is cheap.

    Once a list is over the threshold the remedies narrow, so a warning that
    only fired there would arrive after the decision it informs.
    """
    summary = _run_assess(
        _declared_descriptions(), harness=_healthy_harness(),
        item_counts={"APP_Project": 4200},
    )
    finding = next(
        f for f in _item_count_findings(summary) if f["key"] == "item_count:APP_Project"
    )
    assert finding["level"] == "WARN", finding
    assert "4,200 item(s)" in finding["detail"]
    assert "4,000 to 5,000" in finding["detail"]
    assert summary["verdict"] == "DEGRADED"
    # The only WARN on the run, so the DEGRADED can have come from nothing else.
    assert [
        f["key"] for f in summary["findings"] if f["level"] in {"WARN", "BLOCKED"}
    ] == ["item_count:APP_Project"], summary["findings"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_list_at_the_list_view_threshold_warns_and_names_it() -> None:
    """At the threshold, not past it: the documented figure is inclusive.

    The larger band's number stays out of this finding, because an operator
    reading both would have no way to tell which one this list crossed.
    """
    summary = _run_assess(
        _declared_descriptions(), harness=_healthy_harness(),
        item_counts={"APP_Project": 5000},
    )
    finding = next(
        f for f in _item_count_findings(summary) if f["key"] == "item_count:APP_Project"
    )
    assert finding["level"] == "WARN", finding
    assert "5,000-item list view threshold" in finding["detail"]
    assert "20,000" not in finding["detail"], finding
    assert summary["verdict"] == "DEGRADED"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_list_at_the_index_change_ceiling_warns_and_names_both_numbers() -> None:
    """The upper band is about an operation the deploy itself performs.

    WARN and never BLOCKED. Both numbers, because a list this size has
    crossed both and the operator is deciding what to do about each.
    """
    summary = _run_assess(
        _declared_descriptions(), harness=_healthy_harness(),
        item_counts={"APP_Project": 20000},
    )
    finding = next(
        f for f in _item_count_findings(summary) if f["key"] == "item_count:APP_Project"
    )
    assert finding["level"] == "WARN", finding
    assert "20,000 item(s)" in finding["detail"]
    assert "20,000-item mark" in finding["detail"]
    assert "5,000-item list view threshold" in finding["detail"]
    assert summary["verdict"] == "DEGRADED"
    assert not [
        f for f in summary["findings"] if f["level"] == "BLOCKED"
    ], summary["findings"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_list_that_reports_no_item_count_is_not_read_as_a_small_one() -> None:
    """A property the site did not return is not a count of zero.

    Reading it as one would report every declared list as comfortably under
    the threshold on a site that answered nothing about their size.
    """
    summary = _run_assess(
        _declared_descriptions(),
        harness=_healthy_harness(_item_count_absent_harness()),
    )
    levels = {f["key"]: f["level"] for f in _item_count_findings(summary)}
    assert levels == {
        f"item_count:{title}": "NOT-ASSESSABLE" for title in _declared_descriptions()
    }, summary["findings"]
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

    The default mock hands the collision probe a `BaseTemplate`, a
    `Description` and an `ItemCount`, so the gate below ran over the one
    payload whose properties are all present and could not see the collision
    finding interpolate one that was not.
    """
    bare = _ASSESS_HARNESS.replace(
        "Title: title, BaseTemplate: 100, Description: LIST_DESCRIPTIONS.get(title),",
        "Title: title,",
    ).replace("ItemCount: itemCountOf(title),", "")
    assert bare != _ASSESS_HARNESS, "the list payload was not stripped"
    assert "BaseTemplate" not in bare, "the mock still answers with one"
    # The property spelling, not the bare word: the map the stripped line read
    # from is described in a comment further up the harness.
    assert "ItemCount:" not in bare, "the mock still answers with one"
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
    # The batch mock goes UNDER the log, so the log records the $batch POST
    # itself as well as every part redispatched through it. A log that only
    # saw the envelope could not tell a read-only assessment from a writing
    # one, which is the whole point of the test that reads it.
    return _ASSESS_HARNESS + BATCH_MOCK + wrapper


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
    return _ASSESS_HARNESS + BATCH_MOCK + wrapper


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


def _item_count_null_harness() -> str:
    """`_ASSESS_HARNESS` answering the list object with a NULL `ItemCount`.

    A different answer from the absent one above, and the one that reads as a
    small list if the guard tests only for finiteness: `Number(null)` is 0.
    """
    nulled = _ASSESS_HARNESS.replace(
        "ItemCount: itemCountOf(title),", "ItemCount: null,",
    )
    assert nulled != _ASSESS_HARNESS, "the ItemCount was not replaced"
    assert "itemCountOf(title)" not in nulled, "the mock still answers a number"
    return nulled


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_null_item_count_is_not_read_as_an_empty_list() -> None:
    """The key present and the value null is still no answer about size.

    `Number(null)` is 0, so a guard testing only finiteness passes it through
    and reports every declared list as holding nothing, which is an INFO
    saying the site is comfortably under a threshold it never answered about.
    `reported()` at the top of the same file already treats `v == null` as
    unreported, and this is that convention applied to the size check.
    """
    summary = _run_assess(
        _declared_descriptions(),
        harness=_healthy_harness(_item_count_null_harness()),
    )
    levels = {f["key"]: f["level"] for f in _item_count_findings(summary)}
    assert levels == {
        f"item_count:{title}": "NOT-ASSESSABLE" for title in _declared_descriptions()
    }, summary["findings"]
    assert not [
        f for f in _item_count_findings(summary) if f["level"] == "INFO"
    ], summary["findings"]
