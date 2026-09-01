# test/test_reportgen.py
import re
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from _model import bundle as make_bundle
from _model import column, person
from _model import enum as make_enum
from _model import ref as make_ref
from _model import schema as make_schema
from _model import table as make_table
from _paths import FIXTURES

from dbml_sharepoint.analysis.typemap import FieldKind, SPField, map_column
from dbml_sharepoint.generators import reportgen
from dbml_sharepoint.generators.reportgen import (
    generate_data_dictionary,
    generate_dictionary_powerquery,
    generate_dictionary_sql,
    generate_powerquery,
    generate_reporting_md,
    generate_sql_views,
)
from dbml_sharepoint.model.conditions import Group, Leaf
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import (
    ColumnValidation,
    EntitySection,
    FormVisibility,
    MappingBundle,
)
from dbml_sharepoint.model.parser import Column, Schema, TableIndex, parse_dbml
from dbml_sharepoint.model.release import load_release


def _simple() -> tuple[Schema, MappingBundle]:
    return (
        parse_dbml(FIXTURES / "simple.dbml"),
        load_mapping(FIXTURES / "sharepoint-mapping.yaml"),
    )


def _calculated() -> tuple[Schema, MappingBundle]:
    return (
        parse_dbml(FIXTURES / "calculated.dbml"),
        load_mapping(FIXTURES / "calculated-mapping.yaml"),
    )


def test_powerquery_one_query_per_entity_with_odata_feed() -> None:
    schema, bundle = _simple()
    queries = generate_powerquery(schema, bundle, "default")
    assert set(queries) == {"APP_Project.pq", "APP_Task.pq", "APP_AppSettings.pq"}
    task = queries["APP_Task.pq"]
    assert "OData.Feed(" in task
    assert "getbytitle('APP_Task')" in task
    # Parameterised, not hardcoded -- via the normalised SiteRoot, never the
    # raw parameter; see test_no_query_builds_an_endpoint_from_raw_site_url.
    assert "SiteRoot &" in task
    assert 'Text.TrimEnd(SiteUrl, "/")' in task


def test_powerquery_lookup_selects_join_key_and_expands_title() -> None:
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    # Join key comes back as the scalar <col>Id property...
    assert "ProjectId" in task
    # ...and the display title via $expand + record expansion.
    assert "$expand=Project" in task
    assert 'Table.ExpandRecordColumn' in task
    assert '"ProjectTitle"' in task


def test_powerquery_types_follow_the_schema() -> None:
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert '{"DueDate", type date}' in task
    assert '{"Id", Int64.Type}' in task
    schema, bundle = _calculated()
    risk = generate_powerquery(schema, bundle, "default")["APP_Risk.pq"]
    assert '{"RiskScore", type number}' in risk  # calculated_number
    assert '{"RiskBand", type text}' in risk     # calculated_text


def test_sql_views_typed_and_enriched_with_joins() -> None:
    schema, bundle = _simple()
    sql = generate_sql_views(schema, bundle, "default")
    assert "CREATE OR ALTER VIEW" in sql
    assert "[vw_APP_Task]" in sql
    assert "[vw_APP_Task_Enriched]" in sql
    # The enriched view joins the lookup target on the Id key.
    assert "LEFT JOIN" in sql
    assert "[ProjectId]" in sql
    assert "AS [ProjectTitle]" in sql
    # Types projected from the schema.
    assert "CAST(t.[DueDate] AS DATE)" in sql
    # SQLCMD-parameterised schemas, not hardcoded.
    assert ":setvar LandingSchema" in sql
    assert "$(ReportSchema)" in sql


def test_reporting_md_lists_relationships_for_power_bi() -> None:
    """On the site-qualified Key columns, never on Id.

    `Id` is unique within one list on one site. A report that appends the
    same list from several sites has three different rows with Id = 1, so a
    relationship on Id degrades from many-to-one to many-to-many and joins
    each child to the same-numbered parent on every site -- rendering
    happily with wrong numbers.
    """
    schema, bundle = _simple()
    md = generate_reporting_md(schema, bundle, "default")
    assert "| APP_Task | Project Key | APP_Project | Project Key |" in md
    assert "| APP_Task | ProjectId | APP_Project | Id |" not in md
    assert "SiteUrl" in md  # parameter setup instructions


def test_every_list_query_carries_the_site_it_came_from() -> None:
    """Without these, an appended multi-site table has nothing to slice by."""
    schema, bundle = _simple()
    queries = generate_powerquery(schema, bundle, "default")
    for name, query in queries.items():
        assert '"Site Url", each SiteRoot' in query, name
        assert '"Site Name", each SiteName' in query, name


def test_the_site_name_is_read_from_the_site_not_configured() -> None:
    """The whole point: nobody maintains a URL-to-name list by hand, and a
    site renamed in SharePoint shows its new name at the next refresh.

    `_api/web?$select=Title` is documented on Microsoft Learn and was
    confirmed against a live tenant to answer with an OData entry carrying
    `d:Title` -- the shape `OData.Feed` consumes.
    """
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert '"/_api/web?$select=Title"' in task


def test_each_query_resolves_its_own_site_name() -> None:
    """NOT a shared query, and this is the reason.

    A multi-site report is built by duplicating a list query per site and
    pointing each copy at a different URL. A single shared site-name query
    binds to ONE SiteUrl parameter, so every copy would be stamped with the
    first site's name -- wrong, and silently so, since the rows would be
    right and only the label wrong.

    Inline, the name is derived from whichever URL fetched the rows beside
    it, so a duplicate needs no edit beyond its site parameter.
    """
    schema, bundle = _simple()
    queries = generate_powerquery(schema, bundle, "default")
    assert not any(name.startswith("_Site") for name in queries)
    for name, query in queries.items():
        assert "SiteName =" in query, name
        assert '"/_api/web?$select=Title"' in query, name


def test_the_site_name_lookup_fails_soft() -> None:
    """A slicer label must not be able to take the refresh down.

    This is one of the few places the codebase should NOT fail closed: the
    rows are the data, the name is decoration, and an unhandled error here
    would fail every table in the report.
    """
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert "try" in task
    assert "otherwise SiteRoot," in task


def test_row_keys_are_site_qualified() -> None:
    """`Id` alone collides the moment a second site is appended.

    The site half only. The LIST half of the same key -- without which two
    lists on one site collide just as badly -- is pinned by
    `test_the_row_key_names_the_list_it_came_from` and the tests beside it.
    """
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert '"Task Key",' in task
    assert 'each SiteRoot & "|"' in task
    assert "Number.ToText([Id])" in task


# --------------------------------------------------- SiteUrl normalisation
#
# Measured on a live tenant, 2026-08-11. An operator set the SiteUrl
# parameter to the URL the address bar shows while VIEWING a list
# (.../sites/<site>/Lists/RC_CheckPoint) rather than the site root, so the
# queries requested .../Lists/RC_CheckPoint/_api/web/lists/getbytitle(
# 'RC_CheckPoint')/items -- the title twice and _api hung off a list, which
# is not a web -- and SharePoint answered 404 DataSource.NotFound. The
# generated header already said "site URL"; correct documentation did not
# prevent it, which is why the queries now normalise the value themselves.

# An M identifier is letters/digits/underscore, so these boundaries stop
# `SiteUrl` matching inside the `WithSiteUrl` STEP name, which is not a use
# of the parameter at all.
_RAW_SITE_URL = re.compile(r"(?<![A-Za-z0-9_])SiteUrl(?![A-Za-z0-9_])")

# The one place the raw parameter is legitimately read: the seed of the
# normalisation itself.
_NORMALISING_USE = 'Text.TrimEnd(SiteUrl, "/")'


def _all_powerquery(schema: Schema, bundle: MappingBundle) -> dict[str, str]:
    """Every generated .pq for the role -- list queries and dictionary alike."""
    return {
        **generate_powerquery(schema, bundle, "default"),
        **generate_dictionary_powerquery(schema, bundle, "default"),
    }


def _site_url_consumers(schema: Schema, bundle: MappingBundle) -> dict[str, str]:
    """The generated queries that read the SiteUrl parameter.

    _DataDictionary and _ModelInfo are static `#table` literals that never
    touch a site, so requiring the normalisation of them would be noise.
    Selection is on either name: a consumer that skipped normalisation
    still says `SiteUrl`, so it cannot filter itself out of the check.
    """
    return {
        name: query
        for name, query in _all_powerquery(schema, bundle).items()
        if _RAW_SITE_URL.search(query) or "SiteRoot" in query
    }


def _code_lines(query: str) -> list[str]:
    """Query lines with whole-line `//` comments dropped.

    The emitted M never puts a comment on the same line as code, so this is
    exact rather than approximate -- and it is checked, below, that the
    normalisation prose does not smuggle a passing assertion.
    """
    return [
        line for line in query.splitlines()
        if not line.lstrip().startswith("//")
    ]


def test_site_url_is_normalised_to_the_site_root_before_use() -> None:
    """A pasted list/form/page/API URL is trimmed back to the site.

    Signatures confirmed on Microsoft Learn (2026-08-11): Text.PositionOf
    answers -1 when the substring is absent, and Text.TrimEnd's second
    argument may be a single character to strip from the end.
    """
    schema, bundle = _simple()
    consumers = _site_url_consumers(schema, bundle)
    # Every list query plus the live drift audit -- named, so a selection
    # that quietly narrowed to nothing could not pass this vacuously.
    assert set(consumers) == {
        "APP_Project.pq", "APP_Task.pq", "APP_AppSettings.pq",
        "_UserAddedColumns.pq",
    }
    for name, query in consumers.items():
        assert "SiteRoot = Text.TrimEnd(" in query, name
        assert _NORMALISING_USE in query, name
        assert (
            '{"/_api/", "/_layouts/", "/lists/", "/sitepages/"}' in query
        ), name
        # -1 when absent, and a marker can never sit at position 0 of an
        # https:// URL, so the guard is `> 0` rather than `<> -1`.
        assert "if at > 0 then Text.Start(url, at) else url" in query, name


def test_the_normalisation_markers_are_lowercase() -> None:
    """The URL is lowered for the search, so a mixed-case marker never
    matches -- and the failure is silent: the 404 comes back exactly as it
    did before the fix. `/Lists/` is how SharePoint actually spells it in
    the address bar, so this is the plausible way to get it wrong.
    """
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert "Text.PositionOf(Text.Lower(url), marker)" in task
    markers = re.search(r"\{(\"/[^}]*?)\}", task)
    assert markers is not None
    for marker in re.findall(r'"([^"]+)"', markers.group(1)):
        assert marker == marker.lower(), marker


def test_no_query_builds_an_endpoint_from_raw_site_url() -> None:
    """The regression that matters, and the reason this is not a
    string-presence test.

    Normalising is worthless if the next consumer added to a query reaches
    for the parameter instead. Rather than enumerate today's consumers --
    which would pass forever while a new one went unnormalised -- assert the
    invariant: OUTSIDE the normalisation step, no generated query mentions
    `SiteUrl` in code at all. Every endpoint, link and key is therefore
    built from `SiteRoot`.
    """
    schema, bundle = _simple()
    for name, query in _all_powerquery(schema, bundle).items():
        for line in _code_lines(query):
            if not _RAW_SITE_URL.search(line):
                continue
            assert _NORMALISING_USE in line, (
                f"{name}: uses the raw SiteUrl parameter outside the "
                f"normalisation step -- {line.strip()!r}"
            )
        # The specific shape that was measured failing.
        assert 'SiteUrl & "/_api' not in query, name


def test_the_raw_site_url_check_can_actually_fail() -> None:
    """The guard above is only worth having if it fires.

    A comment-stripping helper that swallowed everything, or a boundary
    regex that matched nothing, would leave the test passing over any input
    -- indistinguishable from a clean bundle. So run it over a query with
    the defect deliberately reintroduced, plus one where the only mention is
    prose, and check it separates them.
    """
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]

    def offending_lines(query: str) -> list[str]:
        return [
            line for line in _code_lines(query)
            if _RAW_SITE_URL.search(line) and _NORMALISING_USE not in line
        ]

    assert offending_lines(task) == []
    # The 2026-08-11 defect, put back.
    assert offending_lines(task.replace("SiteRoot &", "SiteUrl &")) != []
    # A comment naming the parameter is not a use of it.
    assert offending_lines(task + "\n    // SiteUrl is the site root\n") == []
    # ...and the STEP name WithSiteUrl must not be read as one either.
    assert "WithSiteUrl = Table.AddColumn(" in task


def test_the_normalisation_records_the_live_run_that_prompted_it() -> None:
    """A bare Text.TrimEnd chain reads as superstition to the next person,
    who then "simplifies" it away and reopens a 404 nobody can place."""
    schema, bundle = _simple()
    consumers = _site_url_consumers(schema, bundle)
    assert consumers
    for name, query in consumers.items():
        assert "2026-08-11" in query, name
        assert "404" in query, name


# ------------------------------------ the site URL the build already knows
#
# `build` is given `--site-url`. Making the operator retype it into a Power
# Query parameter was work the tool could have done for them -- and the one
# step of the setup with a live 404 behind it (see above). It is bound into
# the queries now. `report`, which has no site at all, still emits the
# parameter form, and both shapes must stay correct.

_BAKED = "https://tenant.sharepoint.com/sites/Ops"


def _asks_for_a_parameter(query: str) -> bool:
    """Does the header tell the operator to create a `SiteUrl` parameter?

    Matched on the shape of the sentence rather than one literal: the list
    queries and the drift audit word it differently, and pinning either
    string would leave the other free to say the wrong thing.
    """
    return any(
        line.startswith("// Requires")
        and "SiteUrl" in line
        and "parameter" in line
        for line in query.splitlines()
    )


def _baked_powerquery(
    schema: Schema, bundle: MappingBundle, site_url: str = _BAKED,
) -> dict[str, str]:
    """Every generated .pq for the role, built with the site known."""
    return {
        **generate_powerquery(schema, bundle, "default", site_url=site_url),
        **generate_dictionary_powerquery(
            schema, bundle, "default", site_url=site_url,
        ),
    }


def _site_queries(queries: dict[str, str]) -> dict[str, str]:
    """The queries that talk to a site.

    _DataDictionary and _ModelInfo are static `#table` literals with no site
    in them; asserting anything about a URL over those would be noise, and
    silently vacuous if the selection ever emptied -- so callers check the
    names they get back.
    """
    return {n: q for n, q in queries.items() if "SiteRoot" in q}


def _binding_line(query: str) -> str | None:
    """The `SiteUrl = …` binding line, verbatim, or None."""
    for line in _code_lines(query):
        if line.strip().startswith("SiteUrl ="):
            return line
    return None


def test_a_known_site_url_is_bound_in_the_query_not_configured() -> None:
    """The whole point: the pack loads with nothing to set up.

    Asserted as the FIRST binding of the `let`, not merely present
    somewhere: M is order-dependent, and a binding emitted after the
    SiteRoot step that consumes it is an unbound-identifier error the build
    cannot see.
    """
    schema, bundle = _simple()
    queries = _baked_powerquery(schema, bundle)
    consumers = _site_queries(queries)
    # Named, so a selection that quietly narrowed could not pass vacuously.
    assert set(consumers) == {
        "APP_Project.pq", "APP_Task.pq", "APP_AppSettings.pq",
        "_UserAddedColumns.pq",
    }
    for name, query in consumers.items():
        code = _code_lines(query)
        assert code[code.index("let") + 1] == f'    SiteUrl = "{_BAKED}",', name


def test_the_parameter_header_is_emitted_only_when_no_site_is_known() -> None:
    """`report` has no site, so its queries must still ask for one -- and a
    baked query must not, or the operator creates a parameter that nothing
    reads and believes the pack is configured when it is not."""
    schema, bundle = _simple()
    baked = _baked_powerquery(schema, bundle)
    unknown = _all_powerquery(schema, bundle)
    assert set(baked) == set(unknown)
    named = set(_site_queries(unknown))
    assert named == {
        "APP_Project.pq", "APP_Task.pq", "APP_AppSettings.pq",
        "_UserAddedColumns.pq",
    }
    for name in named:
        assert _asks_for_a_parameter(unknown[name]), name
        assert _binding_line(unknown[name]) is None, name
        assert not _asks_for_a_parameter(baked[name]), name


def test_a_baked_query_binds_every_name_it_reads() -> None:
    """The property the header check is a proxy for.

    A query that dropped the binding but also dropped the header would pass
    a header-absence test, open cleanly in the Advanced Editor, and fail at
    refresh with "SiteUrl not recognised" -- so assert the binding exists
    wherever the name is read, in both shapes.
    """
    schema, bundle = _simple()
    for label, queries in (
        ("baked", _baked_powerquery(schema, bundle)),
        ("parameter", _all_powerquery(schema, bundle)),
    ):
        for name, query in _site_queries(queries).items():
            reads = [
                line for line in _code_lines(query)
                if _RAW_SITE_URL.search(line) and _binding_line(query) != line
            ]
            assert reads, f"{label}/{name}: nothing reads SiteUrl at all"
            bound = _binding_line(query) is not None
            assert bound == (label == "baked"), f"{label}/{name}"


def test_a_baked_site_url_is_still_normalised_before_use() -> None:
    """The 0d2eff2 trim stays in the baked shape.

    A URL the build supplied is already a site root, so this looks like
    dead code -- but that one line is now the DOCUMENTED place to hand-edit
    for a second site, which makes it MORE likely to receive a pasted list
    URL than the parameter ever was, not less.
    """
    schema, bundle = _simple()
    listy = "https://tenant.sharepoint.com/sites/Ops/Lists/APP_Task"
    consumers = _site_queries(_baked_powerquery(schema, bundle, listy))
    assert set(consumers) == {
        "APP_Project.pq", "APP_Task.pq", "APP_AppSettings.pq",
        "_UserAddedColumns.pq",
    }
    for name, query in consumers.items():
        assert "SiteRoot = Text.TrimEnd(" in query, name
        assert _NORMALISING_USE in query, name
        # The invariant of test_no_query_builds_an_endpoint_from_raw_site_url,
        # carried into the baked shape: outside the binding itself and the
        # seed of the normalisation, nothing reads the raw value. Written as
        # an invariant rather than a list of today's consumers, so the next
        # step added to a query cannot skip the trim unnoticed.
        binding = _binding_line(query)
        for line in _code_lines(query):
            if not _RAW_SITE_URL.search(line) or line == binding:
                continue
            assert _NORMALISING_USE in line, (
                f"{name}: uses the baked SiteUrl outside the normalisation "
                f"step -- {line.strip()!r}"
            )


def _read_m_literal(literal: str) -> tuple[str, str]:
    """Read an M text literal the way the engine would: `""` is one quote,
    the first single quote ends it. Returns (value, whatever followed).

    Written from the grammar rather than by inverting reportgen's own
    escaper, which could be wrong in the same direction and still agree
    with itself. The trailing text is returned instead of discarded because
    that is precisely what a dropped escape produces -- the literal closes
    early and the remainder of the line becomes M code.
    """
    assert literal.startswith('"'), literal
    out: list[str] = []
    i = 1
    while i < len(literal):
        if literal[i] == '"':
            if literal[i + 1:i + 2] == '"':
                out.append('"')
                i += 2
                continue
            return "".join(out), literal[i + 1:]
        out.append(literal[i])
        i += 1
    raise AssertionError(f"unterminated M literal: {literal!r}")


def test_the_m_literal_reader_separates_escaped_from_broken() -> None:
    """The escaping test below is only worth having if its reader can tell
    the two apart."""
    assert _read_m_literal('"a""b"') == ('a"b', "")
    assert _read_m_literal('"a" & b') == ("a", " & b")


def test_the_baked_site_url_cannot_break_out_of_the_m_literal() -> None:
    """`--site-url` is operator input, interpolated into emitted code.

    An unescaped `"` closes the literal and turns the rest of the line into
    M -- a query that fails to parse if you are lucky, and one that quietly
    means something else if you are not. Nothing between here and the
    operator's Advanced Editor would notice.
    """
    schema, bundle = _simple()
    hostile = 'https://tenant.sharepoint.com/sites/A" & Text.From(1) & "B'
    task = generate_powerquery(
        schema, bundle, "default", site_url=hostile,
    )["APP_Task.pq"]
    line = _binding_line(task)
    assert line is not None
    literal = line.strip().removeprefix("SiteUrl = ").removesuffix(",")
    value, trailing = _read_m_literal(literal)
    # Round-trips exactly, and nothing escaped onto the line beside it.
    assert value == hostile
    assert trailing == ""


def test_the_sql_script_carries_the_site_url_when_the_build_knows_it() -> None:
    """Same rule as the M queries, so a pack is configured or not as a
    whole rather than half of each."""
    schema, bundle = _simple()
    known = generate_sql_views(schema, bundle, "default", site_url=_BAKED)
    unknown = generate_sql_views(schema, bundle, "default")
    placeholder = reportgen._SQL_SITE_URL_PLACEHOLDER
    assert f":setvar SiteUrl {_BAKED}" in known.splitlines()
    assert placeholder not in known
    assert f":setvar SiteUrl {placeholder}" in unknown.splitlines()
    assert _BAKED not in unknown


def test_the_baked_sql_site_url_does_not_double_the_slash() -> None:
    """`$(SiteUrl)` is pasted straight in front of a path that already
    starts with `/`. Unlike the M queries there is no normalisation step to
    absorb a second one, so the ItemURL link would 404 on every row."""
    schema, bundle = _simple()
    sql = generate_sql_views(schema, bundle, "default", site_url=_BAKED + "/")
    setvar = next(
        line for line in sql.splitlines() if line.startswith(":setvar SiteUrl ")
    )
    value = setvar.removeprefix(":setvar SiteUrl ")
    # Substituted the way SQLCMD would, rather than eyeballing the setvar.
    links = [
        line.replace("$(SiteUrl)", value)
        for line in sql.splitlines() if "$(SiteUrl)" in line
    ]
    assert links
    for link in links:
        assert "//Lists" not in link, link


def test_the_guide_matches_the_queries_shipped_beside_it() -> None:
    """A guide is read once, at the start. One that opens with "create a
    parameter" over queries that need none costs the operator the whole
    first hour, and nothing downstream contradicts it."""
    schema, bundle = _simple()
    baked = generate_reporting_md(schema, bundle, "default", site_url=_BAKED)
    unknown = generate_reporting_md(schema, bundle, "default")
    assert "Manage Parameters" in unknown
    assert "Manage Parameters" not in baked
    assert "Nothing to configure" in baked
    assert _BAKED in baked
    # The multi-site route survives in both, and stays the reason the
    # site-name lookup is per-query rather than shared.
    for md in (baked, unknown):
        assert "Duplicate each list query" in md
        assert "Append" in md


def test_emit_reporting_bakes_the_build_site_into_the_whole_pack(
    tmp_path: Path,
) -> None:
    """The pack is consumed as a unit. A list query with the URL baked in,
    beside an audit query that still wants a parameter and a guide that
    tells you to make one, is worse than either choice made consistently.
    """
    from dbml_sharepoint.generators.reportgen import emit_reporting
    schema, bundle = _simple()

    emit_reporting(
        tmp_path, schema, bundle, "default",
        release=None, generated_at="2026-08-11T00:00:00Z",
        source_schema="simple.dbml", source_mapping="sharepoint-mapping.yaml",
        site_url=_BAKED,
    )

    pq = sorted((tmp_path / "reporting" / "powerquery").glob("*.pq"))
    assert {p.name for p in pq} == {
        "APP_Project.pq", "APP_Task.pq", "APP_AppSettings.pq",
        "_DataDictionary.pq", "_ModelInfo.pq", "_UserAddedColumns.pq",
    }
    checked = 0
    for path in pq:
        text = path.read_text(encoding="utf-8")
        if "SiteRoot" not in text:
            continue
        assert f'    SiteUrl = "{_BAKED}",' in text.splitlines(), path.name
        assert not _asks_for_a_parameter(text), path.name
        checked += 1
    assert checked == 4  # three lists plus the drift audit
    sql = (tmp_path / "reporting" / "sql" / "views.sql").read_text(
        encoding="utf-8",
    )
    assert f":setvar SiteUrl {_BAKED}" in sql.splitlines()
    guide = (tmp_path / "reporting" / "guide.md").read_text(encoding="utf-8")
    assert "Manage Parameters" not in guide


def test_a_null_lookup_does_not_break_the_refresh() -> None:
    """`Number.ToText(null)` raises rather than returning null, so an
    optional lookup left blank would fail the whole refresh."""
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert "if [ProjectId] = null then null" in task


def test_report_respects_site_role_filter() -> None:
    """Entities outside the requested site role are not reported on."""
    schema, bundle = _simple()
    # All fixture entities are role 'default'; asking for another role
    # yields nothing rather than everything.
    assert generate_powerquery(schema, bundle, "admin") == {}


def test_powerquery_adds_itemurl_helper_column() -> None:
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert "Table.AddColumn" in task
    assert '"ItemURL"' in task
    assert "/Lists/APP_Task/DispForm.aspx?ID=" in task


def test_sql_views_add_itemurl_helper_column() -> None:
    schema, bundle = _simple()
    sql = generate_sql_views(schema, bundle, "default")
    assert ":setvar SiteUrl" in sql
    assert "AS [ItemURL]" in sql
    assert "/Lists/APP_Task/DispForm.aspx?ID=" in sql


def test_data_dictionary_documents_every_list_and_column() -> None:
    schema, bundle = _simple()
    md = generate_data_dictionary(schema, bundle, "default")
    assert "## APP_Task" in md
    assert "| DueDate |" in md
    # Choice members come from the authoritative DBML enum.
    assert "Open" in md
    assert "Closed" in md
    # Lookup target and helper column are documented.
    assert "APP_Project" in md
    assert "ItemURL" in md


def test_data_dictionary_rejects_composite_indexes() -> None:
    schema, bundle = _simple()
    task = next(table for table in schema.tables if table.name == "Task")
    task.indexes = [TableIndex(("Project", "DueDate"))]
    with pytest.raises(ValueError, match="composite DBML indexes"):
        generate_data_dictionary(schema, bundle, "default")


def test_data_dictionary_includes_calculated_formulas() -> None:
    schema, bundle = _calculated()
    md = generate_data_dictionary(schema, bundle, "default")
    assert '=IF([Severity]="High",10,1)' in md


def test_data_dictionary_includes_lookup_projections() -> None:
    schema = make_schema(
        make_table("Person", column("Title")),
        make_table("Risk", make_ref("Owner", "Person.Id")),
    )
    bundle = make_bundle(
        entities=["Risk", "Person"],
        lookup_projections={"Risk": {"Owner": ["Title"]}},
    )
    md = generate_data_dictionary(schema, bundle, "default")
    assert "OwnerTitle" in md
    assert "read-only dependent" in md


def test_data_dictionary_includes_deployment_metadata() -> None:
    schema, bundle = _simple()
    release = load_release(FIXTURES / "release.yaml")
    md = generate_data_dictionary(
        schema, bundle, "default",
        release=release,
        generated_at="2026-07-22T00:00:00+00:00",
        source_schema="simple.dbml",
        source_mapping="sharepoint-mapping.yaml",
    )
    assert "0.1.0-test" in md       # release tag
    assert "0.8" in md              # schema version
    assert "simple.dbml" in md
    assert "sharepoint-mapping.yaml" in md
    assert "2026-07-22T00:00:00+00:00" in md


def test_dictionary_powerquery_returns_report_ready_tables() -> None:
    """The dictionary ships as loadable queries so any report can surface it
    as a page: _DataDictionary (column rows) + _ModelInfo (metadata rows)."""
    schema, bundle = _simple()
    queries = generate_dictionary_powerquery(schema, bundle, "default")
    assert set(queries) == {
        "_DataDictionary.pq", "_ModelInfo.pq", "_UserAddedColumns.pq",
    }
    dd = queries["_DataDictionary.pq"]
    assert "#table(" in dd
    assert '"APP_Task", "DueDate", "Date"' in dd
    mi = queries["_ModelInfo.pq"]
    assert '"Generator", "dbml-sharepoint' in mi


def test_dictionary_powerquery_stamps_release_metadata() -> None:
    schema, bundle = _simple()
    release = load_release(FIXTURES / "release.yaml")
    mi = generate_dictionary_powerquery(
        schema, bundle, "default",
        release=release, generated_at="2026-07-22T00:00:00+00:00",
    )["_ModelInfo.pq"]
    assert "0.1.0-test" in mi
    assert "2026-07-22T00:00:00+00:00" in mi


def test_dictionary_powerquery_escapes_embedded_quotes() -> None:
    """Calculated formulas contain double quotes; M doubles them in string
    literals. An unescaped quote would break the whole query."""
    schema, bundle = _calculated()
    dd = generate_dictionary_powerquery(schema, bundle, "default")["_DataDictionary.pq"]
    assert '=IF([Severity]=""High"",10,1)' in dd


def test_dictionary_sql_views_from_values() -> None:
    schema, bundle = _simple()
    sql = generate_dictionary_sql(schema, bundle, "default")
    assert "[vw_APP_DataDictionary]" in sql
    assert "[vw_APP_ModelInfo]" in sql
    assert "FROM (VALUES" in sql
    assert "N'APP_Task'" in sql  # rows embedded, no landing table needed


def test_cli_report_writes_queries_and_docs(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from dbml_sharepoint.cli import app

    out = tmp_path / "reports"
    result = CliRunner().invoke(app, [
        "report",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    assert (out / "powerquery" / "APP_Task.pq").exists()
    assert (out / "sql" / "views.sql").exists()
    assert (out / "guide.md").exists()
    dictionary = (out / "data-dictionary.md").read_text(encoding="utf-8")
    assert "0.1.0-test" in dictionary  # release metadata stamped
    # The dictionary is also emitted as report-loadable artefacts.
    model_info = (out / "powerquery" / "_ModelInfo.pq").read_text(encoding="utf-8")
    assert "0.1.0-test" in model_info
    assert (out / "powerquery" / "_DataDictionary.pq").exists()
    assert (out / "powerquery" / "_UserAddedColumns.pq").exists()
    views = (out / "sql" / "views.sql").read_text(encoding="utf-8")
    assert "[vw_APP_DataDictionary]" in views
    assert "[vw_APP_ModelInfo]" in views
    assert "[vw_APP_UserAddedColumns]" in views


def test_cli_report_works_without_release(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from dbml_sharepoint.cli import app

    out = tmp_path / "reports"
    result = CliRunner().invoke(app, [
        "report",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    assert (out / "data-dictionary.md").exists()


def test_cli_report_rejects_unknown_site_role(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from dbml_sharepoint.cli import app

    result = CliRunner().invoke(app, [
        "report",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--site-role", "no-such-role",
        "--out", str(tmp_path / "reports"),
    ])
    assert result.exit_code == 2
    assert "no-such-role" in result.output


# --- Reporting integration (display names, ordinals, HTML flags) ------------


def test_powerquery_renames_columns_to_display_titles() -> None:
    """The Power BI model must speak the same language as the forms and
    views staff see: with display names on, each query ends with a
    RenameColumns step from internal to display names (internal names stay
    the wire/OData contract; the rename is the last step)."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    queries = generate_powerquery(schema, bundle, "default")
    project = queries["APP_Project.pq"]
    assert "RenamedForModel = Table.RenameColumns(" in project
    assert '{"SortOrder", "Sort Order"}' in project
    assert '{"ItemURL", "Item URL"}' in project
    assert "MissingField.Ignore" in project
    assert project.rstrip().endswith("RenamedForModel")


def test_powerquery_byte_stable_without_display_names() -> None:
    schema = parse_dbml(FIXTURES / "calculated.dbml")
    bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    queries = generate_powerquery(schema, bundle, "default")
    assert all("RenameColumns" not in q for q in queries.values())


def test_dictionary_choice_members_carry_ordinals() -> None:
    """Choice values sort alphabetically in Power BI (Extreme before Low);
    the dictionary publishes declaration-order ordinals so report authors
    build sort-by-column mappings without hand-made lookup tables."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    md = generate_data_dictionary(schema, bundle, "default")
    assert "Choice: 1. Open, 2. Closed" in md


def test_dictionary_flags_rich_text_as_html() -> None:
    schema = make_schema(
        make_table("Risk", column("Title", required=True), column("Detail", "richtext")),
    )
    bundle = make_bundle(entities=["Risk"])
    md = generate_data_dictionary(schema, bundle, "default")
    assert "HTML over OData" in md
    assert "strip markup" in md


# --- User-added column audit (reporting-layer drift detection) --------------


def test_user_added_columns_powerquery_audits_every_list() -> None:
    """_UserAddedColumns.pq reads each list's /fields collection live and
    filters IN M (never OData $filter): visible, not read-only, deletable
    (CanBeDeleted=false already covers sealed and base-type built-ins),
    then anti-joins the declared internal names. Empty on a healthy site."""
    schema, bundle = _simple()
    queries = generate_dictionary_powerquery(schema, bundle, "default")
    assert "_UserAddedColumns.pq" in queries
    q = queries["_UserAddedColumns.pq"]
    assert "/fields" in q
    assert "$select=InternalName,Title,TypeAsString,Hidden,ReadOnlyField,CanBeDeleted" in q
    assert "not [Hidden] and not [ReadOnlyField] and [CanBeDeleted]" in q
    assert "Table.Combine" in q
    for lst in ("APP_Project", "APP_Task", "APP_AppSettings"):
        assert f'Audit("{lst}"' in q
    # The single documented tenant exclusion.
    assert '"ComplianceAssetId"' in q


def test_user_added_columns_expected_sets_use_internal_names() -> None:
    """The anti-join set must hold declared INTERNAL field names, the
    lookup as 'Project', never the OData item path 'Project/Title' nor the
    derived join-key output 'ProjectId' (those exist only in the data
    queries' $select)."""
    schema, bundle = _simple()
    q = generate_dictionary_powerquery(schema, bundle, "default")["_UserAddedColumns.pq"]
    assert '"Project"' in q
    assert '"DueDate"' in q
    assert "Project/Title" not in q
    assert '"ProjectId"' not in q


def test_user_added_columns_sql_view_antijoins_information_schema() -> None:
    """vw_<prefix>UserAddedColumns lists landed columns the schema does not
    declare: INFORMATION_SCHEMA.COLUMNS over the landing tables, NOT EXISTS
    against embedded (list, expected column) VALUES, Id plus each landed
    name (lookups land as <name>Id). Empty by default; sees only what the
    extractor lands."""
    schema, bundle = _simple()
    sql = generate_dictionary_sql(schema, bundle, "default")
    assert "[vw_APP_UserAddedColumns]" in sql
    assert "INFORMATION_SCHEMA.COLUMNS" in sql
    assert "TABLE_SCHEMA = '$(LandingSchema)'" in sql
    assert "NOT EXISTS" in sql
    assert "(N'APP_Task', N'Id')" in sql
    assert "(N'APP_Task', N'ProjectId')" in sql
    assert "(N'APP_Task', N'DueDate')" in sql


def test_reporting_md_documents_user_added_column_audit() -> None:
    schema, bundle = _simple()
    md = generate_reporting_md(schema, bundle, "default")
    assert "## User-added column audit" in md
    assert "_UserAddedColumns" in md
    assert "vw_APP_UserAddedColumns" in md


def test_emit_reporting_writes_bundle_and_returns_relpaths(tmp_path: Path) -> None:
    """Both CLIs ship reporting through this one helper, so the artifact
    set cannot drift between them. It returns the exact relpaths written,
    POSIX separators, for checksums.txt."""
    from dbml_sharepoint.generators.reportgen import emit_reporting
    schema, bundle = _simple()
    release = load_release(FIXTURES / "release.yaml")

    relpaths = emit_reporting(
        tmp_path, schema, bundle, "default",
        release=release, generated_at="2026-05-04T00:00:00Z",
        source_schema="simple.dbml", source_mapping="sharepoint-mapping.yaml",
    )

    for fixed in ("reporting/sql/views.sql", "reporting/guide.md",
                  "reporting/data-dictionary.md"):
        assert fixed in relpaths
    assert any(p.startswith("reporting/powerquery/") and p.endswith(".pq")
               for p in relpaths)
    assert not any("\\" in p for p in relpaths)
    for relpath in relpaths:
        assert (tmp_path / relpath).is_file(), relpath
    # Nothing written outside reporting/, nothing written but not returned.
    on_disk = {p.relative_to(tmp_path).as_posix()
               for p in tmp_path.rglob("*") if p.is_file()}
    assert on_disk == set(relpaths)


def test_calculated_date_reports_as_date() -> None:
    """A calculated date column must land as a date in both reporting
    surfaces (M `type date` and SQL `DATE`), not the text fallback."""
    schema = make_schema(
        make_table(
            "Risk",
            column("Title", required=True),
            column("NextReviewDue", "calculated_date"),
        ),
    )
    bundle = make_bundle(
        entities=["Risk"],
        calculated_formulas={"Risk": {"NextReviewDue": "=DATE(2026,1,1)"}},
    )
    pq = generate_powerquery(schema, bundle, "default")["APP_Risk.pq"]
    assert "NextReviewDue" in pq
    assert "type date" in pq
    sql = generate_sql_views(schema, bundle, "default")
    assert any(
        "NextReviewDue" in line and " DATE" in line
        for line in sql.splitlines()
    ), sql


# --- Declared form behaviour in the reporting bundle -------------------------
#
# reportgen was not in the form_visibility branch's diff at all: bundles were
# byte-identical with and without every declaration. An analyst seeing a
# 100%-blank column could not tell it was hidden by design from a column
# that nobody fills in, and a save rule that governs the data was invisible
# to everyone who consumes the data.


def _declared() -> tuple[Schema, MappingBundle]:
    schema = make_schema(
        make_table(
            "Escalation",
            column("Title", required=True),
            column("Route"),
            column("Resolution"),
            column("Status"),
        ),
    )
    bundle = make_bundle(
        entities=["Escalation"],
        form_visibility={
            "Escalation": EntitySection(columns={
                # `Route: hidden` is the loader's shorthand for both flags off.
                "Route": FormVisibility(new=False, existing=False),
                "Resolution": FormVisibility(
                    new=False,
                    when=Group("all_of", (
                        Leaf(field="Status", op="eq", value="Resolved"),
                    )),
                ),
            }),
        },
        column_validation={
            "Escalation": EntitySection(columns={
                "Resolution": ColumnValidation(
                    when=Group("all_of", (
                        Leaf(field="Resolution", op="gt", value=10, measure="length"),
                    )),
                    message="Give at least a sentence.",
                ),
            }),
        },
    )
    return schema, bundle


def test_data_dictionary_reports_form_visibility_and_save_rules() -> None:
    schema, bundle = _declared()
    doc = generate_data_dictionary(schema, bundle, "default")
    assert "Populated when" in doc
    assert "Save rule" in doc
    # Described, never target syntax: `[$ID] != ''` means nothing to a
    # report author, and it is the one thing they must not have to decode.
    assert "[$ID]" not in doc
    assert "Never on a form" in doc                    # Route: hidden
    assert "Status eq 'Resolved'" in doc               # the when tree, described
    assert "Give at least a sentence." in doc          # the author's own message
    assert "length(Resolution) gt 10" in doc


def test_dictionary_powerquery_and_sql_carry_the_same_two_columns() -> None:
    """The analyst consuming the bundle sees what the form does, not just
    what the column is."""
    schema, bundle = _declared()
    pq = generate_dictionary_powerquery(schema, bundle, "default")["_DataDictionary.pq"]
    assert "PopulatedWhen = text" in pq
    assert "SaveRule = text" in pq
    assert "Give at least a sentence." in pq
    sql = generate_dictionary_sql(schema, bundle, "default")
    assert "PopulatedWhen" in sql
    assert "SaveRule" in sql


def test_user_added_columns_selects_the_deployed_formula_properties() -> None:
    """_UserAddedColumns is the only LIVE query in the bundle and already
    calls /fields on every refresh. Selecting the two formula properties
    turns it into a refresh-time check that the deployed contract still
    matches the dictionary, for free."""
    schema, bundle = _declared()
    pq = generate_dictionary_powerquery(schema, bundle, "default")["_UserAddedColumns.pq"]
    assert "ClientValidationFormula" in pq
    assert "ValidationFormula" in pq


def test_undeclared_columns_read_as_dashes_not_blanks() -> None:
    """Absence must be legible. An empty cell reads as missing data. The
    analyst cannot tell "no rule declared" from "the generator did not
    know", which is the same ambiguity this whole change exists to remove."""
    schema, bundle = _declared()
    doc = generate_data_dictionary(schema, bundle, "default")

    def cells(column: str) -> list[str]:
        row = next(ln for ln in doc.splitlines() if ln.startswith(f"| {column} |"))
        return [c.strip() for c in row.split("|")]

    # Columns 8 and 9 are Populated when / Save rule (6 and 7 are the
    # retirement pair, which this mapping declares for nothing).
    assert cells("Status")[8] == "-"
    assert cells("Status")[9] == "-"
    assert cells("Resolution")[8] != "-"
    assert cells("Resolution")[9] != "-"


def _retired() -> tuple[Schema, MappingBundle]:
    return (
        parse_dbml(FIXTURES / "retired.dbml"),
        load_mapping(FIXTURES / "retired-mapping.yaml"),
    )


def test_data_dictionary_documents_retirement() -> None:
    schema, bundle = _retired()
    md = generate_data_dictionary(schema, bundle, "default")
    assert "| Retired | Superseded by |" in md
    assert "| 2026-09-01 | SiteServicesStatus |" in md
    # A live column carries the em-dash placeholder, not a blank cell.
    assert "| SiteServicesStatus | Choice" in md


def test_dictionary_powerquery_and_sql_carry_retirement() -> None:
    schema, bundle = _retired()
    dd = generate_dictionary_powerquery(schema, bundle, "default")["_DataDictionary.pq"]
    assert "Retired = text, SupersededBy = text" in dd
    assert '"2026-09-01", "SiteServicesStatus"' in dd
    sql = generate_dictionary_sql(schema, bundle, "default")
    assert "[Retired]" in sql
    assert "[SupersededBy]" in sql
    assert "N'2026-09-01'" in sql


def test_user_added_columns_still_expects_retired_columns() -> None:
    """The whole point of retiring rather than deleting: the column stays
    declared, so the live drift audit must keep expecting it. A row for a
    retired column would erode the "any row here means investigate"
    contract on every refresh, forever."""
    schema, bundle = _retired()
    q = generate_dictionary_powerquery(schema, bundle, "default")["_UserAddedColumns.pq"]
    assert '"OperationsStatus"' in q
    sql = generate_dictionary_sql(schema, bundle, "default")
    assert "N'OperationsStatus'" in sql


def test_powerquery_still_selects_retired_columns() -> None:
    """History is the entire point; the list query must keep selecting the
    retired column."""
    schema, bundle = _retired()
    q = generate_powerquery(schema, bundle, "default")["APP_Board.pq"]
    assert "OperationsStatus" in q


def _kind_swapped(
    monkeypatch: pytest.MonkeyPatch, column_name: str, kind: str,
) -> None:
    """Make `_build_plans` see one column as a field kind it does not handle.

    Monkeypatched rather than schema-driven on purpose: the guard has to hold
    for the NEXT kind somebody adds to `typemap.FieldKind`, and a kind that
    exists is a kind somebody has already had the chance to wire up here.
    """
    def fake(col: Column, enum_names: set[str]) -> SPField:
        sp = map_column(col, enum_names)
        if col.name == column_name:
            return replace(sp, kind=cast("FieldKind", kind))
        return sp

    monkeypatch.setattr(reportgen, "map_column", fake)


def test_build_plans_refuses_a_field_kind_it_does_not_handle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unhandled `sp.kind` must abort, because the two drift audits
    disagree about it and neither of them can say so.

    `field_internal_names` is appended BEFORE the match, so an unhandled kind
    is recorded as a column the list is expected to have while contributing no
    `$select`, no Power Query type and no SQL column. `_UserAddedColumns.pq`
    is built from the expected list, so the M audit sees nothing wrong; the
    SQL audit is built from `sql_columns`, so it reports the same column as an
    unexpected user-added one. Two audits over one deployment, contradicting
    each other, with the column silently absent from every query that was
    supposed to carry it.

    A `case _` that raises is the only version of this the build can see.
    """
    schema, bundle = _simple()
    _kind_swapped(monkeypatch, "Title", "Uncharted")

    with pytest.raises(ValueError, match="Uncharted") as err:
        generate_powerquery(schema, bundle, "default")

    # Named well enough to fix from the message alone: which column, on which
    # entity, and what has to be taught about it.
    assert "Title" in str(err.value)
    assert "Project" in str(err.value)


def test_the_sql_view_builder_refuses_the_same_unhandled_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The SQL side is the audit that reports a FALSE POSITIVE on an
    unhandled kind, so it must fail closed too rather than emitting a view
    that quietly omits the column."""
    schema, bundle = _simple()
    _kind_swapped(monkeypatch, "Title", "Uncharted")

    with pytest.raises(ValueError, match="Uncharted"):
        generate_sql_views(schema, bundle, "default")


def test_the_dictionary_refuses_a_field_kind_it_has_no_arm_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`generate_data_dictionary` is the ONE entry point that never calls
    `_build_plans`, so the guard there cannot cover it.

    `_sp_type_cell` ended `return sp.kind`, which put the raw internal token
    -- `MultiChoice` -- in the "SharePoint type" column of
    data-dictionary.md, `_DataDictionary.pq` and `vw_<prefix>DataDictionary`
    alike. That is a document stating a column's type wrongly in the one
    place a report author goes to look it up, and nothing else in this module
    can see it happen.

    The loadable dictionary tables were already covered, incidentally:
    `generate_dictionary_powerquery` and `generate_dictionary_sql` both build
    `_UserAddedColumns` and so go through `_build_plans` before they return.
    The markdown page is the only entry point in this module that does not,
    which is exactly why the leak survived there.
    """
    schema, bundle = _simple()
    _kind_swapped(monkeypatch, "Title", "Uncharted")

    with pytest.raises(ValueError, match="Uncharted") as err:
        generate_data_dictionary(schema, bundle, "default")

    assert "_sp_type_cell" in str(err.value)


# --- Multi-value columns ----------------------------------------------------


def _multi_value(*, display_names: bool = False) -> tuple[Schema, MappingBundle]:
    """A schema declaring a multi-value column, the thing S9 exists to report.

    `AuditEvents` rather than `Events` so the display-name test has a name that
    auto-splits, and one member carries a space because that is what rules the
    separator choice: a multi-value member is a phrase, not a token.
    """
    schema = make_schema(
        make_table(
            "Platform",
            column("Title", required=True),
            column("AuditEvents", "audit_event[]"),
        ),
        enums=[make_enum("audit_event", "View", "Edit", "Permission change")],
    )
    if display_names:
        return schema, make_bundle(entities=["Platform"], display_name_mode="auto")
    return schema, make_bundle(entities=["Platform"])


def test_powerquery_joins_a_multi_value_column_into_one_text_cell() -> None:
    """MEASURED 2026-08-10: under `odata=nometadata`, which is what the
    Power Query layer speaks, a multi-value item value comes back as a bare
    JSON array, so the cell holds a LIST, not text.

    The scalar arm's `Table.TransformColumnTypes(…, type text)` over a list
    does not produce a mistyped column; it produces an Error value in every
    populated cell, and the query still loads. The join has to happen before
    anything tries to type it, and the type is then ascribed by the step that
    produced the text.
    """
    schema, bundle = _multi_value()
    q = generate_powerquery(schema, bundle, "default")["APP_Platform.pq"]

    assert "$select=Id,Title,AuditEvents" in q
    assert "Table.TransformColumns(" in q
    assert 'Text.Combine(_, "; ")' in q
    assert "type text}" in q
    # The raw list must never reach the typing step: that is the failure this
    # arm exists to avoid, not a cosmetic difference.
    assert '{"AuditEvents", type text},' not in q
    assert '{"AuditEvents", type text}\n' not in q


def test_powerquery_renders_an_empty_multi_value_set_as_blank() -> None:
    """MEASURED 2026-08-10: an empty multi-value set reads back as `null`,
    NOT as `[]`.

    `Text.Combine(null, "; ")` raises, and a raise inside a transform fails
    the whole refresh. One row that has never had a value would take the
    report down. Guarded, the cell is blank, which is what "no members" means.
    """
    schema, bundle = _multi_value()
    q = generate_powerquery(schema, bundle, "default")["APP_Platform.pq"]

    assert "each if _ = null or List.IsEmpty(_) then null" in q


def test_sql_view_gives_a_multi_value_column_nvarchar_max() -> None:
    """A joined set has no meaningful 255 bound, and SQL Server truncates a
    CAST to NVARCHAR(255) silently."""
    schema, bundle = _multi_value()
    sql = generate_sql_views(schema, bundle, "default")

    assert "CAST(t.[AuditEvents] AS NVARCHAR(MAX)) AS [AuditEvents]" in sql


def test_both_drift_audits_agree_about_a_multi_value_column() -> None:
    """The audits are built from two different lists (the M one from
    `field_internal_names`, the SQL one from `sql_columns`), and a kind that
    lands in one but not the other makes them contradict each other over the
    same deployment. A multi-value column must be expected by both."""
    schema, bundle = _multi_value()

    m_audit = generate_dictionary_powerquery(
        schema, bundle, "default",
    )["_UserAddedColumns.pq"]
    sql_audit = generate_dictionary_sql(schema, bundle, "default")

    assert '"AuditEvents"' in m_audit
    assert "(N'APP_Platform', N'AuditEvents')" in sql_audit


def test_dictionary_describes_a_multi_value_column_in_human_words() -> None:
    """`MultiChoice` is this codebase's internal token for FieldTypeKind 15.
    The dictionary is read by report authors, so it says what the column is
    and how the export spells a set."""
    schema, bundle = _multi_value()
    md = generate_data_dictionary(schema, bundle, "default")

    assert "Choice (multiple): 1. View, 2. Edit, 3. Permission change" in md
    assert '"; "' in md
    assert "MultiChoice" not in md


def test_display_names_still_reach_a_multi_value_column() -> None:
    """The joined column is not in `m_types`, which is where every other
    renameable output name comes from, so without an explicit entry the one
    column type this stage added would be the one that never got its display
    title, and only a reader comparing two report pages would ever notice."""
    schema, bundle = _multi_value(display_names=True)
    q = generate_powerquery(schema, bundle, "default")["APP_Platform.pq"]

    assert '{"AuditEvents", "Audit Events"}' in q


def test_reporting_md_states_the_multi_value_landing_contract() -> None:
    """The two targets do different things and the page has to say so.

    Power Query joins the set in a step this generator writes. The SQL views
    only `CAST` whatever the extract landed -- this module never sees that
    process, so it cannot join anything there. A page that said the members
    "are joined by" the separator would be describing, to a warehouse
    reader, a transform no part of their path performs.
    """
    schema, bundle = _multi_value()
    md = generate_reporting_md(schema, bundle, "default")

    assert "Multi-value choice columns are a landing contract" in md
    assert "land such a column as text" in md


def _ambiguous() -> tuple[Schema, MappingBundle]:
    """A member carrying the separator the joined cell is split on.

    `{"Permission change; revoked"}` and `{"Permission change", "revoked"}`
    both join to the same string, so the export is lossy and no reader --
    human or `Text.Split` -- can tell which the row held.
    """
    schema = make_schema(
        make_table(
            "Platform",
            column("Title", required=True),
            column("AuditEvents", "audit_event[]"),
        ),
        enums=[make_enum("audit_event", "View", "Permission change; revoked")],
    )
    return schema, make_bundle(entities=["Platform"])


@pytest.mark.parametrize("generate", [
    generate_powerquery,
    generate_sql_views,
    generate_dictionary_powerquery,
    generate_dictionary_sql,
    generate_data_dictionary,
])
def test_a_member_containing_the_separator_is_refused(
    generate: object,
) -> None:
    """Every entry point, because the export is lossy at all of them.

    A joined cell is only reconstructible while no member contains the
    string it is split on. This one does, so `{"Permission change; revoked"}`
    and `{"Permission change", "revoked"}` land as the same text and a
    downstream count of selections is wrong with nothing to notice it --
    the silent-wrongness failure this repository exists to close, in a
    production export.

    Refused rather than escaped: an escape would have to be understood by
    every consumer of the cell, including a human reading it, and the
    dictionary's advice is `Text.Split`. Naming the member is the whole
    value of the error, so it is asserted.
    """
    schema, bundle = _ambiguous()

    with pytest.raises(ValueError, match="AuditEvents") as err:
        generate(schema, bundle, "default")  # type: ignore[operator]

    assert "Permission change; revoked" in str(err.value)
    assert '"; "' in str(err.value)


def test_a_member_containing_only_a_bare_semicolon_is_allowed() -> None:
    """The separator is `"; "`, and only that string makes a cell ambiguous.

    Refusing every semicolon would refuse `"Approved;pending review"`, which
    joins and splits back perfectly well. A guard stronger than the fault it
    guards against costs a legitimate schema for nothing.
    """
    schema = make_schema(
        make_table(
            "Platform",
            column("Title", required=True),
            column("AuditEvents", "audit_event[]"),
        ),
        enums=[make_enum("audit_event", "View", "Approved;pending")],
    )
    bundle = make_bundle(entities=["Platform"])

    q = generate_powerquery(schema, bundle, "default")["APP_Platform.pq"]

    assert 'Text.Combine(_, "; ")' in q


# --- An EMPTY list must not fail every query (measured 2026-08-11) -----------
#
# An operator refreshed a freshly deployed, ZERO-ROW list and the query died
# at the expand step with `Expression.Error: The column 'Owner' of the table
# wasn't found`. Adding one row made the same query work.
#
# Which matters far more than it looks: a fresh deploy produces EMPTY lists,
# so that is the FIRST refresh every adopter runs, on every person and lookup
# column, across every shipped family -- and the error names a column, so
# it reads as a broken query rather than an empty table. It then fixes itself
# the moment somebody adds a row, which is why no environment that already
# has data can see it.

# Parsed rather than string-matched, because the property is a RELATION
# between three lines: the guard must test the same source column, off the
# same previous step, that the expand reads, and the fallback must produce
# the same output column. A guard copied from the neighbouring expand and
# left unadjusted satisfies every string-presence check ever written.
_EXPAND = re.compile(
    r'Table\.ExpandRecordColumn\((?P<prev>\w+), "(?P<col>[^"]+)", '
    r'\{"(?P<inner>[^"]+)"\}, \{"(?P<out>[^"]+)"\}\)',
)
_GUARD = re.compile(
    r'if List\.Contains\(Table\.ColumnNames\((?P<prev>\w+)\), "(?P<col>[^"]+)"\)',
)
_FALLBACK = re.compile(
    r'else Table\.AddColumn\((?P<prev>\w+), "(?P<out>[^"]+)", each null, '
    r"(?P<type>[^)]+)\)",
)


def _expanding() -> tuple[Schema, MappingBundle]:
    """A schema reaching ALL THREE places `_build_plans` appends an expand.

    `record_expands` is fed from three separate arms -- person, lookup and
    hyperlink -- so a fixture carrying only a lookup would leave two of them
    free to regress while the suite stayed green.
    """
    schema = make_schema(
        make_table("Project", column("Title", required=True)),
        make_table(
            "Task",
            column("Title", required=True),
            person("Owner"),
            make_ref("Project", "Project.Id"),
            column("Evidence", "hyperlink"),
        ),
    )
    return schema, make_bundle(entities=["Project", "Task"])


def _unguarded_expands(query: str) -> list[str]:
    """Expand steps with no guard, or a guard that does not match them."""
    lines = _code_lines(query)
    offenders = []
    for i, line in enumerate(lines):
        expand = _EXPAND.search(line)
        if expand is None:
            continue
        guard = _GUARD.search(lines[i - 1]) if i else None
        fallback = _FALLBACK.search(lines[i + 1]) if i + 1 < len(lines) else None
        if (
            guard is None
            or fallback is None
            or (guard["prev"], guard["col"]) != (expand["prev"], expand["col"])
            or (fallback["prev"], fallback["out"]) != (expand["prev"], expand["out"])
        ):
            offenders.append(line.strip())
    return offenders


def test_every_record_expand_survives_the_source_column_being_absent() -> None:
    """The regression worth pinning, written as an invariant.

    Not "the Owner expand is guarded" -- `_build_plans` appends to
    `record_expands` from three different arms, and a fourth (or a change to
    one of these) is exactly how an unguarded expand gets back in. So: NO
    generated query, anywhere in the pack, may expand a record column
    without a matching guard.
    """
    schema, bundle = _expanding()
    queries = _all_powerquery(schema, bundle)
    # Named, so a selection that quietly emptied could not pass vacuously.
    assert set(queries) == {
        "APP_Project.pq", "APP_Task.pq",
        "_DataDictionary.pq", "_ModelInfo.pq", "_UserAddedColumns.pq",
    }
    for name, query in queries.items():
        assert _unguarded_expands(query) == [], name


def test_the_guard_check_sees_all_three_kinds_of_expand() -> None:
    """The invariant above is worthless over a query with no expands in it.

    Person, lookup and hyperlink are three separate arms of `_build_plans`,
    and this is what says the fixture actually reaches all three -- so
    "every expand is guarded" is a statement about three of them.
    """
    schema, bundle = _expanding()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    # DBML column order: the person, then the lookup, then the hyperlink.
    assert [m["col"] for m in _EXPAND.finditer(task)] == [
        "Owner", "Project", "Evidence",
    ]
    assert [m["out"] for m in _EXPAND.finditer(task)] == [
        "OwnerTitle", "ProjectTitle", "EvidenceUrl",
    ]


def test_the_expand_guard_check_can_actually_fail() -> None:
    """A checker that can never fail is indistinguishable from a clean pack.

    So run it over queries with the defect deliberately reintroduced: the
    guard removed entirely, and -- the subtler one -- a guard left in place
    but naming a different column from the expand beside it.
    """
    schema, bundle = _expanding()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert _unguarded_expands(task) == []

    # The 2026-08-11 defect, put back: bare expands, no guard, no fallback.
    bare = re.sub(
        r" *if List\.Contains\([^\n]*\n"
        r" *then (Table\.ExpandRecordColumn\([^\n]*\))\n"
        r" *else Table\.AddColumn\([^\n]*",
        r"        \1,",
        task,
    )
    assert len(_unguarded_expands(bare)) == 3

    # A guard that does not guard THIS expand -- copied and not adjusted.
    mismatched = task.replace(
        'Table.ColumnNames(Source), "Owner"',
        'Table.ColumnNames(Source), "Project"',
    )
    assert _unguarded_expands(mismatched) != []


def test_a_guarded_expand_still_produces_what_the_rest_of_the_query_needs() -> None:
    """Skipping the step would have been the one-line fix, and wrong.

    `Table.TransformColumnTypes` and the model-facing rename both name these
    output columns; a query missing one fails at the NEXT step instead, with
    the same class of error. So the fallback must add the column, with the
    same type the typing step is about to ascribe to it.
    """
    schema, _ = _expanding()
    bundle = make_bundle(entities=["Project", "Task"], display_name_mode="auto")
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]

    fallbacks = {m["out"]: m["type"] for m in _FALLBACK.finditer(task)}
    assert set(fallbacks) == {"EvidenceUrl", "OwnerTitle", "ProjectTitle"}
    renamed = task.split("RenamedForModel = Table.RenameColumns(")[1]
    for out, m_type in fallbacks.items():
        # The typing step names it, with the type the fallback ascribed...
        assert f'{{"{out}", {m_type}}}' in task, out
        # ...and so does the rename, which would otherwise be the second
        # place an absent column takes the refresh down.
        assert f'{{"{out}", ' in renamed, out


def test_the_empty_list_run_is_recorded_where_the_guard_lives() -> None:
    """A bare `List.Contains(Table.ColumnNames(...))` reads as defensive
    clutter to the next person, who deletes it and reopens a failure that
    only ever shows up on somebody else's first refresh."""
    schema, bundle = _expanding()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert "2026-08-11" in task
    assert "wasn't found" in task


# --- System columns: Created By, Created, Modified By, Modified -------------
#
# Opt-in through `reporting.system_columns`. They ride the same arms as a
# declared person or date-time column, and the names come from the deploy
# side's SYSTEM_COLUMN_TYPES so the two sides cannot disagree about which
# system columns exist.


def _system_columns_on(*, display_names: bool = False) -> tuple[Schema, MappingBundle]:
    from dbml_sharepoint.model.mapping_types import ReportingOptions

    schema, _ = _expanding()
    bundle = make_bundle(
        entities=["Project", "Task"],
        display_name_mode="auto" if display_names else None,
        reporting=ReportingOptions(system_columns=True),
    )
    return schema, bundle


def test_system_columns_are_off_unless_the_mapping_asks() -> None:
    schema, bundle = _expanding()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert "AuthorId" not in task
    assert "Editor" not in task
    assert '{"Created", ' not in task
    sql = generate_sql_views(schema, bundle, "default")
    assert "[Author]" not in sql
    assert "[Modified]" not in sql


def test_system_columns_ride_the_person_and_datetime_arms() -> None:
    schema, bundle = _system_columns_on()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    # After the schema's own columns, in the order Created By, Created,
    # Modified By, Modified.
    assert ',AuthorId,Author/Title,Created,EditorId,Editor/Title,Modified"' in task
    assert ',Author,Editor"' in task
    for typed in (
        '{"AuthorId", Int64.Type}', '{"AuthorTitle", type text}',
        '{"Created", type datetimezone}',
        '{"EditorId", Int64.Type}', '{"EditorTitle", type text}',
        '{"Modified", type datetimezone}',
    ):
        assert typed in task, typed
    # The display titles come through the same empty-list-safe expansion as
    # a declared person column, fallback included.
    for record_col, out in (("Author", "AuthorTitle"), ("Editor", "EditorTitle")):
        assert f'"{record_col}", {{"Title"}}, {{"{out}"}})' in task, out
        assert f'"{out}", each null, type text' in task, out


def test_system_columns_take_sharepoint_display_titles_for_the_model() -> None:
    schema, bundle = _system_columns_on(display_names=True)
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    renamed = task.split("RenamedForModel = Table.RenameColumns(")[1]
    for internal, display in (
        ("AuthorId", "Created By Id"), ("AuthorTitle", "Created By Title"),
        ("EditorId", "Modified By Id"), ("EditorTitle", "Modified By Title"),
    ):
        assert f'{{"{internal}", "{display}"}}' in renamed, internal
    # Never the auto-split of the internal name...
    assert '"Author Id"' not in renamed
    assert '"Editor Title"' not in renamed
    # ...and Created and Modified already are their display titles.
    assert '{"Created", ' not in renamed
    assert '{"Modified", ' not in renamed


def test_system_columns_land_in_the_sql_view_and_its_audit() -> None:
    schema, bundle = _system_columns_on()
    sql = generate_sql_views(schema, bundle, "default")
    for expected in (
        "CAST(t.[Author] AS NVARCHAR(255)) AS [Author]",
        "CAST(t.[Created] AS DATETIMEOFFSET) AS [Created]",
        "CAST(t.[Editor] AS NVARCHAR(255)) AS [Editor]",
        "CAST(t.[Modified] AS DATETIMEOFFSET) AS [Modified]",
    ):
        assert expected in sql, expected
    # A landed system column is expected, not drift.
    audit = generate_dictionary_sql(schema, bundle, "default")
    for name in ("Author", "Created", "Editor", "Modified"):
        assert f"(N'APP_Task', N'{name}')" in audit, name


def test_system_columns_are_in_the_dictionary_when_on() -> None:
    schema, bundle = _system_columns_on()
    md = generate_data_dictionary(schema, bundle, "default")
    for row in (
        "| Author | Person (system: Created By) |",
        "| Created | Date and time (system) |",
        "| Editor | Person (system: Modified By) |",
        "| Modified | Date and time (system) |",
    ):
        assert row in md, row
    schema, bundle = _expanding()
    assert "(system" not in generate_data_dictionary(schema, bundle, "default")


def test_the_guide_names_the_system_columns_and_their_landing_contract() -> None:
    schema, bundle = _system_columns_on()
    md = generate_reporting_md(schema, bundle, "default")
    assert "`reporting.system_columns`" in md
    assert "`Author`, `Editor`, `Created` and `Modified`" in md
    schema, bundle = _expanding()
    assert "system_columns" not in generate_reporting_md(schema, bundle, "default")


def test_the_system_column_list_is_the_deploy_side_fact() -> None:
    """One list of system columns, owned by `analysis/column_projection`.
    A second copy here is the two sides disagreeing about which columns a
    list has, which is the split the shared module exists to prevent."""
    from dbml_sharepoint.analysis.column_projection import SYSTEM_COLUMN_TYPES
    from dbml_sharepoint.analysis.report_columns import REPORT_SYSTEM_COLUMNS

    assert set(REPORT_SYSTEM_COLUMNS) == set(SYSTEM_COLUMN_TYPES) - {"ID"}


# --- The users dimension --------------------------------------------------
#
# Opt-in through `reporting.users_table`: one `_Users.pq` over the site's user
# information list, and a `... Key` on every person column that joins it.
#
# MEASURED 2026-09-02 on a live tenant, read by a site admin: the list is
# readable at /_api/web/siteuserinfolist, every field named below exists on
# it (133 fields in all), a real person column's ids resolve to its rows with
# the same Title, and ContentTypeId starts 0x010A for a person, 0x010B for a
# SharePoint group and 0x010C for a domain group. A reader-tier account was
# NOT measured.

_USERS_SELECT = (
    "$select=Id,Title,EMail,UserName,Department,JobTitle,Office,Deleted,ContentTypeId"
)


def _users_on(*, system_columns: bool = False) -> tuple[Schema, MappingBundle]:
    from dbml_sharepoint.model.mapping_types import ReportingOptions

    schema, _ = _expanding()
    bundle = make_bundle(
        entities=["Project", "Task"],
        reporting=ReportingOptions(
            users_table=True, system_columns=system_columns,
        ),
    )
    return schema, bundle


def test_the_users_table_is_off_unless_the_mapping_asks() -> None:
    schema, bundle = _expanding()
    queries = generate_powerquery(schema, bundle, "default")
    assert "_Users.pq" not in queries
    assert '"Owner Key"' not in queries["APP_Task.pq"]
    assert "_Users" not in generate_reporting_md(schema, bundle, "default")
    assert "_Users" not in generate_data_dictionary(schema, bundle, "default")


def test_the_users_query_reads_the_site_user_list_keyed_like_every_table() -> None:
    schema, bundle = _users_on()
    users = generate_powerquery(schema, bundle, "default")["_Users.pq"]
    assert 'SiteRoot & "/_api/web/siteuserinfolist/items"' in users
    assert _USERS_SELECT in users
    for typed in (
        '{"Id", Int64.Type}', '{"Title", type text}', '{"EMail", type text}',
        '{"Department", type text}', '{"Deleted", type logical}',
        '{"ContentTypeId", type text}',
    ):
        assert typed in users, typed
    # The same key shape as every list table, namespaced so it can never
    # collide with a list's own key.
    assert _added_column_expression(users, "User Key") == (
        'each SiteRoot & "|" & "_Users" & "|" & Number.ToText([Id])'
    )
    # Which kind of principal a row is: groups sit in the same list.
    kind = _added_column_expression(users, "Principal Kind")
    for prefix, label in (
        ("0x010A", "Person"), ("0x010B", "SharePoint group"), ("0x010C", "Domain group"),
    ):
        assert f'Text.StartsWith([ContentTypeId], "{prefix}") then "{label}"' in kind, label
    assert "[ContentTypeId] = null" in kind
    # Site provenance, so appended sites slice like the list tables do.
    assert '"Site Url", each SiteRoot, type text' in users
    assert '"Site Name", each SiteName, type text' in users
    # Only the declared columns go on; SharePoint adds `ID` beside `Id`.
    assert "Table.SelectColumns(" in users
    # Model-facing names, always: there is no schema to keep internal names for.
    for internal, display in (
        ("Title", "Name"), ("EMail", "Email"), ("UserName", "Account"),
        ("JobTitle", "Job Title"),
    ):
        assert f'{{"{internal}", "{display}"}}' in users, internal
    assert "2026-09-02" in users
    assert "siteuserinfolist" in users.split("let")[0], "the header names the source"


def test_person_columns_carry_a_key_that_joins_the_users_table() -> None:
    schema, bundle = _users_on(system_columns=True)
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert _added_column_expression(task, "Owner Key") == (
        "each if [OwnerId] = null then null "
        'else SiteRoot & "|" & "_Users" & "|" & Number.ToText([OwnerId])'
    )
    # The system person columns get keys under their display titles.
    assert _added_column_expression(task, "Created By Key") == (
        "each if [AuthorId] = null then null "
        'else SiteRoot & "|" & "_Users" & "|" & Number.ToText([AuthorId])'
    )
    assert '"Modified By Key"' in task
    # Never renamed: they are already model-facing.
    renamed = (
        task.split("RenamedForModel = Table.RenameColumns(")[1]
        if "RenamedForModel" in task else ""
    )
    assert '"Owner Key"' not in renamed


def test_the_guide_lists_every_person_relationship_and_the_one_active_rule() -> None:
    schema, bundle = _users_on(system_columns=True)
    md = generate_reporting_md(schema, bundle, "default")
    assert "| APP_Task | Owner Key | _Users | User Key |" in md
    assert "| APP_Task | Created By Key | _Users | User Key |" in md
    assert "| APP_Project | Modified By Key | _Users | User Key |" in md
    assert "one active relationship" in md
    assert "USERELATIONSHIP" in md
    assert "Reference" in md
    assert "`reporting.users_table`" in md
    # The unmeasured part is said, not assumed.
    assert "reader" in md.lower() and "403" in md


def test_the_users_table_is_in_the_dictionary() -> None:
    schema, bundle = _users_on()
    md = generate_data_dictionary(schema, bundle, "default")
    assert "## _Users" in md
    for name in (
        "Name", "Email", "Account", "Department", "Job Title", "Office",
        "Deleted", "Principal Kind", "User Key",
    ):
        assert f"| {name} |" in md, name
    rows = generate_dictionary_powerquery(schema, bundle, "default")["_DataDictionary.pq"]
    assert '"_Users"' in rows


# --- The row key must name the LIST, not only the site ----------------------
#
# Measured 2026-08-11: the key was `SiteRoot & "|" & Number.ToText([Id])`,
# with nothing in it identifying the list. Every SharePoint list numbers its
# items from 1, so appending two lists that share a site produces colliding
# keys -- silently. Wrong row counts and wrong relationships, no error
# anywhere, in exactly the multi-site/multi-list append the generated guide
# tells the operator to build.


def _added_column_expression(query: str, column_name: str) -> str:
    """The `each …` generator of the `Table.AddColumn` step producing
    `column_name`, as one whitespace-normalised string.

    Located by the COLUMN name rather than the step name: the step names are
    an internal detail, and pinning them would make this find nothing (and
    return an empty string, which compares equal to nothing useful) after a
    harmless rename. Raises when no such column is added, so a deleted
    column cannot read as an empty expression.
    """
    lines = _code_lines(query)
    for i, line in enumerate(lines):
        if not line.rstrip().endswith(f'"{column_name}",'):
            continue
        expression: list[str] = []
        for rest in lines[i + 1:]:
            if rest.strip() == "type text":
                # The step's own trailing comma is punctuation, not part of
                # the expression -- and it differs between the last step of a
                # query and every other, which would make two otherwise
                # identical keys compare unequal.
                return " ".join(expression).rstrip(",")
            expression.append(rest.strip())
    raise AssertionError(f"no Table.AddColumn step produces {column_name!r}")


def test_the_added_column_reader_finds_the_expression_and_not_a_blank() -> None:
    """The tests below compare expressions for equality, so a reader that
    returned "" for everything would make them agree about nothing."""
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert _added_column_expression(task, "ItemURL").startswith("each SiteRoot &")
    with pytest.raises(AssertionError, match="Absent Key"):
        _added_column_expression(task, "Absent Key")


def test_the_row_key_names_the_list_it_came_from() -> None:
    """Site + id alone collides across two lists on ONE site.

    Asserted as the whole expression rather than "the title appears
    somewhere": the list title is also in the `getbytitle` endpoint and in
    the `List Title` column, so a substring check would keep passing over a
    key that had reverted.
    """
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert _added_column_expression(task, "Task Key") == (
        'each SiteRoot & "|" & "APP_Task" & "|" & Number.ToText([Id])'
    )
    # The defect, spelled out, so a revert cannot pass this file.
    assert 'each SiteRoot & "|" & Number.ToText([Id])' not in task


def test_two_lists_in_one_pack_do_not_share_a_row_key_expression() -> None:
    """The collision itself, not a proxy for it.

    Both lists live on one site and both number their items from 1, so
    equal key EXPRESSIONS mean equal keys on equal ids -- which is what
    silently merges two tables when they are appended.
    """
    schema, bundle = _simple()
    queries = generate_powerquery(schema, bundle, "default")
    keys = {
        f"{entity} Key": _added_column_expression(
            queries[f"APP_{entity}.pq"], f"{entity} Key",
        )
        for entity in ("Project", "Task", "AppSettings")
    }
    assert len(set(keys.values())) == len(keys), keys


def test_a_lookup_key_is_spelled_the_way_its_target_spells_its_own() -> None:
    """The half of the change that is easy to get wrong and impossible to see.

    `Project Key` on APP_Task is joined against `Project Key` on
    APP_Project. Put THIS list's title in the foreign key -- the obvious
    slip, since every other literal in the query is this list's -- and the
    two sides never match: the relationship resolves to nothing, and Power
    BI renders blank visuals rather than raising.
    """
    schema, bundle = _simple()
    queries = generate_powerquery(schema, bundle, "default")
    target_key = _added_column_expression(queries["APP_Project.pq"], "Project Key")
    fk = _added_column_expression(queries["APP_Task.pq"], "Project Key")
    # Same format, same list title, the FK column in place of [Id] -- plus
    # the null guard, which a table's own key does not need.
    assert fk == (
        "each if [ProjectId] = null then null else "
        + target_key.removeprefix("each ").replace("[Id]", "[ProjectId]")
    )
    assert '"APP_Project"' in fk
    assert '"APP_Task"' not in fk


def test_every_list_query_carries_the_list_it_came_from() -> None:
    """`Site Url`/`Site Name` let an appended model slice by site; without
    this it cannot slice by LIST, and the key that now distinguishes them is
    opaque text nobody would slice on."""
    schema, bundle = _simple()
    for name, query in generate_powerquery(schema, bundle, "default").items():
        list_title = name.removesuffix(".pq")
        assert _added_column_expression(query, "List Title") == (
            f'each "{list_title}"'
        )


def test_the_list_title_column_is_not_renamed_for_the_model() -> None:
    """Consistently with `Site Url` and `Site Name`, which it sits beside:
    those three are already model-facing names, and putting one of them
    through the display-name rename would give an appended model two
    differently-spelled slicers for the same fact."""
    schema, bundle = _simple()
    project = generate_powerquery(schema, bundle, "default")["APP_Project.pq"]
    assert "RenamedForModel = Table.RenameColumns(" in project  # not vacuous
    renamed = project.split("RenamedForModel = Table.RenameColumns(")[1]
    for column_name in ("List Title", "Site Url", "Site Name", "Project Key"):
        assert f'{{"{column_name}", ' not in renamed, column_name


def test_the_guide_says_what_the_key_is_made_of() -> None:
    """The guide is where a report author decides what to join on. One that
    still says "`Site Url` and the id" describes a key that no longer
    exists, and the mismatch surfaces as a relationship that silently
    matches nothing."""
    schema, bundle = _simple()
    md = generate_reporting_md(schema, bundle, "default")
    assert "**`List Title`**" in md
    assert "**list title**" in md


# --- Only the declared columns reach the model ------------------------------
#
# MEASURED 2026-09-02 on a live tenant, at the Source step of a generated
# query in Power BI Desktop: `/items?$select=Id,...` answers with an uppercase
# `ID` beside the `Id` that was asked for, identical on every row. No step
# removed it, Power Query keeps both because its column names are
# case-sensitive, and the Power BI model, whose names are not, loaded the
# second one as "ID 2" in every list table of a production report.

_TYPING_STEP = re.compile(
    r"(?P<step>\w+) = Table\.TransformColumnTypes\(\s*\w+,\s*\{(?P<body>.*?)\n\s*\}\s*\)",
    re.DOTALL,
)
_SELECT_STEP = re.compile(
    r"(?P<step>\w+) = Table\.SelectColumns\(\s*(?P<prev>\w+),\s*\{(?P<body>[^}]*)\}",
)


def _typed_columns(query: str) -> list[str]:
    typed = _TYPING_STEP.search(query)
    assert typed is not None, "no typing step"
    return re.findall(r'\{"([^"]+)",', typed["body"])


def test_powerquery_keeps_exactly_the_typed_columns_after_typing() -> None:
    """Anything SharePoint adds unasked rides through every later step, so the
    declared set is selected right after it is typed, and the next step builds
    on that selection rather than on the typing step it bypasses."""
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]

    select = _SELECT_STEP.search(task)
    assert select is not None, "no Table.SelectColumns step"
    typing = _TYPING_STEP.search(task)
    assert typing is not None
    assert select["prev"] == typing["step"]
    assert re.findall(r'"([^"]+)"', select["body"]) == _typed_columns(task)
    assert re.search(
        rf'Table\.AddColumn\(\s*{select["step"]}, "ItemURL"', task,
    ), "ItemURL is not built on the selected columns"


def test_powerquery_keeps_a_multi_value_column_through_the_selection() -> None:
    """The joined multi-value column is the one output that is NOT in the
    typing step (the join ascribes its type), so a selection built from the
    typed names alone would drop it silently: a column missing from an export
    with no error anywhere, this project's failure class."""
    schema, bundle = _multi_value()
    q = generate_powerquery(schema, bundle, "default")["APP_Platform.pq"]

    select = _SELECT_STEP.search(q)
    assert select is not None, "no Table.SelectColumns step"
    kept = re.findall(r'"([^"]+)"', select["body"])
    assert "AuditEvents" in kept
    assert set(kept) == set(_typed_columns(q)) | {"AuditEvents"}


def test_the_uppercase_id_run_is_recorded_where_the_selection_lives() -> None:
    """A bare `Table.SelectColumns` over the columns the query itself asked
    for reads as a no-op to the next person, who deletes it and puts "ID 2"
    back into every model."""
    schema, bundle = _simple()
    task = generate_powerquery(schema, bundle, "default")["APP_Task.pq"]
    assert "2026-09-02" in task
    assert '"ID 2"' in task
