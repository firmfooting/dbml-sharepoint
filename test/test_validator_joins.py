"""Validator: the view join threshold (the LOOKUP limit, not the item count)."""
from pathlib import Path

from dbml_sharepoint.analysis.validator import (
    Finding,
    validate_against_mapping,
)
from dbml_sharepoint.model.mapping_loader import (
    MappingBundle,
    load_mapping,
)
from dbml_sharepoint.model.parser import (
    Schema,
    parse_dbml,
)

# --- View join threshold (the list view LOOKUP threshold, not the item count) ---


def _persons(count: int) -> str:
    """`count` person columns, P1..Pn — the cheapest join-bearing column."""
    return "".join(f"  P{n} person\n" for n in range(1, count + 1))

def _join_inputs(
    tmp_path: Path, columns: str, mapping_tail: str = "",
) -> tuple[Schema, MappingBundle]:
    """A Project table whose extra columns the caller supplies, so a test can
    put an exact number of join-bearing columns on it. `mapping_tail` is
    appended inside the Project entity block — indent it four spaces to add an
    entity key, or start at column zero to open a new top-level section."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Person {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Notes nvarchar\n"
        f"{columns}"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Person: { kind: List, base_template: 100, site_role: default }\n"
        "  Project:\n"
        "    kind: List\n"
        "    base_template: 100\n"
        "    site_role: default\n"
        + mapping_tail,
        encoding="utf-8",
    )
    return parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")

def _join_findings(
    schema: Schema, bundle: MappingBundle, subject: str,
) -> list[Finding]:
    """Join-threshold findings about one subject.

    Both substrings are required. 'join-bearing columns' and 'join operations'
    occur together in no other message in this codebase, so if the check is
    deleted this returns [] and every assertion below fails — while the
    unnecessary-suppression warning added in Task 5, which also says
    'join-bearing columns', is excluded because it never says 'join
    operations'."""
    return [
        f for f in validate_against_mapping(schema, bundle)
        if "join-bearing columns" in f.message
        and "join operations" in f.message
        and f.message.startswith(subject)
    ]

def _named(message: str) -> list[str]:
    """The columns a join finding NAMES, taken from its parenthesised list.

    Assert against this, never against the whole message, whenever a test cares
    whether a column name is present or absent. `_join_finding` appends a shared
    sentence reading "...including Created By (Author) and Modified By (Editor);
    Created and Modified are inferred to cost nothing...", so
    `"Created" not in f.message` and `"Author" in f.message` are BOTH vacuous —
    the first can never pass and the second passes even if the column was never
    counted. The parenthesised list is the only part of the message that varies
    with the count.

    The first "(" in every join finding opens that list: the subject prefixes
    (`views[X].Y:` and `entities[X]: the generated 'All Items' view`) use
    brackets and quotes, never parentheses."""
    return message.split("(", 1)[1].split(")", 1)[0].split(", ")

def _view_block(title: str, fields: list[str]) -> str:
    return (
        "views:\n"
        "  Project:\n"
        f"    - title: {title}\n"
        f"      fields: [{', '.join(fields)}]\n"
    )

def test_a_view_with_eight_join_columns_is_silent(tmp_path: Path) -> None:
    """Under every figure ever documented, anywhere. The subject filter matters:
    this entity's generated All Items carries 10 and is warned about separately."""
    schema, bundle = _join_inputs(
        tmp_path,
        _persons(8),
        _view_block("Wide", ["Title", *(f"P{n}" for n in range(1, 9))]),
    )
    assert _join_findings(schema, bundle, "views[Project].Wide") == []

def test_a_view_with_nine_join_columns_warns(tmp_path: Path) -> None:
    schema, bundle = _join_inputs(
        tmp_path,
        _persons(9),
        _view_block("Wide", ["Title", *(f"P{n}" for n in range(1, 10))]),
    )
    found = _join_findings(schema, bundle, "views[Project].Wide")
    assert len(found) == 1
    assert found[0].severity == "warning"
    assert "9 join-bearing columns" in found[0].message
    assert "P9" in _named(found[0].message)
    assert "Remove fields from this view." in found[0].message

def test_a_view_with_thirteen_join_columns_errors(tmp_path: Path) -> None:
    schema, bundle = _join_inputs(
        tmp_path,
        _persons(13),
        _view_block("Wide", ["Title", *(f"P{n}" for n in range(1, 14))]),
    )
    found = _join_findings(schema, bundle, "views[Project].Wide")
    assert len(found) == 1
    assert found[0].severity == "error"
    assert "13 join-bearing columns" in found[0].message
    assert "-2147024749" in found[0].message
    assert "Remove fields from this view." in found[0].message

def test_author_and_editor_each_cost_a_join_and_the_dates_cost_none(
    tmp_path: Path,
) -> None:
    """The pairing is the whole point: the same 12 columns pass, and adding one
    system PERSON column fails while adding two system DATES does not.

    Every name assertion goes through `_named`. Asserted against the whole
    message they would all be vacuous — the shared sentence `_join_finding`
    appends says "including Created By (Author) and Modified By (Editor); Created
    and Modified are inferred to cost nothing", so "Created"/"Modified"/"Author"
    are in EVERY join message regardless of what was counted."""
    twelve = [f"P{n}" for n in range(1, 13)]

    schema, bundle = _join_inputs(
        tmp_path, _persons(12),
        _view_block("Dates", ["Title", *twelve, "Created", "Modified"]),
    )
    dates = _join_findings(schema, bundle, "views[Project].Dates")
    assert len(dates) == 1
    assert dates[0].severity == "warning"
    assert "12 join-bearing columns" in dates[0].message
    assert "Created" not in _named(dates[0].message)
    assert "Modified" not in _named(dates[0].message)

    schema, bundle = _join_inputs(
        tmp_path, _persons(12), _view_block("WithAuthor", ["Title", *twelve, "Author"]),
    )
    with_author = _join_findings(schema, bundle, "views[Project].WithAuthor")
    assert len(with_author) == 1
    assert with_author[0].severity == "error"
    assert "13 join-bearing columns" in with_author[0].message
    assert "Author" in _named(with_author[0].message)

    schema, bundle = _join_inputs(
        tmp_path, _persons(12), _view_block("WithEditor", ["Title", *twelve, "Editor"]),
    )
    with_editor = _join_findings(schema, bundle, "views[Project].WithEditor")
    assert len(with_editor) == 1
    assert with_editor[0].severity == "error"
    assert "13 join-bearing columns" in with_editor[0].message
    assert "Editor" in _named(with_editor[0].message)

def test_a_real_ref_column_costs_a_join(tmp_path: Path) -> None:
    """The control for the cross-site test below. The schema is identical; the
    view must name the expanded pair rather than the column, because a cross-site
    column never exists under its own name (validator.py:145-147). The COUNT is
    what is being compared: 13 here, 12 there."""
    twelve = [f"P{n}" for n in range(1, 13)]
    schema, bundle = _join_inputs(
        tmp_path,
        _persons(12) + "  Elsewhere int [ref: > Person.Id]\n",
        _view_block("Wide", ["Title", *twelve, "Elsewhere"]),
    )
    found = _join_findings(schema, bundle, "views[Project].Wide")
    assert len(found) == 1
    assert found[0].severity == "error"
    assert "13 join-bearing columns" in found[0].message
    assert "Elsewhere" in _named(found[0].message)

def test_a_cross_site_ref_costs_no_join_in_a_view(tmp_path: Path) -> None:
    twelve = [f"P{n}" for n in range(1, 13)]
    schema, bundle = _join_inputs(
        tmp_path,
        _persons(12) + "  Elsewhere int [ref: > Person.Id]\n",
        _view_block(
            "Wide",
            ["Title", *twelve, "ElsewhereAbbreviation", "ElsewhereSiteUrl"],
        )
        + "cross_site_reference_columns:\n"
        "  - { entity: Project, column: Elsewhere }\n",
    )
    found = _join_findings(schema, bundle, "views[Project].Wide")
    assert len(found) == 1
    assert found[0].severity == "warning"
    assert "12 join-bearing columns" in found[0].message
    assert "Elsewhere" not in _named(found[0].message)

def test_a_view_declaring_a_field_set_counts_the_join_columns_it_expands_to(
    tmp_path: Path,
) -> None:
    """Sets are expanded into ViewDef.fields at load time. A view whose authored
    fields is ["@wide"] must count what @wide resolves to, not zero.

    NAMED with "join" in it on purpose. The earlier name
    `..._is_counted_on_its_expansion` contained no "join", so `-k join` never
    collected it and the step that was meant to watch it fail first ran five
    words of nothing."""
    thirteen = ", ".join(f"P{n}" for n in range(1, 14))
    schema, bundle = _join_inputs(
        tmp_path,
        _persons(13),
        "field_sets:\n"
        "  Project:\n"
        f"    wide: [{thirteen}]\n"
        "views:\n"
        "  Project:\n"
        "    - title: Wide\n"
        '      fields: [Title, "@wide"]\n',
    )
    found = _join_findings(schema, bundle, "views[Project].Wide")
    assert len(found) == 1
    assert found[0].severity == "error"
    assert "13 join-bearing columns" in found[0].message

def test_a_declared_view_counts_every_join_it_declares_even_when_hidden(
    tmp_path: Path,
) -> None:
    """`hide_from_all_items` must not reach the DECLARED-view count.

    The generator-side half of this rule is tested in test_jsgen.py; this is the
    VALIDATOR-side half, and without it a plausible 'consistency' edit — both
    derivations sit in the same entity loop, so subtracting `all_items_hidden`
    from the per-view count looks tidy — would quietly stop erroring on a view
    over 13 join columns with the whole suite still green.

    13, not 11: P1 and P2 are hidden from All Items and the declared view keeps
    them."""
    schema, bundle = _join_inputs(
        tmp_path,
        _persons(13),
        "    hide_from_all_items: [P1, P2]\n"
        + _view_block("Wide", ["Title", *(f"P{n}" for n in range(1, 14))]),
    )
    found = _join_findings(schema, bundle, "views[Project].Wide")
    assert len(found) == 1
    assert found[0].severity == "error"
    assert "13 join-bearing columns" in found[0].message
    assert "P1" in _named(found[0].message)
    assert "P2" in _named(found[0].message)

def test_the_generated_all_items_counts_author_and_editor_as_joins(
    tmp_path: Path,
) -> None:
    """11 declared join columns + Author + Editor = 13. Nothing declares this
    view — the generator appends both system columns unconditionally — so the
    message has to name all three contributions and point at the only remedy.

    All three name assertions go through `_named`. Against the whole message
    "Author" and "Editor" would pass even if SYSTEM_JOIN_COLUMNS were EMPTY and
    neither column were counted, because `_join_finding`'s shared sentence says
    "Created By (Author) and Modified By (Editor)" in every finding it makes."""
    schema, bundle = _join_inputs(tmp_path, _persons(11))
    found = _join_findings(schema, bundle, "entities[Project]")
    assert len(found) == 1
    assert found[0].severity == "error"
    assert "13 join-bearing columns" in found[0].message
    names = _named(found[0].message)
    assert "Author" in names
    assert "Editor" in names
    assert "P11" in names
    assert "hide_from_all_items" in found[0].message
    # The declared-view remedy must NOT be offered: All Items cannot be edited.
    assert "Remove fields from this view." not in found[0].message

def test_the_generated_all_items_join_count_is_silent_under_the_band(
    tmp_path: Path,
) -> None:
    """The negative case: 6 declared + Author + Editor = 8, under the band."""
    schema, bundle = _join_inputs(tmp_path, _persons(6))
    assert _join_findings(schema, bundle, "entities[Project]") == []

def test_the_generated_all_items_starts_at_two_joins(tmp_path: Path) -> None:
    """Author and Editor are 2 of the 12 before a single business column, so an
    entity's real budget for its own columns is 10. 7 declared columns is 9."""
    schema, bundle = _join_inputs(tmp_path, _persons(7))
    found = _join_findings(schema, bundle, "entities[Project]")
    assert len(found) == 1
    assert found[0].severity == "warning"
    assert "9 join-bearing columns" in found[0].message

def test_hide_from_all_items_clears_the_all_items_join_error(
    tmp_path: Path,
) -> None:
    schema, bundle = _join_inputs(
        tmp_path, _persons(11), "    hide_from_all_items: [Author, Editor]\n",
    )
    found = _join_findings(schema, bundle, "entities[Project]")
    assert [f for f in found if f.severity == "error"] == []
    # 11 remain, which is inside the 9-12 band, so the warning legitimately
    # stays. The key raises the ceiling on what an ENTITY may carry; it does
    # not remove the limit on what a VIEW may render.
    assert len(found) == 1
    assert found[0].severity == "warning"
    assert "11 join-bearing columns" in found[0].message
    assert "Author" not in _named(found[0].message)
    assert "Editor" not in _named(found[0].message)

def test_hide_from_all_items_does_not_lift_the_join_ceiling(
    tmp_path: Path,
) -> None:
    """The spec's fourth validation rule, and the one an implementation can pass
    the rest of this suite while breaking: "After suppression, the >=13 error
    still applies. The key raises the ceiling on what an ENTITY may carry; it
    does not remove the limit on what a VIEW may render."

    Without this, an implementation that computed `shown_joins` on `rendered`
    only when `hidden` is empty — or that skipped the band check whenever
    `hide_from_all_items` is set — passes every other test in the plan. The
    clears-the-error test above only proves suppression can make a finding go
    away; nothing else proves INSUFFICIENT suppression still errors.

    14 persons + Author + Editor = 16; Author and Editor are hidden; 14 remain,
    which is still over 12."""
    schema, bundle = _join_inputs(
        tmp_path, _persons(14), "    hide_from_all_items: [Author, Editor]\n",
    )
    found = _join_findings(schema, bundle, "entities[Project]")
    assert len(found) == 1
    assert found[0].severity == "error"
    assert "14 join-bearing columns" in found[0].message
    assert "Author" not in _named(found[0].message)
    assert "Editor" not in _named(found[0].message)
    assert "hide_from_all_items" in found[0].message

def test_a_document_library_gets_no_all_items_join_finding(
    tmp_path: Path,
) -> None:
    """The `kind == "DocumentLibrary"` half of the loop guard, PAIRED.

    `jsgen.py:597` builds `All Items` only when the kind is not
    `DocumentLibrary`, so counting one here would refuse a schema over a view
    the generator never creates — the exact validator/generator disagreement
    this module exists to avoid. Deleting the clause must turn a test red, and
    only the pair does that: the count alone proves nothing, because the same
    13 columns are what the List case is asserted on.

    `kind: DocumentLibrary` is separately an ERROR from `_structure.py:101-111`,
    so this build is already red for another reason. That is not a licence to
    skip the guard — it is why the guard is easy to delete unnoticed."""
    library = (
        'prefix: "APP_"\n'
        "entities:\n"
        "  Person: { kind: List, base_template: 100, site_role: default }\n"
        "  Project:\n"
        "    kind: DocumentLibrary\n"
        "    base_template: 100\n"
        "    site_role: default\n"
    )
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Person {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        f"{_persons(13)}"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(library, encoding="utf-8")
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    assert _join_findings(schema, bundle, "entities[Project]") == []

    # The pair. The identical schema declared `kind: List` DOES error, so the
    # empty result above is the guard and not an accident of the fixture.
    as_list, as_list_bundle = _join_inputs(tmp_path, _persons(13))
    found = _join_findings(as_list, as_list_bundle, "entities[Project]")
    assert len(found) == 1
    assert found[0].severity == "error"
    assert "15 join-bearing columns" in found[0].message

def test_hide_from_all_items_on_a_document_library_is_refused(
    tmp_path: Path,
) -> None:
    """The refusal above the loop's `continue`, exercised for the first time in
    this file. No other test in this section supplies `hide_from_all_items` on
    an entity the loop skips, so without this the branch that answers it has
    no red/green cycle anywhere in the suite — the `_join_findings` filter
    would not even see it, since this message never says "join-bearing
    columns" or "join operations": it belongs to a different subject entirely.

    Task 5's own covering test for this branch is already green at its
    fail-first gate, by design, because Task 4 answers this key before Task 5
    exists — that is documented there, not a gap here.

    Pairs with `test_a_document_library_gets_no_all_items_join_finding` above:
    that one catches deleting the loop's `continue`, this one catches deleting
    the refusal that runs before it. Neither test alone covers the guard."""
    library = (
        'prefix: "APP_"\n'
        "entities:\n"
        "  Person: { kind: List, base_template: 100, site_role: default }\n"
        "  Project:\n"
        "    kind: DocumentLibrary\n"
        "    base_template: 100\n"
        "    site_role: default\n"
        "    hide_from_all_items: [Author]\n"
    )
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Person {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(library, encoding="utf-8")
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    found = [
        f for f in validate_against_mapping(schema, bundle)
        if f.message.startswith("entities[Project].hide_from_all_items")
    ]
    assert len(found) == 1
    assert found[0].severity == "error"

def test_a_cross_site_ref_costs_no_join_on_all_items(tmp_path: Path) -> None:
    """A cross-site column is rendered as a Choice + URL PAIR — two rendered
    columns — and still costs nothing. Paired with the control below."""
    schema, bundle = _join_inputs(
        tmp_path,
        _persons(10) + "  Elsewhere int [ref: > Person.Id]\n",
        "cross_site_reference_columns:\n"
        "  - { entity: Project, column: Elsewhere }\n",
    )
    found = _join_findings(schema, bundle, "entities[Project]")
    assert len(found) == 1
    assert found[0].severity == "warning"
    assert "12 join-bearing columns" in found[0].message

    # Control: the same column as a real ref makes it 13.
    schema, bundle = _join_inputs(
        tmp_path, _persons(10) + "  Elsewhere int [ref: > Person.Id]\n",
    )
    control = _join_findings(schema, bundle, "entities[Project]")
    assert len(control) == 1
    assert control[0].severity == "error"
    assert "13 join-bearing columns" in control[0].message

def _hide_errors(
    schema: Schema, bundle: MappingBundle, entity: str = "Project",
) -> list[str]:
    prefix = f"entities[{entity}].hide_from_all_items"
    return [
        f.message for f in validate_against_mapping(schema, bundle)
        if f.severity == "error" and f.message.startswith(prefix)
    ]

def test_hiding_a_column_all_items_does_not_render_errors(tmp_path: Path) -> None:
    """A typo must not silently do nothing."""
    schema, bundle = _join_inputs(
        tmp_path, _persons(11), "    hide_from_all_items: [Athor]\n",
    )
    msgs = _hide_errors(schema, bundle)
    assert len(msgs) == 1
    assert "'Athor'" in msgs[0]
    assert "not a column the generated 'All Items' view renders" in msgs[0]

    # Negative case: the correctly spelled column is accepted silently.
    schema, bundle = _join_inputs(
        tmp_path, _persons(11), "    hide_from_all_items: [Author]\n",
    )
    assert _hide_errors(schema, bundle) == []

# test_hiding_a_column_on_an_entity_with_no_all_items_errors is deliberately
# NOT duplicated here. Task 4's fix round already added
# test_hide_from_all_items_on_a_document_library_is_refused above, which
# exercises the identical branch — a hide_from_all_items key on a
# DocumentLibrary, refused above this loop's `continue` — and asserts exactly
# one "error" finding whose message starts with the same
# "entities[Project].hide_from_all_items" prefix. A second test asserting the
# same branch would be duplication, not coverage.


def test_hiding_a_column_that_costs_no_join_errors(tmp_path: Path) -> None:
    """All Items renders every column for a reason. The threshold is the one
    exception, not a general hide-this feature."""
    schema, bundle = _join_inputs(
        tmp_path, _persons(11), "    hide_from_all_items: [Notes]\n",
    )
    msgs = _hide_errors(schema, bundle)
    assert len(msgs) == 1
    assert "'Notes'" in msgs[0]
    assert "costs no join operation" in msgs[0]

    # Negative case: a person column on the same entity is hideable.
    schema, bundle = _join_inputs(
        tmp_path, _persons(11), "    hide_from_all_items: [P1]\n",
    )
    assert _hide_errors(schema, bundle) == []

def test_hiding_title_is_refused_as_not_join_bearing_not_as_a_typo(
    tmp_path: Path,
) -> None:
    """`hide_from_all_items: [Title]` must be refused for costing no join
    (nvarchar, not join-bearing), never reported as an unrecognised column:
    the wrong branch would send the author looking for a typo in a column
    that plainly exists.

    NOTE on what this test can and cannot pin, recorded here because it is
    not obvious from the assertions alone. `_join_inputs` declares `Title`
    as a real DBML column on `Project`, so `_rendered_columns` alone already
    puts 'Title' in `rendered` — the explicit `| {"Title"}` union inside
    `analysis/joins.py::all_items_rendered` is redundant for THIS fixture
    and this test cannot observe it being dropped. That is by design, not
    an oversight: this test pins the branch choice for an entity that DOES
    declare its own Title (a real, common case), and
    `test_hiding_an_undeclared_title_still_takes_the_not_join_bearing_branch`
    immediately below pins the case that actually exercises the union.
    """
    schema, bundle = _join_inputs(
        tmp_path, _persons(11), "    hide_from_all_items: [Title]\n",
    )
    msgs = _hide_errors(schema, bundle)
    assert len(msgs) == 1
    assert "costs no join operation" in msgs[0]
    assert "Check the spelling" not in msgs[0]

def test_hiding_an_undeclared_title_still_takes_the_not_join_bearing_branch(
    tmp_path: Path,
) -> None:
    """The fixture `_join_inputs` builds cannot pin this — see the NOTE on
    `test_hiding_title_is_refused_as_not_join_bearing_not_as_a_typo` above.
    This entity's DBML declares NO `Title` column at all, which is legal:
    SharePoint's base-template `Title` exists on every provisioned list
    regardless of whether the schema names it. So 'Title' reaches
    `all_items_rendered`'s result ONLY through its `| {"Title"}` union —
    `_rendered_columns` alone has nothing to contribute for a column that
    is not in `table.columns`. `hide_from_all_items: [Title]` must still be
    refused for costing no join, not reported as an unrecognised column."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Notes nvarchar\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Project:\n"
        "    kind: List\n"
        "    base_template: 100\n"
        "    site_role: default\n"
        "    hide_from_all_items: [Title]\n",
        encoding="utf-8",
    )
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    msgs = _hide_errors(schema, bundle)
    assert len(msgs) == 1
    assert "costs no join operation" in msgs[0]
    assert "Check the spelling" not in msgs[0]

def test_hiding_a_cross_site_ref_errors(tmp_path: Path) -> None:
    """It is a `ref` in DBML but expands to Choice + URL, so it costs no join
    and hiding it buys nothing."""
    columns = _persons(11) + "  Elsewhere int [ref: > Person.Id]\n"
    schema, bundle = _join_inputs(
        tmp_path,
        columns,
        "    hide_from_all_items: [Elsewhere]\n"
        "cross_site_reference_columns:\n"
        "  - { entity: Project, column: Elsewhere }\n",
    )
    msgs = _hide_errors(schema, bundle)
    assert len(msgs) == 1
    assert "'Elsewhere'" in msgs[0]
    assert "is a cross-site reference" in msgs[0]

    # Negative case: the identical column, hidden identically, is fine once it
    # is a real Lookup. Only the cross_site_reference_columns entry differs.
    schema, bundle = _join_inputs(
        tmp_path, columns, "    hide_from_all_items: [Elsewhere]\n",
    )
    assert _hide_errors(schema, bundle) == []

def _unnecessary_hide_warnings(schema: Schema, bundle: MappingBundle) -> list[str]:
    return [
        f.message for f in validate_against_mapping(schema, bundle)
        if f.severity == "warning" and "hide_from_all_items is set, but" in f.message
    ]

def test_unnecessary_hide_from_all_items_warns(tmp_path: Path) -> None:
    """Mirrors the pointless-acceptance warning already shipped for
    accept_unindexable_display_column.

    THREE cases, because the condition is a band boundary at 12/13 and the
    boundary is where it breaks. Written `< JOIN_LIMIT` instead of `<=`, the
    check silently stops nagging the entity that most deserves it — 12
    unsuppressed joins with the key set for nothing — and a suite that only
    exercised 4 and 13 would stay green through it."""
    # Well inside: P1, P2, Author, Editor with nothing hidden.
    schema, bundle = _join_inputs(
        tmp_path, _persons(2), "    hide_from_all_items: [Author]\n",
    )
    msgs = _unnecessary_hide_warnings(schema, bundle)
    assert len(msgs) == 1
    assert "renders 4 join-bearing columns with nothing hidden" in msgs[0]
    assert "Remove it" in msgs[0]

    # ON the boundary: 10 persons + Author + Editor = 12 unsuppressed, which is
    # exactly JOIN_LIMIT, so the key was not needed and this MUST still warn.
    schema, bundle = _join_inputs(
        tmp_path, _persons(10), "    hide_from_all_items: [Author]\n",
    )
    msgs = _unnecessary_hide_warnings(schema, bundle)
    assert len(msgs) == 1
    assert "renders 12 join-bearing columns with nothing hidden" in msgs[0]

    # Negative case, one past the boundary: 11 + Author + Editor = 13
    # unsuppressed. The entity genuinely needs the key and is not nagged.
    schema, bundle = _join_inputs(
        tmp_path, _persons(11), "    hide_from_all_items: [Author, Editor]\n",
    )
    assert _unnecessary_hide_warnings(schema, bundle) == []
