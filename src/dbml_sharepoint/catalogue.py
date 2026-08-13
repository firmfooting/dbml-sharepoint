"""The shipped solution templates, as data the wizard can offer.

One `Solution` per directory under `solutions/`. Everything here is
read-only discovery: nothing in this module writes, validates or deploys.

Discovered by glob, never by roster. A hardcoded list of thirty names fails
open — a new template is simply never offered, and every test stays green
saying so. `.github/workflows/ci.yml` builds the same set the same way, and
`test_template_standard.py` derives its conformance cases from it.

The directory is located the way `templating.py` locates the Jinja
templates — relative to this file, inside the installed package. That is
the whole reason the templates were moved here: the audience for the wizard
is somebody who ran `uvx dbml-sharepoint` and has no checkout.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

#: One directory per list family. Not `templates/`, which is Jinja.
SOLUTIONS_DIR = Path(__file__).parent / "solutions"

#: The three files every family ships, relative to its own directory. The
#: family standard requires all three; `test_template_standard.py` enforces
#: it, so a family missing one is a bug in the template, not a case to
#: tolerate here.
SCHEMA_RELPATH = Path("10-design") / "schema.dbml"
MAPPING_RELPATH = Path("20-configure") / "mapping.yaml"
RELEASE_RELPATH = Path("20-configure") / "release.yaml"

#: How every shipped family spells "the site you are deploying to" in its
#: documentation, so the wizard can repoint it at the site the operator
#: actually chose.
#:
#: A constant, and substituted literally, because not every SharePoint URL in
#: a template means the deploy target: credentialing-register's deploy.md
#: links a by-laws page on a governance site, and several mappings carry
#: example.sharepoint.com document links in their demo rows. Rewriting
#: anything URL-shaped would repoint those at the deploy target and invent
#: dead links. `test_every_deploy_doc_spells_the_site_url_placeholder_the_same_way`
#: pays the matching cost of a literal by keeping the templates uniform.
PLACEHOLDER_SITE_URL = "https://yourtenant.sharepoint.com/sites/your-site"

#: Files at the top of `solutions/` that document the collection rather than
#: being one of its members.
_NOT_A_SOLUTION = {"README.md", "healthcare.md"}

_SUMMARY_MAX = 140

#: ASCII, because the summary is rendered into the wizard's terminal table and
#: a Windows console code page cannot encode U+2026. See
#: `test_messages_bound_for_a_console_are_ascii`.
_ELLIPSIS = "..."


class UnknownSolutionError(LookupError):
    """Named solution does not exist. Carries the available names.

    A `LookupError` rather than a bare `ValueError` so a caller can
    distinguish "no such template" from "this template is malformed", which
    fail in completely different ways and want different messages.
    """

    def __init__(self, name: str, available: list[str]) -> None:
        self.name = name
        self.available = available
        super().__init__(
            f"unknown solution template {name!r}. Available: "
            f"{', '.join(available) or '(none)'}",
        )


@dataclass(frozen=True)
class Solution:
    """One shipped list family.

    Frozen because the catalogue is read once and handed to a UI; nothing
    downstream has any business editing a template's identity.
    """

    id: str
    title: str
    summary: str
    #: The same sentence as `summary`, uncapped. `summary` is bound for a
    #: table cell and `detail` for a Panel; they differ only in length.
    detail: str
    lists: tuple[str, ...]
    prefix: str
    root: Path

    @property
    def schema_path(self) -> Path:
        return self.root / SCHEMA_RELPATH

    @property
    def mapping_path(self) -> Path:
        return self.root / MAPPING_RELPATH

    @property
    def release_path(self) -> Path:
        return self.root / RELEASE_RELPATH


#: Typographic characters a README may use, and their terminal spellings.
#:
#: The READMEs are documentation read in a browser and they use real
#: punctuation; that is house style and should stay. But the wizard renders
#: the title and summary into a TERMINAL, where the encoding is the console's
#: choice -- and ten of the thirty shipped families carry one of these. `→`
#: cannot be encoded by cp1252, cp850 OR cp437, so picking a template on a
#: legacy Windows console could raise `UnicodeEncodeError` from inside rich.
#:
#: Folded here rather than in the READMEs, because `_clean` already exists to
#: turn README prose into something a terminal can show -- stripping `**` and
#: backticks for exactly the same reason.
#:
#: A closed table, not a general "strip anything non-ASCII": silently mangling
#: a character nobody anticipated is how a summary comes to read `Risk 5x5
#: matri`. `test_every_catalogue_entry_is_ascii` fails on a new template that
#: introduces one, which is a build failure somebody can fix in a line.
_TERMINAL_SPELLINGS = {
    # Keyed by CODEPOINT, not by the character.
    #
    # `test_messages_bound_for_a_console_are_ascii` walks every string
    # literal in this module and checks the parsed value, so `"\u2014"` fails
    # it just as the bare character does -- the escape is only source
    # spelling. It is right not to distinguish an input from an output: it
    # cannot, and a guard that tried would be guessing.
    #
    # `chr()` keeps every literal here ASCII -- ints and their replacements --
    # so the table needs no exemption from a rule this repository just
    # adopted.
    chr(codepoint): plain
    for codepoint, plain in (
        (0x2014, "--"),    # em dash
        (0x2013, "-"),     # en dash
        (0x2018, "'"),     # left single quote
        (0x2019, "'"),     # right single quote / apostrophe
        (0x201C, '"'),     # left double quote
        (0x201D, '"'),     # right double quote
        (0x2026, "..."),   # ellipsis
        (0x2192, "->"),    # rightwards arrow
        (0x00D7, "x"),     # multiplication sign, as in a 5x5 matrix
        (0x2264, "<="),
        (0x2265, ">="),
        (0x00B1, "+/-"),
    )
}


def _clean(text: str) -> str:
    """Strip the markdown a README uses for emphasis, keeping the words.

    The summary is rendered into a terminal table, where `**bold**` and
    backticks are noise rather than formatting -- and where a character the
    console cannot encode is worse than noise, so typographic punctuation is
    folded to its ASCII spelling on the way through.
    """
    text = re.sub(r"[*_`]+", "", text)
    for fancy, plain in _TERMINAL_SPELLINGS.items():
        text = text.replace(fancy, plain)
    return re.sub(r"\s+", " ", text).strip()


def _lead_sentence(readme: str) -> str:
    """The first sentence of the README's lead paragraph, terminal-safe.

    Split out of `_summary` so the wizard's detail panel can show the whole
    sentence. `_SUMMARY_MAX` exists because a summary is rendered into a
    TABLE CELL; a Panel has no such constraint, and reusing the capped text
    there cut `...SharePoint calculates Resi...` out of risk-register.

    Fourteen of the thirty READMEs open with a `*Theme: ...*` line, which
    sometimes wraps onto a second line and sometimes carries a trailing
    qualifier. It is not consistent enough to key a grouping off, so it is
    skipped rather than parsed.

    Returns "" when there is nothing usable. The caller decides what an
    empty summary looks like; `test_catalogue` asserts none of the shipped
    thirty actually produce one, so an empty string means a NEW template
    broke the convention rather than that this is a normal state.
    """
    lines = readme.splitlines()
    # Drop the H1 and anything before it.
    for index, line in enumerate(lines):
        if line.startswith("# "):
            lines = lines[index + 1 :]
            break

    paragraph: list[str] = []
    in_theme = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if paragraph:
                break
            in_theme = False
            continue
        if stripped.startswith("*Theme:"):
            # May wrap; keep skipping until the emphasis closes or the
            # paragraph ends.
            in_theme = not stripped.endswith("*") or stripped == "*Theme:"
            continue
        if in_theme:
            in_theme = not stripped.endswith("*")
            continue
        if stripped.startswith(("#", ">", "|", "-", "```")):
            break
        paragraph.append(stripped)

    text = _clean(" ".join(paragraph))
    if not text:
        return ""
    # First sentence, but only when the full stop is followed by a space --
    # otherwise `5x5.` inside a phrase, or a version number, cuts it short.
    match = re.search(r"\.(?:\s|$)", text)
    if match:
        text = text[: match.start() + 1]
    return text


def _summary(readme: str) -> str:
    """`_lead_sentence` capped to fit the wizard's table cell."""
    text = _lead_sentence(readme)
    if len(text) > _SUMMARY_MAX:
        # Reserve exactly as many characters as the marker occupies. This read
        # `- 1` while the marker was a one-character ellipsis; ASCII-ifying it
        # to "..." for the wizard's table made every truncated summary two
        # characters over the cap, which `test_each_summary_fits_a_terminal`
        # caught on fifteen templates.
        text = text[: _SUMMARY_MAX - len(_ELLIPSIS)].rstrip() + _ELLIPSIS
    return text


def _title(readme: str, fallback: str) -> str:
    for line in readme.splitlines():
        if line.startswith("# "):
            return _clean(line[2:])
    return fallback


def _mapping_facts(mapping_path: Path) -> tuple[tuple[str, ...], str]:
    """The entity names and prefix, read WITHOUT the mapping loader.

    Deliberately a plain `yaml.safe_load` of two keys. `load_mapping` parses
    and folds every section and raises on anything it dislikes, so using it
    here would let one malformed template take down the whole picker --
    including the twenty-nine that are fine. Listing what is available must
    not depend on all of it being valid.

    The build path still goes through the real loader, so nothing is
    accepted here that would be refused there.
    """
    try:
        raw: Any = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return (), ""
    if not isinstance(raw, dict):
        return (), ""
    entities = raw.get("entities")
    names = tuple(entities) if isinstance(entities, dict) else ()
    prefix = raw.get("prefix")
    return names, prefix if isinstance(prefix, str) else ""


def _build(root: Path) -> Solution:
    readme_path = root / "README.md"
    readme = (
        readme_path.read_text(encoding="utf-8") if readme_path.is_file() else ""
    )
    lists, prefix = _mapping_facts(root / MAPPING_RELPATH)
    return Solution(
        id=root.name,
        title=_title(readme, root.name),
        summary=_summary(readme),
        detail=_lead_sentence(readme),
        lists=lists,
        prefix=prefix,
        root=root,
    )


def available_solutions() -> list[Solution]:
    """Every shipped family, ordered by id.

    A directory only counts when it carries a `schema.dbml` at the family
    standard's path. That keeps a stray directory -- a leftover `build/`,
    an editor's backup -- from appearing in the picker as a template the
    user can choose and then fail to deploy.
    """
    if not SOLUTIONS_DIR.is_dir():
        return []
    found = [
        path.parent.parent
        for path in sorted(SOLUTIONS_DIR.glob(f"*/{SCHEMA_RELPATH.as_posix()}"))
        if path.parent.parent.name not in _NOT_A_SOLUTION
    ]
    return [_build(root) for root in found]


def load_solution(name: str) -> Solution:
    """One family by directory name, or `UnknownSolutionError`."""
    catalogue = available_solutions()
    for solution in catalogue:
        if solution.id == name:
            return solution
    raise UnknownSolutionError(name, [s.id for s in catalogue])
