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

#: Files at the top of `solutions/` that document the collection rather than
#: being one of its members.
_NOT_A_SOLUTION = {"README.md", "HEALTHCARE.md"}

_SUMMARY_MAX = 140


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


def _clean(text: str) -> str:
    """Strip the markdown a README uses for emphasis, keeping the words.

    The summary is rendered into a terminal table, where `**bold**` and
    backticks are noise rather than formatting.
    """
    text = re.sub(r"[*_`]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _summary(readme: str) -> str:
    """The first sentence of a family README's opening paragraph.

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
    if len(text) > _SUMMARY_MAX:
        text = text[: _SUMMARY_MAX - 1].rstrip() + "…"
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
