# test/test_report_static_sources.py
"""Every query reads SharePoint through ONE `Web.Contents` data source.

The Power BI Service asks for one credential per distinct data source and
refuses to schedule a refresh for one whose URL it cannot resolve statically
(Learn, "Refresh and dynamic data sources"). So each query opens a single
`Web.Contents` whose base is `SiteUrl & "<literal>"` (SiteUrl is a literal
binding or a parameter), every read goes through `Get`, and the rest of each
URL travels in `RelativePath` and `Query`. Nothing in a build or in Desktop
sees a violation, so the shape is pinned over the generated text.
"""

import re
from pathlib import Path

import pytest
from _packs import pack
from _paths import engine_blueprints

from dbml_sharepoint.generators.report_m import (
    generate_dictionary_powerquery,
    generate_powerquery,
)
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml

BLUEPRINTS = engine_blueprints()
_SOURCE = re.compile(r"(?<![\w.])(OData\.Feed|Web\.Contents|SharePoint\.\w+)\(")
_STATIC_URL = re.compile(r'(SiteUrl\s*&\s*)?"(?:[^"]|"")*"')


def _code(query: str) -> str:
    return "\n".join(
        line for line in query.splitlines() if not line.lstrip().startswith("//")
    )


def _first_argument(text: str, start: int) -> str:
    """The text of a call's first argument, from just after its `(`."""
    depth, i = 0, start
    while i < len(text):
        char = text[i]
        if char == '"':
            i += 1
            while text[i] != '"' or text[i + 1 : i + 2] == '"':
                i += 2 if text[i] == '"' else 1
        elif char in "({[":
            depth += 1
        elif char in ")}]":
            if depth == 0:
                return text[start:i]
            depth -= 1
        elif char == "," and depth == 0:
            return text[start:i]
        i += 1
    raise AssertionError("unbalanced call")


def _options_argument(text: str, start: int) -> str:
    """The second argument of a call, from just after its `(`."""
    first = _first_argument(text, start)
    rest = text[start + len(first) + 1 :]
    return _first_argument(rest, 0).strip()


def _web_contents_options(query: str) -> list[str]:
    code = _code(query)
    return [
        _options_argument(code, m.end())
        for m in re.finditer(r"(?<![\w.])Web\.Contents\(", code)
    ]


def _bad_options(query: str) -> list[str]:
    """Options that are not ONE record literal: the service reads a record built
    by `&`, an `if` or a call as a dynamic data source."""
    bad = []
    for options in _web_contents_options(query):
        flat = re.sub(r'"(?:[^"]|"")*"', '""', options)
        depth, closes_early, top = 0, False, ""
        for i, char in enumerate(flat):
            depth += char in "[({"
            depth -= char in "])}"
            if depth == 0 and i < len(flat) - 1:
                closes_early = True
            if depth == 1:
                top += char
        one_record = flat.startswith("[") and flat.endswith("]") and not closes_early
        if not one_record or "&" in top or re.search(r"\bif\b|\w\(", top):
            bad.append(options)
    return bad


def _data_source_urls(query: str) -> list[str]:
    code = _code(query)
    return [
        _first_argument(code, match.end()).strip() for match in _SOURCE.finditer(code)
    ]


def _bad(query: str) -> list[str]:
    return [url for url in _data_source_urls(query) if not _STATIC_URL.fullmatch(url)]


def test_the_checker_rejects_options_that_are_not_one_record_literal() -> None:
    literal = 'Web.Contents(SiteUrl & "/a", [RelativePath = p, Query = q, Headers = [A = "&"]])'
    assert _web_contents_options(literal) == ['[RelativePath = p, Query = q, Headers = [A = "&"]]']
    assert _bad_options(literal) == []
    assert _bad_options('Web.Contents("a", [Query = q] & [RelativePath = p])') != []
    assert _bad_options('Web.Contents("a", [Query = q] & (if p = "" then [] else [A = 1]))') != []
    assert _bad_options("Web.Contents(\"a\", Record.AddField([], \"A\", 1))") != []
    assert _bad_options('Web.Contents("a", opts)') != []


def test_the_checker_separates_static_from_dynamic_urls() -> None:
    """The guard is only worth having if it fires on the shapes that were refused."""
    assert _bad('x = Web.Contents("https://a/_api/web", [A = 1])') == []
    assert _bad('x = Web.Contents(SiteUrl & "/_api/web", [A = 1])') == []
    assert _bad("Web.Contents(url, [A = 1])") != []
    assert _bad("Web.Contents(SiteUrl & path)") != []
    assert _bad('SharePoint.Files(SiteUrl, [ApiVersion = 15])') != []
    assert _bad('// Web.Contents(url)\nWeb.Contents("https://a")') == []
    assert _data_source_urls('Web.Contents("a,(b""c", [])') == ['"a,(b""c"']


_PAIR_DBML = """
Table Risk {
  Id int [pk, increment]
  Title nvarchar [not null]
  Due date
}

Table Action {
  Id int [pk, increment]
  Title nvarchar [not null]
  Status nvarchar
  RelatedRisk int [ref: > Risk.Id]
}
"""

_PAIR_MAPPING = """
entities:
  Risk: {kind: List, base_template: 100, site_role: default}
  Action: {kind: List, base_template: 100, site_role: default}
display_names:
  mode: auto
derived_columns:
  Risk:
    - kind: count
      from: Action
      via: RelatedRisk
      name: OpenActions
      aggregate: count
      type: Int64
  Action:
    - kind: lookup
      from: Risk
      via: RelatedRisk
      pick:
        RiskTitle: Title
      types:
        RiskTitle: text
"""


_TABLES = {"_DataDictionary.pq", "_ModelInfo.pq"}


@pytest.mark.parametrize("site_url", [None, "https://tenant.sharepoint.com/sites/Ops"])
def test_every_data_source_in_a_cross_list_bundle_is_static(
    tmp_path: Path, site_url: str | None,
) -> None:
    schema, bundle = pack(tmp_path, _PAIR_DBML, _PAIR_MAPPING)
    queries = {
        **generate_powerquery(schema, bundle, "default", site_url=site_url),
        **generate_dictionary_powerquery(schema, bundle, "default", site_url=site_url),
    }
    for name, text in queries.items():
        assert _bad(text) == [], name
        assert "OData.Feed" not in text, name
        assert _bad_options(text) == [], name
        sources = _data_source_urls(text)
        # One data source per query: the base inside Get, none elsewhere.
        assert len(sources) == (0 if name in _TABLES else 1), name
        if sources:
            assert text.count("Web.Contents(") == 1, name
            assert sources[0] == 'SiteUrl & "/_api/web"', name


@pytest.mark.parametrize("family", sorted(BLUEPRINTS))
def test_every_data_source_in_a_shipped_family_is_static(family: str) -> None:
    root = BLUEPRINTS[family]
    schema = parse_dbml(root / "10-design" / "schema.dbml")
    bundle = load_mapping(root / "20-configure" / "mapping.yaml")
    roles = sorted({entity.site_role for entity in bundle.mapping.entities.values()})
    seen = 0
    for role in roles:
        for site_url, zone in (
            (None, None),
            ("https://tenant.sharepoint.com/sites/Ops", "Australia/Melbourne"),
        ):
            for name, text in {
                **generate_powerquery(
                    schema, bundle, role, site_url=site_url, time_zone=zone,
                ),
                **generate_dictionary_powerquery(
                    schema, bundle, role, site_url=site_url, time_zone=zone,
                ),
            }.items():
                seen += len(_data_source_urls(text))
                assert _bad(text) == [], f"{family}/{role}/{name}"
                assert "OData.Feed" not in text, f"{family}/{role}/{name}"
                assert _bad_options(text) == [], f"{family}/{role}/{name}"
                assert len(_data_source_urls(text)) <= 1, f"{family}/{role}/{name}"
    assert seen


def test_every_read_goes_through_get_and_paging_moves_only_the_query() -> None:
    schema, bundle = pack(
        Path(__import__("tempfile").mkdtemp()), _PAIR_DBML, _PAIR_MAPPING,
    )
    text = _code(generate_powerquery(schema, bundle, "default")["APP_Risk.pq"])
    # No call reaches the network except through Get / GetAll.
    assert len(re.findall(r"Web\.Contents\(", text)) == 1
    assert len(re.findall(r"(?<![\w])Get(All)?\(", text)) >= 5
    # Paging: only the next link's query keys are carried over, never the link.
    assert "Uri.Parts(NextLink(_))[Query]" in text
    assert "Uri.Parts(NextLink(_)" in text and text.count("Uri.Parts(") == 1
    assert '#"$top" = "5000"' in text


@pytest.mark.parametrize(("title", "encoded"), [
    ("Risk Register", "Risk%20Register"),
    ("R&D", "R%26D"),
    ("Bob's List", "Bob%27%27s%20List"),
])
def test_a_list_title_is_percent_encoded_once_in_the_relative_path(
    title: str, encoded: str,
) -> None:
    from dataclasses import replace

    from dbml_sharepoint.analysis.reporting.names import query_name
    from dbml_sharepoint.analysis.reporting.plan import build_plans
    from dbml_sharepoint.generators.report_m import _render_m

    schema, bundle = pack(Path(__import__("tempfile").mkdtemp()), _PAIR_DBML, _PAIR_MAPPING)
    plans = build_plans(schema, bundle, "default")
    bases = {query_name(plan.list_title): plan for plan in plans}
    text = _render_m(replace(plans[0], list_title=title), bases)
    assert f"lists/getbytitle('{encoded}')/items" in text
    assert f"lists/getbytitle('{encoded}')/RootFolder" in text
    assert "%25" not in text


def test_a_list_with_no_rows_still_gets_every_declared_column() -> None:
    """A list with no rows answers with no columns; the step straight after the
    read adds each declared one, before the typing step names it."""
    schema, bundle = pack(
        Path(__import__("tempfile").mkdtemp()), _PAIR_DBML, _PAIR_MAPPING,
    )
    text = _code(generate_powerquery(schema, bundle, "default")["APP_Risk.pq"])
    assert text.index("Source = GetAll(") < text.index("Ensured = List.Accumulate(")
    typed = text.index("Typed = Table.TransformColumnTypes(")
    assert text.index("Ensured = List.Accumulate(") < typed
    assert "Table.AddColumn(t, c, each null, type text)" in text


@pytest.mark.parametrize("spelling", ["odata.nextLink", "@odata.nextLink"])
def test_a_page_carries_a_next_link_under_either_spelling(spelling: str) -> None:
    """One helper reads the link, trying each spelling, and paging asks only it."""
    schema, bundle = pack(
        Path(__import__("tempfile").mkdtemp()), _PAIR_DBML, _PAIR_MAPPING,
    )
    text = _code(generate_powerquery(schema, bundle, "default")["APP_Risk.pq"])
    helper = text.split("NextLink = ", 1)[1].split("),", 1)[0]
    assert f'"{spelling}"' in helper
    assert text.count(f'"{spelling}"') == 1
