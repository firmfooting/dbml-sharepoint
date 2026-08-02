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

from pathlib import Path
from textwrap import dedent

from dbml_sharepoint.model.mapping_loader import MappingBundle, load_mapping
from dbml_sharepoint.model.parser import Schema, parse_dbml

#: Every schema in the suite starts with this and no test is about it.
DBML_PREAMBLE = "Project t { database_type: 'SharePoint Online' }"

#: Likewise the mapping prefix.
DEFAULT_PREFIX = 'prefix: "APP_"'


def _body(text: str) -> str:
    """Dedent a triple-quoted block and give it exactly one trailing newline."""
    return dedent(text).strip("\n") + "\n"


def blocks(*parts: str) -> str:
    """Dedent each part separately, then join.

    Dedenting the *concatenation* would not work: an indented literal joined to
    an already-flush fragment has no common prefix, so `dedent` becomes a no-op
    and the literal keeps its indentation. Each part has to be dedented against
    its own margin before they meet.
    """
    return "".join(_body(p) for p in parts if p.strip())


def write_dbml(tmp_path: Path, body: str, *, preamble: bool = True) -> Path:
    """Write ``s.dbml`` under `tmp_path`, prepending the Project line."""
    text = _body(body)
    if preamble:
        text = f"{DBML_PREAMBLE}\n{text}"
    path = tmp_path / "s.dbml"
    path.write_text(text, encoding="utf-8")
    return path


def write_mapping(tmp_path: Path, body: str, *, prefix: str | None = DEFAULT_PREFIX) -> Path:
    """Write ``m.yaml`` under `tmp_path`, prepending the prefix declaration."""
    text = _body(body)
    if prefix is not None:
        text = f"{prefix}\n{text}"
    path = tmp_path / "m.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def pack(
    tmp_path: Path,
    dbml: str,
    mapping: str,
    *,
    preamble: bool = True,
    prefix: str | None = DEFAULT_PREFIX,
) -> tuple[Schema, MappingBundle]:
    """Write both files and return the parsed schema and loaded bundle.

    The pair is what 178 ``parse_dbml`` and 302 ``load_mapping`` calls in this
    suite were spelling out one line at a time.
    """
    schema_path = write_dbml(tmp_path, dbml, preamble=preamble)
    mapping_path = write_mapping(tmp_path, mapping, prefix=prefix)
    return parse_dbml(schema_path), load_mapping(mapping_path)
