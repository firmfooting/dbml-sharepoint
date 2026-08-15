"""Write a schema + mapping pair for a test, without hand-rolled newlines.

The suite's older idiom builds its inputs by concatenating string fragments
that each end in an explicit ``\\n``::

    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\\n"
        "Table Risk {\\n  Id int [pk, increment]\\n"
        "  Title nvarchar [not null]\\n}\\n",
        encoding="utf-8",
    )

Three things are wrong with that, in increasing order of seriousness:

1. It reads nothing like the file it produces, so a YAML indentation bug is
   invisible until the loader complains about something else.
2. Line boundaries drift. The fragment above puts two logical lines in one
   string, and the suite does this inconsistently.
3. It is the ISC004 hazard. Adjacent string literals concatenate silently, so
   a **missing comma** between two list items produces one joined string
   rather than an error -- the same defect class that was fixed across 45
   sites in ``src``. Here it would corrupt a test's input while the test
   still passes.

So: pass the real text, indented naturally, and let ``dedent`` handle it.

    schema, bundle = pack(
        tmp_path,
        dbml='''
            Table Risk {
              Id int [pk, increment]
              Title nvarchar [not null]
            }
        ''',
        mapping='''
            entities:
              Risk: { kind: List, base_template: 100, site_role: default }
        ''',
    )

The DBML ``Project`` line and the mapping ``prefix`` are supplied by default --
110 and 128 copies of them respectively were spread across the suite, and no
test was ever about them. Pass ``preamble=False`` or your own ``prefix`` when
the test *is* about them.
"""

import re
from pathlib import Path
from textwrap import dedent

from dbml_sharepoint.model.mapping_loader import MappingBundle, load_mapping
from dbml_sharepoint.model.parser import Schema, parse_dbml

#: Every schema in the suite starts with this and no test is about it.
#: The `Project` name the preamble declares. Named rather than inlined
#: because `_model.schema()` builds the OBJECT the parser would produce from
#: this text, and `test_model_contract` asserts the two are equal --
#: `schema.project_name` is now one of the fields compared, so a second
#: spelling of `t` would be a contract test comparing two different schemas.
PREAMBLE_PROJECT = "t"

DBML_PREAMBLE = f"Project {PREAMBLE_PROJECT} {{ database_type: 'SharePoint Online' }}"

#: Likewise the mapping prefix.
DEFAULT_PREFIX = 'prefix: "APP_"'

#: The table `Note:` a fixture table gets when it declares none.
#:
#: Same reasoning as `DBML_PREAMBLE`, and the same arithmetic. Every
#: provisioned list must describe itself -- `ENTITY_HAS_NO_NOTE` is an ERROR,
#: so a note-less table makes a schema unbuildable -- and several hundred
#: fixtures across this suite are about views, formatters, indexes and
#: retirement rather than about prose in list settings. Without a default,
#: every one of them would carry a line no test is about, and the next test
#: that asserts `errors == []` would fail for a reason unrelated to its
#: subject.
#:
#: It is supplied HERE rather than by giving `_model.table()` a default,
#: because the rule has to stay exercisable at the object level: the tests
#: that make `ENTITY_HAS_NO_NOTE` fire build a `Table` with no note and would
#: have nothing to assert if the builder invented one.
#:
#: Pass `notes=False` for a test that is about the DBML text itself.
DEFAULT_TABLE_NOTE = "Fixture list, for a test that is not about the description."

#: A `Table` header opening a block. Anchored at column zero because `_body`
#: has already dedented, and deliberately NOT matching `Enum` or `Ref`.
_TABLE_OPEN = re.compile(r"^Table\s")

#: A table-level note: at the START OF A LINE, which a column's inline
#: `[note: '...']` is not.
#:
#: CASE-INSENSITIVE, because pydbml is. A fixture authored as
#: `note: 'the specific thing this test is about'` parses as the table note
#: exactly like `Note:` does -- and when a table carries two notes, THE LAST
#: ONE WINS. So a case-sensitive detector would miss the author's note, append
#: the default after it, and hand the test `DEFAULT_TABLE_NOTE` while the
#: source still reads as bespoke prose. The test would look like it exercised
#: a particular description and would not, with nothing anywhere reporting it
#: -- the same quietly-green failure the brace counting in
#: `_with_default_notes` guards against.
_TABLE_NOTE = re.compile(r"^\s*Note\s*:", re.IGNORECASE)


def _noted(block: list[str]) -> list[str]:
    """One `Table { ... }` block, with a default `Note:` if it declares none."""
    if any(_TABLE_NOTE.match(line) for line in block):
        return block
    return [*block[:-1], f"\n  Note: '{DEFAULT_TABLE_NOTE}'\n", block[-1]]


def _with_default_notes(text: str) -> str:
    """Give every `Table` block in a DBML document a note, unless it has one.

    Brace-counted rather than regex-matched over the whole block, because a
    table body nests: `indexes { }` opens and closes braces of its own, and a
    pattern reaching for the first `}` would insert the note in the middle of
    the index list -- where DBML still parses, and the note is then attached to
    nothing anybody looks at.

    An unbalanced document is emitted UNCHANGED rather than guessed at. The
    parser is what reports a malformed fixture, and a helper that silently
    rewrote one would make its complaint point at the wrong line.
    """
    out: list[str] = []
    block: list[str] = []
    depth = 0
    for line in text.splitlines(keepends=True):
        if not block:
            if _TABLE_OPEN.match(line) and "{" in line:
                depth = line.count("{") - line.count("}")
                if depth > 0:
                    block = [line]
                    continue
            out.append(line)
            continue
        depth += line.count("{") - line.count("}")
        block.append(line)
        if depth == 0:
            out.extend(_noted(block))
            block = []
    out.extend(block)
    return "".join(out)


def _body(text: str) -> str:
    """Dedent a triple-quoted block and give it exactly one trailing newline."""
    return dedent(text).strip("\n") + "\n"


def blocks(*parts: str) -> str:
    """Dedent each part separately, then join.

    Dedenting the *concatenation* would not work: an indented literal joined to
    an already-flush fragment has no common prefix, so `dedent` becomes a no-op
    and the literal keeps its indentation. Each part has to be dedented against
    its own margin before they meet.

    Blank and whitespace-only parts are dropped rather than contributing an
    empty line, so `blocks(base, extra)` with an empty `extra` is exactly
    `blocks(base)`. That is what callers passing an optional fragment want; it
    does mean a part that is *deliberately* only whitespace cannot be expressed
    here, which no caller needs and YAML would ignore anyway.

    Passing `entity()` directly is refused -- see `_EntityLine`.
    """
    for part in parts:
        if isinstance(part, _EntityLine):
            raise TypeError(
                "blocks() dedents each part, which would unnest this entity line "
                "to the top level of the mapping. Pass it through entities() "
                "instead: entities('Risk', entity('Event', display_column='X')).",
            )
    return "".join(_body(p) for p in parts if p.strip())


def with_tail(body: str, tail: str = "") -> str:
    """Dedent `body`, then append `tail` **verbatim**.

    For the helpers that take a caller-supplied fragment whose indentation is
    SEMANTIC. `_join_inputs`' `mapping_tail` documents it plainly: *"indent it
    four spaces to add an entity key, or start at column zero to open a new
    top-level section"*. The indent is how the caller says where the fragment
    goes.

    `blocks()` is exactly wrong for those. It dedents each part against its own
    margin, so a tail indented four spaces to nest under an entity comes out
    flush and reparents to the top level of the document, silently, because
    the result is still valid YAML. One conversion agent hit this on
    `_shape_warnings`' `where` argument and left it as a fragment rather than
    risk it.

    So: the literal half gets dedented, the caller's half does not. Since
    `body` starts at column zero after dedenting, a later `_body` pass over the
    joined string is a no-op and the tail's indentation survives that too.
    """
    return _body(body) + tail


def write_dbml(
    tmp_path: Path,
    body: str,
    *,
    preamble: bool = True,
    notes: bool = True,
    name: str = "s.dbml",
) -> Path:
    """Write a schema under `tmp_path`, prepending the Project line.

    `name` is settable because a handful of tests write more than one schema in
    the same `tmp_path`, and because several already use their own filenames.

    `notes=False` writes the body verbatim, for a test about the DBML text
    itself or about a table that is meant to have no note. See
    `DEFAULT_TABLE_NOTE`.
    """
    text = _body(body)
    if notes:
        text = _with_default_notes(text)
    if preamble:
        text = f"{DBML_PREAMBLE}\n{text}"
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def write_mapping(
    tmp_path: Path,
    body: str,
    *,
    prefix: str | None = DEFAULT_PREFIX,
    name: str = "m.yaml",
) -> Path:
    """Write a mapping under `tmp_path`, prepending the prefix declaration.

    `name` matters more here than for schemas: tests that compare two mappings
    write `m.yaml` and `m2.yaml` side by side in one `tmp_path`, so collapsing
    them onto one filename would silently make the second overwrite the first.
    Counted across the suite: `m.yaml` 357, `mapping.yaml` 28, `m2.yaml` 22,
    `m3.yaml` 12, `m4.yaml` 6, `release.yaml` 6, `fixed.yaml` 4.

    `prefix=None` omits the prefix line entirely, for the enum and release
    side-files that carry no `prefix:` of their own.
    """
    text = _body(body)
    if prefix is not None:
        text = f"{prefix}\n{text}"
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def pack(
    tmp_path: Path,
    dbml: str,
    mapping: str,
    *,
    preamble: bool = True,
    notes: bool = True,
    prefix: str | None = DEFAULT_PREFIX,
    dbml_name: str = "s.dbml",
    mapping_name: str = "m.yaml",
) -> tuple[Schema, MappingBundle]:
    """Write both files and return the parsed schema and loaded bundle.

    The pair is what 178 ``parse_dbml`` and 302 ``load_mapping`` calls in this
    suite were spelling out one line at a time.
    """
    schema_path = write_dbml(
        tmp_path, dbml, preamble=preamble, notes=notes, name=dbml_name,
    )
    mapping_path = write_mapping(tmp_path, mapping, prefix=prefix, name=mapping_name)
    return parse_dbml(schema_path), load_mapping(mapping_path)


class _EntityLine(str):
    """One indented `entities:` line, whose indentation is SEMANTIC.

    A distinct type because `blocks()` dedents every part against its own
    margin, and for a lone indented line that margin is the indentation itself
    -- so `blocks(entity("Risk"))` yields `Risk: {...}` at the TOP LEVEL of the
    mapping, escaping the `entities:` key. YAML loads it happily and the
    mapping ends up with no entities at all.

    There is no way to tell that apart structurally from a triple-quoted source
    block, where dedenting is exactly right. So it is told apart by type, and
    `blocks()` refuses this one.
    """


def entity(
    name: str,
    *,
    kind: str = "List",
    base_template: int = 100,
    site_role: str = "default",
    **extra: object,
) -> _EntityLine:
    """One `entities:` line, indented two spaces, with no trailing newline.

    41 copies of the `Risk` line alone, 16 `Project`, 15 `Board`. None of the
    tests using them are about the kind or the base template.
    """
    parts = [f"kind: {kind}", f"base_template: {base_template}", f"site_role: {site_role}"]
    parts += [f"{k}: {v}" for k, v in extra.items()]
    return _EntityLine(f"  {name}: {{ {', '.join(parts)} }}")


def entities(*items: str) -> str:
    """The `entities:` key plus one line per item.

    An item is either a bare entity name, which gets the default declaration,
    or an already-built line from `entity()` for one that needs extras:

        entities("Risk", entity("Event", display_column="EventRef"))

    Combining them this way is the only safe route -- see `_EntityLine` for why
    `blocks(entity(...))` is not.
    """
    lines = [item if isinstance(item, _EntityLine) else entity(item) for item in items]
    return "entities:\n" + "".join(f"{line}\n" for line in lines)


def replaced(text: str, needle: str, replacement: str) -> str:
    """`str.replace`, but a needle that does not match is an error.

    Five tests build a variant of a schema or mapping by needle-matching a
    whole line. `str.replace` returns the input unchanged when the needle is
    absent and raises nothing, so a drifted indent -- or an edit to the fixture
    the needle was copied from -- leaves the test running against the ORIGINAL
    document and still passing.

    That is the same silent-corruption class this module's docstring describes,
    wearing a different hat, and it is the one hazard in the fragment
    conversion that a green suite cannot rule out.
    """
    assert needle in text, f"needle not found; the replacement would be a no-op: {needle!r}"
    return text.replace(needle, replacement)
