# test/test_demogen.py
"""demo-data.js generation (--seed): plan typing and script contract."""

from pathlib import Path

from dbml_sharepoint.demogen import generate_demo_js
from dbml_sharepoint.mapping_loader import MappingBundle, load_mapping
from dbml_sharepoint.parser import Schema, parse_dbml
from dbml_sharepoint.release import load_release

FIXTURES = Path(__file__).parent / "fixtures"


def _demo_inputs(tmp_path: Path) -> tuple[Schema, MappingBundle]:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Enum status {\n"
        '  "Open"\n'
        '  "Closed"\n'
        "}\n"
        "Table Risk {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Status status\n"
        "  Owner person\n"
        "  ReviewDate date\n"
        "}\n"
        "Table Issue {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  RelatedRisk int [ref: > Risk.Id]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "  Issue: { kind: List, base_template: 100, site_role: default }\n"
        "demo_items:\n"
        "  Risk:\n"
        "    - key: r1\n"
        "      values:\n"
        '        Title: "[DEMO] Sample risk"\n'
        '        Status: "Open"\n'
        '        Owner: "@me"\n'
        '        ReviewDate: "today-40"\n'
        "  Issue:\n"
        "    - key: i1\n"
        "      values:\n"
        '        Title: "[DEMO] Sample issue"\n'
        "        RelatedRisk: { demo_ref: r1 }\n",
        encoding="utf-8",
    )
    return parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")


def _generate(tmp_path: Path) -> str:
    schema, bundle = _demo_inputs(tmp_path)
    return generate_demo_js(
        schema=schema,
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        generated_at="2026-05-04T00:00:00Z",
    )


def test_demo_plan_types_fields_at_generation(tmp_path: Path) -> None:
    """The script must not guess column semantics at run time: person
    columns become kind 'me' (written as <Name>Id from the operator),
    lookups kind 'ref' (resolved from created demo Ids), today±N on date
    columns kind 'date_offset' (resolved on demo day), all else literal."""
    js = _generate(tmp_path)
    assert '"kind": "me"' in js
    assert '"kind": "ref"' in js
    assert '"value": "r1"' in js
    assert '"kind": "date_offset"' in js
    assert '"value": -40' in js
    assert '"kind": "literal"' in js
    # Creation order follows list dependency order: Risk before Issue.
    assert js.index('"APP_Risk"') < js.index('"APP_Issue"')


def test_demo_script_contract(tmp_path: Path) -> None:
    js = _generate(tmp_path)
    # Site guard + operator identity, like every pasteable script.
    assert "_spPageContextInfo" in js
    assert "Site mismatch" in js
    # Idempotence by Title; person via the operator; lookups via <Name>Id.
    assert "findByTitle" in js
    assert "_spPageContextInfo.userId" in js
    assert "body[`${f.name}Id`]" in js
    # The teardown contract and in-record notice ride the Title marker.
    assert "[DEMO] " in js
    # Per-row list-item comments were tried and WITHDRAWN: the modern
    # Comments() endpoint is undocumented surface and 400'd the write live
    # (2026-07-24) while adding nothing the visible marker doesn't show.
    assert "/Comments()" not in js
    # All REST traffic rides the shared _http transport partial.
    assert "async function fetchWithRetry(" in js
    assert "const spHeaders = (digest, extra = {})" in js
    assert "await fetch(apiUrl" not in js
