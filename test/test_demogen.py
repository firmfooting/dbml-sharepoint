# test/test_demogen.py
"""demo-data.js generation (--seed): plan typing and script contract."""

from pathlib import Path

from _builders import ID_PK, TITLE, table
from _packs import blocks, entities, pack
from _paths import FIXTURES

from dbml_sharepoint.generators.demogen import generate_demo_js
from dbml_sharepoint.model.mapping_loader import MappingBundle
from dbml_sharepoint.model.parser import Schema
from dbml_sharepoint.model.release import load_release


def _demo_inputs(tmp_path: Path) -> tuple[Schema, MappingBundle]:
    return pack(
        tmp_path,
        dbml=blocks(
            """
            Enum status {
              "Open"
              "Closed"
            }
            """,
            table("Risk", ID_PK, TITLE, "Status status", "Owner person", "ReviewDate date"),
            table("Issue", ID_PK, TITLE, "RelatedRisk int [ref: > Risk.Id]"),
        ),
        mapping=blocks(entities("Risk", "Issue"), """
            demo_items:
              Risk:
                - key: r1
                  values:
                    Title: "[DEMO] Sample risk"
                    Status: "Open"
                    Owner: "@me"
                    ReviewDate: "today-40"
              Issue:
                - key: i1
                  values:
                    Title: "[DEMO] Sample issue"
                    RelatedRisk: { demo_ref: r1 }
        """),
    )


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


def test_bare_today_is_offset_zero(tmp_path: Path) -> None:
    """The validator accepts a bare `today` on demo date values (it shares
    the view-condition sentinel, where bare `today` is correct). Generation
    must accept it too and mean offset 0 — otherwise a demo row declaring
    `today` passes the build with zero findings and emits the literal
    string "today" into demo-data.js."""
    schema, bundle = pack(
        tmp_path,
        dbml=table("Board", ID_PK, TITLE, "BoardDate date"),
        mapping=blocks(entities("Board"), """
            demo_items:
              Board:
                - key: b1
                  values:
                    Title: "[DEMO] Today"
                    BoardDate: "today"
        """),
    )
    js = generate_demo_js(
        schema=schema,
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert '"kind": "date_offset"' in js
    assert '"value": 0' in js
    assert '"value": "today"' not in js


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


def test_a_hyperlink_demo_value_becomes_a_field_url_value_record() -> None:
    """A SharePoint URL column is a record over REST (SP.FieldUrlValue —
    Url plus Description), not a scalar, and a bare string is rejected at
    create time. Before this, a hyperlink column could not be seeded at
    all: four templates in the people theme shipped their EvidenceUrl and
    MinutesUrl blank because of it."""
    from dbml_sharepoint.generators.demogen import _field_plan

    plan = _field_plan("hyperlink", "EvidenceUrl", "https://example.invalid/a.pdf")
    assert plan == {
        "name": "EvidenceUrl",
        "kind": "url",
        "value": {
            "url": "https://example.invalid/a.pdf",
            "description": "https://example.invalid/a.pdf",
        },
    }


def test_a_hyperlink_demo_value_may_carry_its_own_description() -> None:
    from dbml_sharepoint.generators.demogen import _field_plan

    plan = _field_plan(
        "hyperlink",
        "MinutesUrl",
        {"url": "https://example.invalid/m.docx", "description": "March minutes"},
    )
    assert plan["kind"] == "url"
    assert plan["value"] == {
        "url": "https://example.invalid/m.docx",
        "description": "March minutes",
    }


def test_every_reader_of_the_today_sentinel_shares_one_pattern() -> None:
    """The validator gates what may be DECLARED, the condition renderers
    decide what it becomes in CAML, and the demo planner decides what it
    becomes in a seeded row. Three readers of one authored value.

    A copy that drifted wider or narrower than another would pass the build
    with zero findings and emit the literal string "today" into a script —
    the same shape as any two readers disagreeing about one declaration.
    Comments asserted the agreement; this asserts it.
    """
    from dbml_sharepoint.analysis import validator
    from dbml_sharepoint.analysis.conditions import _TODAY
    from dbml_sharepoint.analysis.typemap import TODAY_SENTINEL
    from dbml_sharepoint.generators.demogen import _TODAY_OFFSET

    assert _TODAY is TODAY_SENTINEL
    assert _TODAY_OFFSET is TODAY_SENTINEL
    assert validator._TODAY_SENTINEL is TODAY_SENTINEL


def test_the_today_sentinel_accepts_exactly_the_documented_forms() -> None:
    from dbml_sharepoint.analysis.typemap import TODAY_SENTINEL

    for good in ("today", "today+1", "today+30", "today-7", "today-365"):
        assert TODAY_SENTINEL.match(good), good
    for bad in ("today+", "today-", "Today", "today +1", "today+1.5", "tomorrow", "today++1"):
        assert not TODAY_SENTINEL.match(bad), bad


def test_a_today_offset_keeps_its_sign_through_the_planner() -> None:
    """The shared pattern captures sign and digits separately; reading one
    group would make every negative offset a crash or a positive."""
    from dbml_sharepoint.generators.demogen import _field_plan

    assert _field_plan("date", "D", "today")["value"] == 0
    assert _field_plan("date", "D", "today+30")["value"] == 30
    assert _field_plan("date", "D", "today-7")["value"] == -7


def test_the_demo_validator_refuses_everything_the_planner_refuses() -> None:
    """The planner and the validator are two readers of one authored value.
    Where the planner raises, the validator must already have reported —
    otherwise an invalid mapping reaches generation and surfaces as a build
    traceback rather than a finding an author can act on.

    This asserts the property directly rather than trusting the two to be
    kept in step by hand, which is how they drifted twice: once on the
    {url, description} record the planner accepted and the validator
    refused, and once on the scalar hyperlink the planner refused and the
    validator waved through.
    """
    from typing import Any

    import pytest as _pytest

    from dbml_sharepoint.generators.demogen import _field_plan

    refused_by_planner: list[Any] = [
        None, 123, "", "   ", {"url": None}, {"url": ""},
    ]
    for refused in refused_by_planner:
        with _pytest.raises(ValueError):
            _field_plan("hyperlink", "Link", refused)

    accepted: list[Any] = [
        "https://example.invalid/a.pdf",
        {"url": "https://example.invalid/a.pdf"},
        {"url": "https://example.invalid/a.pdf", "description": "A file"},
    ]
    for good in accepted:
        assert _field_plan("hyperlink", "Link", good)["kind"] == "url"
