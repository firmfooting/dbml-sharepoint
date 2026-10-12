# test/test_report_static_sources.py
"""Every data source a report query opens takes `SiteUrl & "<literal>"`.

The Power BI Service refuses to schedule a refresh for a data source whose
URL it cannot resolve statically (Learn, "Refresh and dynamic data
sources"). A computed site root, or a function parameter reaching
`OData.Feed`, is dynamic. Nothing in a build or in Desktop sees this, so the
shape is pinned here over the text of every generated query. The evidence is
in the findings records.
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
_STATIC_URL = re.compile(r'SiteUrl(\s*&\s*"(?:[^"]|"")*")+')


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


def _data_source_urls(query: str) -> list[str]:
    code = _code(query)
    return [
        _first_argument(code, match.end()).strip() for match in _SOURCE.finditer(code)
    ]


def _bad(query: str) -> list[str]:
    return [url for url in _data_source_urls(query) if not _STATIC_URL.fullmatch(url)]


def test_the_checker_separates_static_from_dynamic_urls() -> None:
    """The guard is only worth having if it fires on the shapes that were refused."""
    static = 'x = OData.Feed(SiteUrl & "/_api/web?$select=Title" & "", null, [A = 1])'
    assert _data_source_urls(static) == ['SiteUrl & "/_api/web?$select=Title" & ""']
    assert _bad(static) == []
    assert _bad('OData.Feed(SiteRoot & "/_api/web", null)') != []
    assert _bad("OData.Feed(url, null)") != []
    assert _bad('OData.Feed(Text.TrimEnd(SiteUrl, "/") & "/_api/web", null)') != []
    assert _bad('Web.Contents(SiteUrl & path)') != []
    assert _bad('SharePoint.Files(SiteUrl, [ApiVersion = 15])') != []
    assert _bad('// OData.Feed(url)\nOData.Feed(SiteUrl & "/a")') == []
    assert _data_source_urls('OData.Feed(SiteUrl & "a,(b""c")') == ['SiteUrl & "a,(b""c"']


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


@pytest.mark.parametrize("site_url", [None, "https://tenant.sharepoint.com/sites/Ops"])
def test_every_data_source_in_a_cross_list_bundle_is_static(
    tmp_path: Path, site_url: str | None,
) -> None:
    schema, bundle = pack(tmp_path, _PAIR_DBML, _PAIR_MAPPING)
    queries = {
        **generate_powerquery(schema, bundle, "default", site_url=site_url),
        **generate_dictionary_powerquery(schema, bundle, "default", site_url=site_url),
    }
    sources = {name: _data_source_urls(text) for name, text in queries.items()}
    # Every list reads the site, its time zone or folder, and the other list inline.
    assert len(sources["APP_Risk.pq"]) >= 4
    assert len(sources["_UserAddedColumns.pq"]) == 2
    for name, text in queries.items():
        assert _bad(text) == [], name


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
    assert seen
