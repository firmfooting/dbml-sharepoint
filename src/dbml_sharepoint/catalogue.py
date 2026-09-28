"""The blueprints the wizard can offer, as data.

Blueprints come from blueprint roots: core's own `solutions/` directory first,
then the directory each installed distribution registers under the
`dbml_sharepoint.blueprint_roots` entry-point group. One `Solution` per blueprint
directory in any root. Everything here is read-only discovery: nothing in
this module writes, validates a mapping or deploys.

Discovered by glob, never by roster. A hardcoded list of names fails open.
A new template is simply never offered, and every test stays green saying
so. `.github/workflows/ci.yml` builds core's set the same way, and
`test_template_standard.py` derives its conformance cases from it.

Each blueprint declares its id, title, summary and licence in `blueprint.toml`. A blueprint
whose manifest is missing, or claims a licence its distribution does not
declare, is refused rather than offered. Core's root is located relative to
this file, inside the installed package, because the audience for the wizard
is somebody who ran `uvx dbml-sharepoint` and has no checkout.
"""

import re
import tomllib
from dataclasses import dataclass
from importlib.metadata import EntryPoint, PackageNotFoundError, entry_points, metadata
from pathlib import Path, PureWindowsPath
from typing import Any, NamedTuple

from dbml_sharepoint.model import _yaml

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

#: The `--time-zone` value every shipped deploy.md spells its build command
#: with, for the same literal substitution. Deliberately NOT a real zone:
#: `validate_time_zone` refuses it, so a command copied without editing
#: fails closed and names what to pass, where the URL placeholder above
#: passes `validate_site_url` and had to be kept out of the wizard's
#: defaults for exactly that reason.
PLACEHOLDER_TIME_ZONE = "Region/City"

#: Files at the top of `solutions/` that document the collection rather than
#: being one of its members.
_NOT_A_SOLUTION = {"README.md"}

#: Curated reading orders over the families, one file each. A journey is
#: EDITORIAL and may name a family more than one journey names: routine-checks
#: is a digitisation win and a daily-rhythm list at once, and forcing a family
#: into exactly one group is what made the README's four themes rot.
JOURNEYS_DIRNAME = "journeys"

#: Sector overlays: guidance for reading the whole collection from inside one
#: industry, rather than a family anybody deploys.
SECTORS_DIRNAME = "sectors"

#: Directories under `solutions/` that hold documentation rather than families.
#: The discovery glob already excludes them by requiring a `schema.dbml`; this
#: names them so a reader does not have to derive that.
_NOT_A_SOLUTION_DIR = {JOURNEYS_DIRNAME, SECTORS_DIRNAME}

_SUMMARY_MAX = 140

#: ASCII, because the summary is rendered into the wizard's terminal table and
#: a Windows console code page cannot encode U+2026. See
#: `test_messages_bound_for_a_console_are_ascii`.
_ELLIPSIS = "..."

#: The distribution this module ships in. Its blueprints win a duplicate id.
CORE_DISTRIBUTION = "dbml-sharepoint"

#: The entry-point group a blueprint provider registers a zero-argument callable under.
BLUEPRINT_ROOTS_GROUP = "dbml_sharepoint.blueprint_roots"

#: The file every blueprint directory carries beside its README.
BLUEPRINT_MANIFEST = "blueprint.toml"

#: Every key a blueprint.toml carries, each one required.
_MANIFEST_KEYS = ("id", "title", "summary", "license", "origin", "notice", "min_core")

#: The wizard's answer for "every blueprint", read before any id, so no blueprint or journey
#: may take it.
BROWSE_ALL = "all"

#: The origin of a blueprint designed by this project, which needs no notice.
ORIGIN_OWN = "firmfooting"

#: `<organisation>-released` needs a notice file; `<organisation>-held` is never released.
_ORIGIN_DERIVED = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*-(released|held)")


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


class BlueprintManifestError(ValueError):
    """A blueprint's blueprint.toml is missing, malformed, or claims what the catalogue refuses,
    or the blueprint lacks a file every family ships.

    Named so the catalogue can refuse that one blueprint and keep offering the rest,
    and so the reason reaches the operator rather than a traceback.
    """


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
    #: The distribution whose blueprint root holds this blueprint.
    distribution: str
    #: The SPDX licence the blueprint declares, equal to its distribution's.
    license: str
    #: Who designed it: `firmfooting`, `<organisation>-released` or `<organisation>-held`.
    origin: str

    @property
    def schema_path(self) -> Path:
        return self.root / SCHEMA_RELPATH

    @property
    def mapping_path(self) -> Path:
        return self.root / MAPPING_RELPATH

    @property
    def release_path(self) -> Path:
        return self.root / RELEASE_RELPATH


@dataclass(frozen=True)
class Journey:
    """One curated reading order over the families.

    The wizard's first step. Grouping is DECLARED here rather than derived
    from a family's own prose: the READMEs' `*Theme:*` line was never
    consistent enough to key off, and a grouping nothing verifies is a
    grouping that goes stale, which is how one shipped family came to sit in
    no theme at all.
    """

    id: str
    title: str
    summary: str
    #: Declared order, which is the order to deploy in. Not sorted.
    solution_ids: tuple[str, ...]
    path: Path
    #: The distribution whose blueprint root holds this journey file.
    distribution: str


@dataclass(frozen=True)
class BlueprintManifest:
    """What a blueprint declares about itself in blueprint.toml, checked."""

    id: str
    #: Folded to ASCII, because it is rendered into a terminal table.
    title: str
    #: The whole lead sentence; the catalogue caps it for the table itself.
    summary: str
    #: An SPDX expression, equal to the License-Expression of its distribution.
    license: str
    #: `firmfooting`, `<organisation>-released` or `<organisation>-held`.
    origin: str
    #: A file inside the blueprint carrying release terms, or "".
    notice: str
    #: The core version range the blueprint was tested against. Stored, not evaluated.
    min_core: str


class BlueprintRoot(NamedTuple):
    """Where one installed distribution keeps its blueprints, and the licence it declares."""

    distribution: str
    root: Path
    #: The distribution's License-Expression, which each of its blueprints must repeat.
    license: str


class BlueprintRootError(RuntimeError):
    """A blueprint root cannot be read, so no licence the catalogue would print is certain.

    Always names the distribution, so the operator knows what to reinstall or remove.
    """


@dataclass(frozen=True)
class Refusal:
    """A blueprint directory the catalogue will not offer, and the named error why."""

    distribution: str
    path: Path
    reason: str


@dataclass(frozen=True)
class Shadowed:
    """A blueprint or journey not offered because an earlier root offers the same id."""

    #: "blueprint" or "journey".
    kind: str
    id: str
    #: The distribution whose copy is hidden.
    distribution: str
    #: The distribution whose copy is offered instead.
    kept_from: str


@dataclass(frozen=True)
class Catalogue:
    """Everything offered from every root, and what was refused.

    Read once per command, so the wizard and `blueprints` report the same thing.
    """

    solutions: tuple[Solution, ...]
    journeys: tuple[Journey, ...]
    refused: tuple[Refusal, ...]
    shadowed: tuple[Shadowed, ...]


#: Typographic characters a README may use, and their terminal spellings.
#:
#: The wizard renders a README's title and summary into a TERMINAL, where the
#: encoding is the console's choice. A rightwards arrow cannot be encoded by
#: cp1252, cp850 OR cp437, so a shipped family carrying one could raise
#: `UnicodeEncodeError` from inside rich when somebody picks it. An em dash
#: fails on the two OEM pages but not on cp1252, which is why the rule is
#: ASCII rather than any one code page.
#:
#: MEASURED 2026-08-16: no shipped README carries a non-ASCII character any
#: more, because `test_shipped_text_is_ascii` refuses them at source. This
#: table is the fallback for a README added before that gate runs.
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
    return _fold(re.sub(r"[*_`]+", "", text))


def _fold(text: str) -> str:
    """Typography folded to its ASCII spelling and whitespace collapsed; markdown untouched."""
    for fancy, plain in _TERMINAL_SPELLINGS.items():
        text = text.replace(fancy, plain)
    return re.sub(r"\s+", " ", text).strip()


def _manifest_string(raw: dict[str, Any], key: str, path: Path) -> str:
    """One required string value of a blueprint.toml, stripped."""
    if key not in raw:
        raise BlueprintManifestError(f"{path}: declares no '{key}'")
    value = raw[key]
    if not isinstance(value, str):
        raise BlueprintManifestError(
            f"{path}: '{key}' must be a string, not {type(value).__name__}",
        )
    if not value.strip() and key != "notice":
        raise BlueprintManifestError(f"{path}: '{key}' is empty")
    return value.strip()


def _check_notice(blueprint_dir: Path, notice: str, path: Path) -> None:
    """A notice names a file inside the blueprint, so it travels wherever the blueprint goes."""
    # Windows rules read both separators, so this refuses `/x`, `\\x` and `C:x` on every platform.
    if PureWindowsPath(notice).anchor:
        raise BlueprintManifestError(
            f"{path}: notice {notice!r} must be a path relative to the blueprint",
        )
    target = (blueprint_dir / notice).resolve()
    if not target.is_relative_to(blueprint_dir.resolve()) or not target.is_file():
        raise BlueprintManifestError(
            f"{path}: notice {notice!r} is not a file inside the blueprint",
        )


def _unprintable(text: str) -> str:
    """The codepoints in `text` outside printable ASCII, joined, or "" when there are none.

    Control characters are refused with the rest: an escape sequence in a
    title would clear or rewrite the terminal it is printed to.
    """
    return ", ".join(sorted({f"U+{ord(c):04X}" for c in text if not " " <= c <= "~"}))


def _terminal_text(value: str, key: str, path: Path) -> str:
    """`value` folded to ASCII, or refused when a character has no ASCII spelling."""
    folded = _fold(value)
    if found := _unprintable(folded):
        raise BlueprintManifestError(
            f"{path}: '{key}' carries characters a console may not print: {found}",
        )
    return folded


def _manifest_table(blueprint_dir: Path, path: Path) -> dict[str, Any]:
    """The parsed blueprint.toml, or `BlueprintManifestError` saying why it could not be read."""
    if not path.is_file():
        raise BlueprintManifestError(
            f"{blueprint_dir}: no {BLUEPRINT_MANIFEST}; every blueprint declares its id, title, "
            "summary and licence there",
        )
    try:
        # utf-8-sig: an editor on Windows may save a byte-order mark, which TOML does not allow.
        return tomllib.loads(path.read_text(encoding="utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise BlueprintManifestError(
            f"{path}: not UTF-8: {exc.reason} at byte {exc.start}",
        ) from exc
    except OSError as exc:
        raise BlueprintManifestError(f"{path}: cannot be read: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise BlueprintManifestError(f"{path}: not valid TOML: {exc}") from exc


def _check_id(blueprint_id: str, blueprint_dir: Path, path: Path) -> None:
    """The id is the directory name, printable, and not the wizard's browse-all answer."""
    if blueprint_id != blueprint_dir.name:
        raise BlueprintManifestError(
            f"{path}: id {blueprint_id!r} is not the directory name {blueprint_dir.name!r}",
        )
    if found := _unprintable(blueprint_id):
        raise BlueprintManifestError(
            f"{path}: 'id' carries characters a console may not print: {found}",
        )
    if blueprint_id == BROWSE_ALL:
        raise BlueprintManifestError(
            f"{path}: the id {BROWSE_ALL!r} is reserved: the wizard reads it as every blueprint",
        )


def read_blueprint_manifest(blueprint_dir: Path, distribution_licence: str) -> BlueprintManifest:
    """Read and check `blueprint_dir/blueprint.toml`, or raise `BlueprintManifestError`.

    `distribution_licence` is the License-Expression of the distribution the
    blueprint was found in. A blueprint may not claim a different one, so the licence a
    listing shows is the one the installed package was published under.
    """
    path = blueprint_dir / BLUEPRINT_MANIFEST
    raw = _manifest_table(blueprint_dir, path)
    unknown = sorted(set(raw) - set(_MANIFEST_KEYS))
    if unknown:
        raise BlueprintManifestError(f"{path}: unknown key(s) {unknown}")
    values = {key: _manifest_string(raw, key, path) for key in _MANIFEST_KEYS}
    _check_id(values["id"], blueprint_dir, path)
    if values["license"] != distribution_licence:
        raise BlueprintManifestError(
            f"{path}: license {values['license']!r} differs from {distribution_licence!r}, "
            "the License-Expression of the distribution that ships it",
        )
    origin = values["origin"]
    derived = _ORIGIN_DERIVED.fullmatch(origin)
    if origin != ORIGIN_OWN and derived is None:
        raise BlueprintManifestError(
            f"{path}: origin {origin!r} is not {ORIGIN_OWN!r}, "
            "'<organisation>-released' or '<organisation>-held'",
        )
    if derived is not None and derived.group(1) == "released" and not values["notice"]:
        raise BlueprintManifestError(
            f"{path}: origin {origin!r} needs a notice file carrying the release terms",
        )
    if values["notice"]:
        _check_notice(blueprint_dir, values["notice"], path)
    return BlueprintManifest(
        id=values["id"],
        title=_terminal_text(values["title"], "title", path),
        summary=_terminal_text(values["summary"], "summary", path),
        license=values["license"],
        origin=origin,
        notice=values["notice"],
        min_core=values["min_core"],
    )


def _cap(text: str) -> str:
    """`text` capped to fit the wizard's table cell; `detail` keeps the whole sentence."""
    if len(text) > _SUMMARY_MAX:
        # Reserve exactly as many characters as the marker occupies.
        return text[: _SUMMARY_MAX - len(_ELLIPSIS)].rstrip() + _ELLIPSIS
    return text


def _mapping_facts(mapping_path: Path) -> tuple[tuple[str, ...], str]:
    """The entity names and prefix, read WITHOUT the mapping loader.

    Deliberately a plain parse of two keys. `load_mapping` parses
    and folds every section and raises on anything it dislikes, so using it
    here would let one malformed template take down the whole picker --
    including every other family, all of them fine. Listing what is
    available must not depend on all of it being valid.

    The build path still goes through the real loader, so nothing is
    accepted here that would be refused there.
    """
    try:
        raw: Any = _yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, *_yaml.PARSE_ERRORS):
        return (), ""
    if not isinstance(raw, dict):
        return (), ""
    entities = raw.get("entities")
    names = tuple(entities) if isinstance(entities, dict) else ()
    prefix = raw.get("prefix")
    return names, prefix if isinstance(prefix, str) else ""


def _family_dirs(root: Path) -> list[Path]:
    """Every directory under `root` with a schema at the family standard's path or a manifest.

    That keeps a stray directory (a leftover `build/`, an editor's backup) from
    appearing in the picker as a blueprint the user can choose and then fail
    to deploy, while a blueprint that declares itself and lacks its schema is
    refused by name rather than ignored.
    """
    if not root.is_dir():
        return []
    families = {path.parent.parent for path in root.glob(f"*/{SCHEMA_RELPATH.as_posix()}")}
    families |= {path.parent for path in root.glob(f"*/{BLUEPRINT_MANIFEST}")}
    return sorted(family for family in families if family.name not in _NOT_A_SOLUTION)


def _build(family: Path, source: BlueprintRoot) -> Solution:
    """One blueprint, described by its blueprint.toml. Raises `BlueprintManifestError`."""
    missing = [
        relpath.as_posix()
        for relpath in (SCHEMA_RELPATH, MAPPING_RELPATH, RELEASE_RELPATH)
        if not (family / relpath).is_file()
    ]
    if missing:
        raise BlueprintManifestError(
            f"{family}: no {', '.join(missing)}; every blueprint ships its schema, "
            "mapping and release, and the wizard copies all three",
        )
    manifest = read_blueprint_manifest(family, source.license)
    lists, prefix = _mapping_facts(family / MAPPING_RELPATH)
    # Printed when the blueprint is chosen, before the mapping loader ever sees them.
    for key, text in (("prefix", prefix), *(("list", name) for name in lists)):
        if found := _unprintable(text):
            raise BlueprintManifestError(
                f"{family / MAPPING_RELPATH}: {key} {text!r} carries characters a console "
                f"may not print: {found}",
            )
    return Solution(
        id=manifest.id,
        title=manifest.title,
        summary=_cap(manifest.summary),
        detail=manifest.summary,
        lists=lists,
        prefix=prefix,
        root=family,
        distribution=source.distribution,
        license=manifest.license,
        origin=manifest.origin,
    )


def _gather_solutions(
    roots: list[BlueprintRoot],
) -> tuple[list[Solution], list[Refusal], list[Shadowed]]:
    """Every blueprint in every root, in root order then by id; a repeated id is hidden."""
    solutions: list[Solution] = []
    refused: list[Refusal] = []
    shadowed: list[Shadowed] = []
    kept: dict[str, str] = {}
    for source in roots:
        for family in _family_dirs(source.root):
            try:
                solution = _build(family, source)
            except BlueprintManifestError as exc:
                refused.append(Refusal(source.distribution, family, str(exc)))
                continue
            if solution.id in kept:
                shadowed.append(
                    Shadowed("blueprint", solution.id, source.distribution, kept[solution.id]),
                )
                continue
            kept[solution.id] = source.distribution
            solutions.append(solution)
    return solutions, refused, shadowed


def available_solutions() -> list[Solution]:
    """Every blueprint offered, core's first, each root's ordered by id.

    A refused blueprint is left out; `read_catalogue` says which and why.
    """
    return _gather_solutions(blueprint_roots())[0]


#: Opens and closes a journey file's YAML front matter.
_FRONT_MATTER_FENCE = "---"


def _front_matter(text: str, path: Path) -> dict[str, Any]:
    """The YAML block a journey file opens with.

    Declared rather than parsed out of prose. The whole reason this file
    refuses to key grouping off a README's `*Theme:*` line is that prose is
    not consistent enough to trust; a journey states its members in YAML so
    the guard in `test_journeys.py` can check them.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != _FRONT_MATTER_FENCE:
        raise ValueError(f"{path}: no YAML front matter; the file must open with '---'")
    try:
        end = lines.index(_FRONT_MATTER_FENCE, 1)
    except ValueError:
        raise ValueError(f"{path}: front matter is never closed with '---'") from None
    try:
        # The opening fence parses as a blank line, so the lines the parser names are the file's.
        loaded = _yaml.safe_load("\n".join(["", *lines[1:end]])) or {}
    except _yaml.TagOrDirectiveError as exc:
        raise ValueError(f"{path}: front matter {exc}") from exc
    except _yaml.RefusedYAMLError as exc:
        raise ValueError(f"{path}: front matter is refused: {exc}") from exc
    except _yaml.PARSE_ERRORS as exc:
        raise ValueError(f"{path}: front matter is not valid YAML: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"{path}: front matter must be a mapping")
    return loaded


def _build_journey(path: Path, distribution: str) -> Journey:
    raw = _front_matter(path.read_text(encoding="utf-8"), path)
    unknown = set(raw) - {"title", "summary", "solutions"}
    if unknown:
        raise ValueError(f"{path}: unknown front-matter key(s) {sorted(unknown)}")
    solutions = raw.get("solutions")
    if not isinstance(solutions, list) or not solutions:
        raise ValueError(f"{path}: 'solutions' must be a non-empty list")
    if not all(isinstance(s, str) for s in solutions):
        raise ValueError(f"{path}: 'solutions' must be a list of family ids")
    if len(set(solutions)) != len(solutions):
        raise ValueError(f"{path}: 'solutions' names the same family twice")
    for key in ("title", "summary"):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise ValueError(f"{path}: '{key}' must be a non-empty string")
    shown = {key: _clean(str(raw[key])) for key in ("title", "summary")}
    # Rendered into the same terminal as a blueprint's title, so held to the same rule.
    for key, text in {"id": path.stem, **shown, "solutions": "".join(solutions)}.items():
        if found := _unprintable(text):
            raise ValueError(
                f"{path}: '{key}' carries characters a console may not print: {found}",
            )
    if path.stem == BROWSE_ALL:
        raise ValueError(
            f"{path}: the id {BROWSE_ALL!r} is reserved: the wizard reads it as every blueprint",
        )
    return Journey(
        id=path.stem,
        title=shown["title"],
        summary=shown["summary"],
        solution_ids=tuple(solutions),
        path=path,
        distribution=distribution,
    )


def _gather_journeys(roots: list[BlueprintRoot]) -> tuple[list[Journey], list[Shadowed]]:
    """Every journey in every root, ordered by id; a repeated id is hidden."""
    journeys: dict[str, Journey] = {}
    shadowed: list[Shadowed] = []
    for source in roots:
        directory = source.root / JOURNEYS_DIRNAME
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.md")):
            try:
                journey = _build_journey(path, source.distribution)
            except (ValueError, OSError) as exc:
                # Core's journeys are guarded by its tests; a provider's reach the operator.
                if source.distribution == CORE_DISTRIBUTION:
                    raise
                raise BlueprintRootError(f"{source.distribution}: {exc}") from exc
            if journey.id in journeys:
                kept = journeys[journey.id].distribution
                shadowed.append(Shadowed("journey", journey.id, source.distribution, kept))
                continue
            journeys[journey.id] = journey
    return sorted(journeys.values(), key=lambda journey: journey.id), shadowed


def available_journeys() -> list[Journey]:
    """Every curated reading order, ordered by id.

    Unlike `available_solutions`, a malformed file RAISES rather than being
    skipped. A family that will not load is one template out of the picker;
    a journey that will not load is a grouping silently missing its members,
    and the guard that would have caught it is the one being bypassed.
    """
    return _gather_journeys(blueprint_roots())[0]


def _declared_licence(distribution: str, declared: str | None) -> str:
    """The License-Expression a distribution publishes, or `BlueprintRootError`."""
    if not declared:
        raise BlueprintRootError(
            f"{distribution} declares no License-Expression in its metadata, so the "
            "licence of its blueprints cannot be checked",
        )
    return declared


def _core_root() -> BlueprintRoot:
    """Core's own blueprints. `SOLUTIONS_DIR` is read here so a test can point it elsewhere."""
    try:
        declared = metadata(CORE_DISTRIBUTION).get("License-Expression")
    except PackageNotFoundError as exc:
        raise BlueprintRootError(
            f"{CORE_DISTRIBUTION} is not installed, so the licence of its blueprints cannot "
            "be read; install it (uv sync, or uvx) rather than importing a source tree",
        ) from exc
    return BlueprintRoot(
        CORE_DISTRIBUTION, SOLUTIONS_DIR, _declared_licence(CORE_DISTRIBUTION, declared),
    )


def _provider_root(point: EntryPoint) -> BlueprintRoot:
    """One provider's root, checked, or `BlueprintRootError` naming the distribution."""
    if point.dist is None:
        raise BlueprintRootError(
            f"entry point {point.name} ({point.value}) in {BLUEPRINT_ROOTS_GROUP} belongs "
            "to no distribution, so its blueprints have no licence to check",
        )
    try:
        distribution = point.dist.name
        declared = point.dist.metadata.get("License-Expression")
    except (OSError, ValueError) as exc:
        raise BlueprintRootError(
            f"entry point {point.name} ({point.value}) in {BLUEPRINT_ROOTS_GROUP}: its "
            f"distribution's metadata cannot be read: {type(exc).__name__}: {exc}",
        ) from exc
    licence = _declared_licence(distribution, declared)
    # Any failure inside a provider's own code is that provider's, and named as such.
    try:
        root: object = point.load()()
    except Exception as exc:
        raise BlueprintRootError(
            f"{distribution}: {point.value} failed to load: {type(exc).__name__}: {exc}",
        ) from exc
    if not isinstance(root, Path):
        kind = f"{type(root).__module__}.{type(root).__qualname__}"
        raise BlueprintRootError(
            f"{distribution}: {point.value} returned a {kind}, not a directory on disk. "
            "Blueprints are copied and built as real files, so install the distribution unpacked",
        )
    if not root.is_dir():
        raise BlueprintRootError(f"{distribution}: {root} is not a directory")
    # A directory denied to this user globs as empty, which would hide every blueprint in it.
    try:
        next(root.iterdir(), None)
    except OSError as exc:
        raise BlueprintRootError(f"{distribution}: {root} cannot be listed: {exc}") from exc
    return BlueprintRoot(distribution, root, licence)


def blueprint_roots() -> list[BlueprintRoot]:
    """Where blueprints are read from: core first, then each provider by distribution name.

    Raises `BlueprintRootError` when any root cannot be read. A provider that is
    installed but unreadable makes every licence the catalogue would print
    uncertain, so nothing is offered until it is fixed or removed.
    """
    providers = [_provider_root(point) for point in entry_points(group=BLUEPRINT_ROOTS_GROUP)]
    return [_core_root(), *sorted(providers, key=lambda root: root.distribution)]


def read_catalogue() -> Catalogue:
    """Every root's blueprints and journeys, what was refused, and what was hidden.

    Raises `BlueprintRootError` when a root cannot be read or a provider's
    journey is malformed, and `ValueError` for a malformed journey of core's own.
    """
    roots = blueprint_roots()
    solutions, refused, hidden = _gather_solutions(roots)
    journeys, hidden_journeys = _gather_journeys(roots)
    # One wizard prompt takes a blueprint id or a journey id, and a blueprint id wins it.
    offered = {s.id: s.distribution for s in solutions}
    hidden_journeys += [
        Shadowed("journey", journey.id, journey.distribution, offered[journey.id])
        for journey in journeys
        if journey.id in offered
    ]
    return Catalogue(
        solutions=tuple(solutions),
        journeys=tuple(j for j in journeys if j.id not in offered),
        refused=tuple(refused),
        shadowed=(*hidden, *hidden_journeys),
    )


def notices(found: Catalogue) -> list[str]:
    """What an interface prints once per run: each refused blueprint, then each hidden group.

    Hidden ids are grouped by package, so a provider that repeats every core
    blueprint costs one line rather than one per blueprint.
    """
    lines = [f"Not offered: {r.distribution}: {r.reason}" for r in found.refused]
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for hidden in found.shadowed:
        grouped.setdefault((hidden.kind, hidden.distribution, hidden.kept_from), []).append(
            hidden.id,
        )
    for (kind, distribution, kept_from), ids in grouped.items():
        noun, verb = (kind, "shares") if len(ids) == 1 else (f"{kind}s", "share")
        lines.append(
            f"Hidden: {len(ids)} {noun} from {distribution} {verb} an id with one from "
            f"{kept_from}, which is offered instead: {', '.join(sorted(ids))}",
        )
    return lines


def load_solution(name: str) -> Solution:
    """One family by directory name, or `UnknownSolutionError`."""
    catalogue = available_solutions()
    for solution in catalogue:
        if solution.id == name:
            return solution
    raise UnknownSolutionError(name, [s.id for s in catalogue])
