"""The test-input builders are themselves tested.

They are about to be used by several hundred call sites. A builder that emits
subtly wrong YAML would change what all of those tests exercise while leaving
every one of them green — which is the exact failure the conversion they serve
exists to avoid.
"""

from pathlib import Path

import pytest
from _builders import ID_PK, TITLE, table
from _packs import (
    DEFAULT_TABLE_NOTE,
    blocks,
    entities,
    entity,
    pack,
    replaced,
    with_tail,
    write_dbml,
    write_mapping,
)

from dbml_sharepoint.model.parser import parse_dbml


def test_entity_emits_one_indented_line() -> None:
    assert entity("Risk") == (
        "  Risk: { kind: List, base_template: 100, site_role: default }"
    )


def test_entity_extra_keys_are_appended_in_order() -> None:
    """`display_column` is the common extra, and it must land inside the braces."""
    assert entity("Event", display_column="EventRef") == (
        "  Event: { kind: List, base_template: 100, site_role: default, "
        "display_column: EventRef }"
    )


def test_entities_emits_the_key_and_one_line_each() -> None:
    assert entities("Risk", "Event") == (
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "  Event: { kind: List, base_template: 100, site_role: default }\n"
    )


def test_table_emits_a_dbml_block() -> None:
    assert table("Risk", ID_PK, TITLE) == (
        "Table Risk {\n  Id int [pk, increment]\n  Title nvarchar [not null]\n}\n"
    )


def test_write_mapping_honours_a_custom_name(tmp_path: Path) -> None:
    """Several tests write two mappings into one tmp_path to compare them."""
    path = write_mapping(tmp_path, "entities: {}\n", name="m2.yaml")
    assert path.name == "m2.yaml"
    assert path.read_text(encoding="utf-8").startswith('prefix: "APP_"')


def test_write_mapping_can_omit_the_prefix(tmp_path: Path) -> None:
    """Enum and release side-files carry no prefix of their own."""
    path = write_mapping(tmp_path, "choices: {}\n", prefix=None)
    assert not path.read_text(encoding="utf-8").startswith("prefix:")


def test_write_dbml_honours_a_custom_name(tmp_path: Path) -> None:
    assert write_dbml(tmp_path, table("A", ID_PK), name="other.dbml").name == "other.dbml"


def test_write_dbml_gives_every_table_a_note(tmp_path: Path) -> None:
    """`ENTITY_HAS_NO_NOTE` is an error, so a fixture with no note is a fixture
    that cannot be built. Parsed back rather than string-matched: the note has
    to reach `Table.note`, which is where the rule and the emitter read it."""
    path = write_dbml(tmp_path, blocks(table("A", ID_PK), table("B", ID_PK)))
    assert [t.note for t in parse_dbml(path).tables] == [DEFAULT_TABLE_NOTE] * 2


@pytest.mark.parametrize("keyword", ["Note", "note", "NOTE"])
def test_write_dbml_leaves_a_declared_note_alone(tmp_path: Path, keyword: str) -> None:
    """A test that authored its own note is about that note.

    Parametrised over the CASE of the keyword because pydbml ignores it and a
    case-sensitive detector here would not. `note:` at the start of a line is
    a table note as surely as `Note:` is; if the detector missed it the helper
    would append its default afterwards, and pydbml takes the LAST note — so
    the fixture would read as bespoke prose in the source while `Table.note`
    held the generic sentence. Nothing would report that.
    """
    path = write_dbml(tmp_path, f"""
        Table A {{
          Id int [pk, increment]

          {keyword}: 'The one this test is about.'
        }}
    """)
    assert [t.note for t in parse_dbml(path).tables] == ["The one this test is about."]


def test_the_default_note_goes_after_an_index_block_not_inside_it(
    tmp_path: Path,
) -> None:
    """The nesting case. A table body opens braces of its own, so inserting at
    the first `}` would land the note inside `indexes { }` -- which parses, and
    leaves `Table.note` empty while the fixture looks noted."""
    path = write_dbml(tmp_path, """
        Table A {
          Id int [pk, increment]
          Code nvarchar

          indexes {
            Code
          }
        }
    """)
    table_a = parse_dbml(path).tables[0]
    assert table_a.note == DEFAULT_TABLE_NOTE
    assert [index.columns for index in table_a.indexes] == [("Code",)]


def test_notes_false_writes_the_body_verbatim(tmp_path: Path) -> None:
    """The escape the note rule's own tests need."""
    path = write_dbml(tmp_path, table("A", ID_PK), notes=False)
    assert parse_dbml(path).tables[0].note == ""
    assert "Note:" not in path.read_text(encoding="utf-8")


def test_blocks_dedents_each_part_against_its_own_margin() -> None:
    """The bug that broke 53 tests: dedenting the concatenation is a no-op."""
    assert blocks("""
        a: 1
    """, "b: 2\n") == "a: 1\nb: 2\n"


def test_blocks_drops_an_empty_part() -> None:
    assert blocks("a: 1\n", "") == "a: 1\n"


def test_entities_accepts_a_prebuilt_line_alongside_bare_names() -> None:
    """The safe way to mix a default entity with one carrying extras."""
    assert entities("Risk", entity("Event", display_column="EventRef")) == (
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "  Event: { kind: List, base_template: 100, site_role: default, "
        "display_column: EventRef }\n"
    )


def test_with_tail_leaves_the_tail_indentation_alone() -> None:
    """The tail's indentation says where it goes, so it must survive verbatim.

    This is the case `blocks()` gets wrong: it would dedent the four-space tail
    flush and reparent `views:` from under `Project` to the top level of the
    document — still valid YAML, silently a different mapping.
    """
    assert with_tail("""
        entities:
          Project:
            kind: List
    """, "    views: []\n") == (
        "entities:\n  Project:\n    kind: List\n    views: []\n"
    )


def test_with_tail_matches_blocks_when_the_tail_is_flush() -> None:
    """Where the tail is a top-level section, the two agree — the difference
    only shows up for a tail whose indent is load-bearing."""
    body = """
        entities:
          Project: {}
    """
    assert with_tail(body, "views: []\n") == blocks(body, "views: []\n")


def test_with_tail_accepts_an_absent_tail() -> None:
    assert with_tail("a: 1\n") == "a: 1\n"


def test_blocks_refuses_a_bare_entity_line() -> None:
    """`blocks(entity(...))` would unnest it to the top level of the mapping.

    `blocks` dedents each part against its own margin, and for a lone indented
    line that margin IS the indentation, so `  Risk: {...}` becomes
    `Risk: {...}` — outside the `entities:` key. YAML loads that happily and
    the mapping ends up with no entities at all: a green test asserting
    nothing. Caught by a conversion agent, not by review.
    """
    with pytest.raises(TypeError, match="unnest"):
        blocks(entity("Risk"))


def test_blocks_still_dedents_an_ordinary_source_block() -> None:
    """The guard must not disturb the normal case it sits next to."""
    assert blocks(entities("Risk"), """
        views:
          Risk: []
    """) == (
        "entities:\n"
        "  Risk: { kind: List, base_template: 100, site_role: default }\n"
        "views:\n"
        "  Risk: []\n"
    )


def test_pack_round_trips_through_the_real_loaders(tmp_path: Path) -> None:
    """The builders must produce documents the real parser and loader accept.

    Asserting on the emitted strings alone would let a builder drift into
    something that looks right and does not parse.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=table("Risk", ID_PK, TITLE),
        mapping=entities("Risk"),
    )
    assert [t.name for t in schema.tables] == ["Risk"]
    assert set(bundle.mapping.entities) == {"Risk"}


def test_replaced_returns_the_substituted_text() -> None:
    assert replaced("a\nb\n", "b", "c") == "a\nc\n"


def test_replaced_raises_when_the_needle_is_absent() -> None:
    """The whole point: a missed needle must not be a silent no-op."""
    with pytest.raises(AssertionError, match="needle not found"):
        replaced("a\nb\n", "  b: indented", "x")
