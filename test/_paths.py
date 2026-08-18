"""Where things are, worked out once.

The suite used to re-derive these in every file, in three different spellings
of the same idea -- `Path(__file__).parent.parent`,
`Path(__file__).resolve().parents[1]`, and fourteen separate copies of
`Path(__file__).parent / "fixtures"`. Parent-counting is silently wrong the
moment a file moves to a different depth: it does not raise, it resolves
somewhere else and the tests fail somewhere unrelated.

So the root is found by looking for the marker that actually defines it, and
raises if it is not there. Everything else hangs off that.

Two directories were both called `TEMPLATES` in different modules and are not
the same place. They are named apart here.
"""

from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent


def _repo_root() -> Path:
    """The directory holding pyproject.toml, searched upward from this file."""
    for candidate in (TEST_DIR, *TEST_DIR.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError(
        f"no pyproject.toml above {TEST_DIR} - cannot locate the repository root"
    )


REPO_ROOT = _repo_root()

#: Test data committed beside the tests.
FIXTURES = TEST_DIR / "fixtures"

#: Committed golden files: the emitted scripts, byte for byte.
EXPECTED = FIXTURES / "expected"


def write_golden(path: Path, text: str) -> None:
    """Explicit newline: the default emits CRLF on Windows, so the file reads
    as modified locally while producing an empty diff."""
    path.write_text(text, encoding="utf-8", newline="\n")


#: Live-site probes. Their transcripts are gitignored; see test_probes.py.
MANUAL = TEST_DIR / "manual"

#: The installable package.
PACKAGE = REPO_ROOT / "src" / "dbml_sharepoint"

#: The Jinja templates the generators render (``*.j2``).
JINJA_TEMPLATES = PACKAGE / "templates"

#: The shipped solution templates -- one directory per list family. NOT the
#: Jinja templates above; these are schema + mapping + release triples.
#:
#: Inside the package, not at the repository root, because the wizard offers
#: them to somebody who ran ``uvx dbml-sharepoint`` and has no checkout. Only
#: files under the package directory reach the wheel, so a solution template
#: outside it exists for contributors and for nobody else.
SOLUTION_TEMPLATES = PACKAGE / "solutions"
