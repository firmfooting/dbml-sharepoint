# test/test_jsgen.py
"""The deploy generator's frame, and the inputs the rest of the family shares.

`generate_deploy_js` is tested across `test_jsgen_*.py`, one module per
concern: `_fields` for what a column becomes, `_views` for views, `_lists`
for the list and library objects, `_security` for levels, groups and ACLs,
`_phases` for the emitted run and its guards, `_formatting` for the display
and validation surfaces, and `_golden` for the byte comparison. Grep the
whole family for a test name; the split was a pure move (#172).

What is left here is what has no better home: the two standard inputs every
module builds on, and the tests about the script's frame rather than any one
phase of it -- the provenance line, the API addressing, the escaping and the
abort that runs before anything else does.
"""

from pathlib import Path
from typing import Any, override

from _builders import ID_PK, TITLE, table
from _packs import blocks, entities, pack
from _paths import FIXTURES, SOLUTION_TEMPLATES

from dbml_sharepoint.analysis.joins import (
    all_items_hidden,
    all_items_joining_fields,
    join_bearing_columns,
    joining_fields,
)
from dbml_sharepoint.analysis.phases import phase_number as pn
from dbml_sharepoint.analysis.rendered_columns import (
    SYSTEM_COLUMNS,
    rendered_columns,
    system_columns_for,
)
from dbml_sharepoint.analysis.resolve import resolve
from dbml_sharepoint.extension import BaseExtension
from dbml_sharepoint.generators.jsgen import build_schema_json, generate_deploy_js
from dbml_sharepoint.model.env_file import ENV_SETTINGS, EnvProvenance, EnvValue
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml
from dbml_sharepoint.model.release import load_release

_FIXED_ARGS: dict[str, Any] = dict(
    site_url="https://example.sharepoint.com/sites/test",
    site_role="default",
    source_dbml="simple.dbml",
    source_mtime="2026-05-04T00:00:00Z",
    generated_at="2026-05-04T00:00:00Z",
)


def _generate_simple_js() -> str:
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    return generate_deploy_js(
        schema=schema,
        bundle=bundle,
        release=release,
        **_FIXED_ARGS,
        resolved=resolve(schema, bundle.mapping),
    )


def test_generated_deploy_js_contains_lifecycle_markers() -> None:
    js = _generate_simple_js()

    assert "[SP-DEPLOY]" in js
    assert f"Phase {pn('lists')}" in js
    assert f"Phase {pn('lookups')}" in js
    assert f"Phase {pn('indexes')}" in js
    assert "0.1.0-test" in js  # release tag rendered


def test_deploy_js_says_so_when_no_env_file_was_read() -> None:
    """The default `env_provenance` must produce an explicit log() line, not
    silence a later regression could not tell apart from a feature that
    never ran. It is a plain log() call, not a header comment: the operator
    pastes back the console transcript, not the file."""
    js = _generate_simple_js()
    assert "log('INFO', \"No dbml-sharepoint.env file was read.\");" in js


def test_deploy_js_logs_the_env_file_path_digest_and_keys_used() -> None:
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    provenance = EnvProvenance(
        path="dbml-sharepoint.env",
        digest="abc123def456",
        values=(
            EnvValue(setting=ENV_SETTINGS[0], value="svc@example.org", used=True, override=None),
        ),
    )
    js = generate_deploy_js(
        schema=schema, bundle=bundle, release=release, env_provenance=provenance,
        resolved=resolve(schema, bundle.mapping), **_FIXED_ARGS,
    )
    log_line = next(line for line in js.splitlines() if line.strip().startswith("log('INFO',"))
    assert "dbml-sharepoint.env" in log_line
    assert "abc123def456" in log_line
    assert "DBMLSP_ENTERPRISE_READER" in log_line
    # The static line is baked at build time -- it must not read as a live
    # observation of the tenant.
    assert "svc@example.org" not in log_line


class _CrossSiteExpansion(BaseExtension):
    """The Choice + URL pair a cross-site reference really becomes."""

    @override
    def expand_column(
        self, table: Any, column: Any, bundle: Any,
    ) -> list[dict[str, Any]] | None:
        return [
            {
                "title": f"{column.name}Abbreviation",
                "body": {
                    "__metadata": {"type": "SP.FieldChoice"},
                    "Title": f"{column.name}Abbreviation",
                    "FieldTypeKind": 6,
                    "Choices": {"results": ["A"]},
                    "Required": False,
                },
            },
            {
                "title": f"{column.name}SiteUrl",
                "body": {
                    "__metadata": {"type": "SP.FieldUrl"},
                    "Title": f"{column.name}SiteUrl",
                    "FieldTypeKind": 11,
                    "Required": False,
                },
            },
        ]


def test_generated_js_uses_web_prefixed_api_urls() -> None:
    """Regression: every SP REST endpoint must be prefixed with the
    current web's server-relative URL, not a bare '/_api/...'.

    SP routes '/_api/...' against the path BEFORE '_api'. A bare
    '/_api/web/lists' targets the tenant ROOT web, not the sub-site or
    site-collection web the operator is on. The template must construct
    URLs as `${WEB}/_api/...` (where WEB is derived from
    `_spPageContextInfo.webServerRelativeUrl`).
    """
    js = _generate_simple_js()

    # Must declare WEB and an apiUrl helper.
    assert "const WEB = actualPath" in js
    assert "const apiUrl = (suffix) =>" in js
    assert "${WEB}/_api/${suffix}" in js

    # Must NOT contain any bare '/_api/' literal in fetch calls.
    # Strip comment lines (// ... or  * ...) since explanatory comments
    # describing the bug are allowed to mention the wrong form. Match
    # only string literals, which start with ' or `.
    code_lines = [
        line for line in js.splitlines()
        if not line.lstrip().startswith(("//", "*", "/*"))
    ]
    lines_with_bare_api = [
        line for line in code_lines
        if ("'/_api/" in line or "`/_api/" in line) and "apiUrl" not in line
    ]
    assert lines_with_bare_api == [], (
        "Found bare '/_api/' URL literals in code (which target the root "
        "web on sub-sites). Use apiUrl(suffix) instead. Offending lines:\n"
        + "\n".join(lines_with_bare_api)
    )


def test_tojson_escapes_injection_chars(tmp_path: Path) -> None:
    """A5: schema-controlled strings (a field description) are emitted through
    tojson htmlsafe escaping, so <, >, & and </script> are unicode-escaped and
    cannot break out of the generated JS. Locks the invariant against a future
    refactor reintroducing a raw interpolation."""
    schema, bundle = pack(
        tmp_path,
        dbml=table(
            "Widget", ID_PK, TITLE,
            "Field1 nvarchar [note: 'Bad </script><tag> and & value']",
        ),
        mapping=entities("Widget"),
    )
    release = load_release(FIXTURES / "release.yaml")
    js = generate_deploy_js(
        schema=schema, bundle=bundle, release=release,
        site_url="https://example.sharepoint.com/sites/t", site_role="default",
        source_dbml="s.dbml", source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z", resolved=resolve(schema, bundle.mapping),
    )
    assert "</script>" not in js  # literal breakout sequence absent
    assert "\\u003c/script\\u003e" in js  # tojson htmlsafe escaped it
    assert "\\u0026" in js  # & escaped


def test_generated_js_aborts_when_sp_page_context_missing() -> None:
    """The deploy script depends on _spPageContextInfo for both the
    site-mismatch preflight and the WEB url prefix. If it's absent we
    must abort cleanly rather than silently routing API calls to the
    tenant root."""
    js = _generate_simple_js()
    assert "typeof _spPageContextInfo === 'undefined'" in js
    assert "no-sp-page-context" in js


def _schema_json_for(solution_id: str) -> dict[str, Any]:
    """Build SCHEMA for a shipped family named by its solution id."""
    root = SOLUTION_TEMPLATES / solution_id
    schema = parse_dbml(root / "10-design" / "schema.dbml")
    bundle = load_mapping(root / "20-configure" / "mapping.yaml")
    return build_schema_json(schema, bundle, "default", resolved=resolve(schema, bundle.mapping))


def _generate_views_js(tmp_path: Path) -> str:
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            """
            Enum status {
              "Open"
              "Closed"
            }
            """,
            table("Risk", ID_PK, TITLE, "Status status", "DueDate date"),
        ),
        mapping=blocks(entities("Risk"), """
            views:
              Risk:
                - title: Open risks
                  default: true
                  fields: [Title, Status, DueDate]
                  where:
                    - { field: Status, op: neq, value: Closed }
                  sort:
                    - { field: DueDate, direction: asc }
        """),
    )
    return generate_deploy_js(
        schema=schema,
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z", resolved=resolve(schema, bundle.mapping),
    )


def test_debug_flag_default_off(tmp_path: Path) -> None:
    """Timing diagnostics ship in every bundle behind `const DEBUG = false`
    (operators flip it in the pasted script; no rebuild). Phase timings and
    the request counter record always; printing is DEBUG-only."""
    js = _generate_views_js(tmp_path)
    assert "const DEBUG = false;" in js
    assert "const dbg = " in js
    assert "requestCount += 1" in js
    assert "markPhase(" in js
    assert "console.table" in js
    assert "elapsedSeconds" in js


def test_the_validator_and_the_generator_agree_on_what_all_items_renders(
    tmp_path: Path,
) -> None:
    """The guard on the shared-module claim in this plan's Architecture section.

    If this test is deleted or weakened, the validator and the generator CAN
    drift about which fields `All Items` renders, and the drift shows up as a
    build that passes a view the deploy then creates over the ceiling, or one
    refused that was never going to exist. Nothing else in the suite catches it.

    The fixture carries every shape that could pull the two apart:

    - `Assignee`, a real `ref` resolved in PHASE 1 (Person precedes Task in
      creation order, so nothing defers it).
    - `Parent`, a self-ref on Task. `ordering.py` always defers a self-ref,
      so this one is a genuine phase-2 Lookup on Task's OWN list.
    - `Manager`, a self-ref on Person (a phase-2 Lookup belonging to a
      DIFFERENT list), so `jsgen.py`'s `lookup["list"] == list_title` filter
      has to actually discriminate rather than pass every phase-2 entry
      through unfiltered.
    - `Elsewhere`, a CROSS-SITE ref, which exists only as
      <col>Abbreviation / <col>SiteUrl and never under its own name.
    - `Owner`, a `person` column, also named in `hide_from_all_items`, so
      the hidden-set subtraction does real work on both sides, and is not
      just exercised by the generator's own tests above.
    - `Notes`, a plain `nvarchar`.
    - The auto-increment `Id`, which `analysis.rendered_columns.rendered_columns`
      drops while SharePoint supplies `ID`.

    TWO assertions, not one, because a single hand-recomputed expectation
    re-types the validator's arithmetic instead of calling it, the exact
    anti-pattern `analysis/joins.py`'s own docstring warns about for the
    survey test. The first assertion pins the FIELD LIST jsgen renders
    against an expression written by hand in this test; deleting a term
    from `all_items_joining_fields`'s own composition in `joins.py` would
    NOT turn it red, because it does not call that function. The second
    assertion does call it (`all_items_joining_fields`, the validator's
    actual shared derivation), so THAT one goes red if `| SYSTEM_COLUMNS`,
    `| {"Title"}`, or the `hide_from_all_items` subtraction is ever dropped
    from `joins.py`. Dropping each term by hand, one at a time, left the
    first assertion green and turned only the second red, confirming the
    two assertions catch different failures, not the same one twice.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            table("Person", ID_PK, TITLE, "Manager int [ref: > Person.Id]"),
            table(
                "Task", ID_PK, TITLE,
                "Owner person",
                "Assignee int [ref: > Person.Id]",
                "Elsewhere int [ref: > Person.Id]",
                "Parent int [ref: > Task.Id]",
                "Notes nvarchar",
            ),
            # A library: both sides carry a kind term, and only a library in
            # the fixture turns a dropped kind term on either side red.
            table("Docs", ID_PK, TITLE, "Reviewer person", "Summary nvarchar"),
        ),
        mapping="""
            entities:
              Person: { kind: List, base_template: 100, site_role: default }
              Task:
                kind: List
                base_template: 100
                site_role: default
                hide_from_all_items: [Owner]
              Docs:
                kind: DocumentLibrary
                base_template: 101
                site_role: default
                hide_from_all_items: [Reviewer]
            cross_site_reference_columns:
              - { entity: Task, column: Elsewhere }
        """,
    )
    # A cross-site column needs an extension that expands it, or
    # build_schema_json raises (jsgen.py:411-415). _CrossSiteExpansion is
    # already defined earlier in this module.
    schema_json = build_schema_json(
        schema, bundle, "default", extension=_CrossSiteExpansion(),
        resolved=resolve(schema, bundle.mapping),
    )
    generated = next(
        v for v in schema_json["views"]
        if v["title"] == "All Items" and v["list"] == "APP_Task"
    )["view_fields"]

    # Not `table` / `entity`: those names are the input builders imported at
    # the top of this module, and shadowing them here is an UnboundLocalError
    # in the `dbml=` argument above.
    task = next(t for t in schema.tables if t.name == "Task")
    task_entity = bundle.mapping.entities["Task"]
    xcols = {"Elsewhere"}

    derived = (
        rendered_columns(task, xcols) | {"Title"} | SYSTEM_COLUMNS
    ) - all_items_hidden(task_entity)
    assert set(generated) == derived

    # Calls the validator's REAL function rather than re-typing its formula.
    # This is what actually goes red if `joins.py`'s composition drifts from
    # what jsgen renders. See the docstring above.
    assert (
        joining_fields(generated, join_bearing_columns(task, xcols))
        == all_items_joining_fields(task, task_entity, xcols)
    )

    # The same two assertions for the library, whose All Items leads with
    # FileLeafRef: the kind term on each side is what this pair pins.
    generated_docs = next(
        v for v in schema_json["views"]
        if v["title"] == "All Items" and v["list"] == "APP_Docs"
    )["view_fields"]
    docs = next(t for t in schema.tables if t.name == "Docs")
    docs_entity = bundle.mapping.entities["Docs"]
    assert set(generated_docs) == (
        rendered_columns(docs, set()) | {"Title", "DocIcon"} | system_columns_for("DocumentLibrary")
    ) - all_items_hidden(docs_entity)
    assert "FileLeafRef" in generated_docs and "FileLeafRef" not in generated
    assert (
        joining_fields(generated_docs, join_bearing_columns(docs, set()))
        == all_items_joining_fields(docs, docs_entity, set())
    )
