"""The solution templates the wizard can offer, as data.

Templates come from solution roots: core's own `solutions/` directory first,
then the directory each installed distribution registers under the
`dbml_sharepoint.solution_roots` entry-point group. One `Solution` per pack
directory in any root. Everything here is read-only discovery: nothing in
this module writes, validates a mapping or deploys.

Discovered by glob, never by roster. A hardcoded list of names fails open.
A new template is simply never offered, and every test stays green saying
so. `.github/workflows/ci.yml` builds core's set the same way, and
`test_template_standard.py` derives its conformance cases from it.

Each pack declares its id, title, summary and licence in `pack.toml`. A pack
whose manifest is missing, or claims a licence its distribution does not
declare, is refused rather than offered. Core's root is located relative to
this file, inside the installed package, because the audience for the wizard
is somebody who ran `uvx dbml-sharepoint` and has no checkout.
"""

import re
import tomllib
from dataclasses import dataclass
from importlib.metadata import EntryPoint, PackageNotFoundError, entry_points, metadata
from pathlib import Path
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

#: The distribution this module ships in. Its packs win a duplicate id.
CORE_DISTRIBUTION = "dbml-sharepoint"

#: The entry-point group a pack provider registers a zero-argument callable under.
SOLUTION_ROOTS_GROUP = "dbml_sharepoint.solution_roots"

#: The file every pack directory carries beside its README.
PACK_MANIFEST = "pack.toml"

#: Every key a pack.toml carries, each one required.
_MANIFEST_KEYS = ("id", "title", "summary", "license", "origin", "notice", "min_core")

#: The origin of a pack designed by this project, which needs no notice.
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


class PackManifestError(ValueError):
    """A pack's pack.toml is missing, malformed, or claims what the catalogue refuses.

    Named so the catalogue can refuse that one pack and keep offering the rest,
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
    #: The distribution whose solution root holds this pack.
    distribution: str
    #: The SPDX licence the pack declares, equal to its distribution's.
    license: str
    #: Who designed the pack: `firmfooting`, `<organisation>-released` or `<organisation>-held`.
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
    #: The distribution whose solution root holds this journey file.
    distribution: str


@dataclass(frozen=True)
class PackManifest:
    """What a pack declares about itself in pack.toml, checked."""

    id: str
    #: Folded to ASCII, because it is rendered into a terminal table.
    title: str
    #: The whole lead sentence; the catalogue caps it for the table itself.
    summary: str
    #: An SPDX expression, equal to the License-Expression of its distribution.
    license: str
    #: `firmfooting`, `<organisation>-released` or `<organisation>-held`.
    origin: str
    #: A file inside the pack carrying release terms, or "".
    notice: str
    #: The core version range the pack was tested against. Stored, not evaluated.
    min_core: str


class SolutionRoot(NamedTuple):
    """Where one installed distribution keeps its packs, and the licence it declares."""

    distribution: str
    root: Path
    #: The distribution's License-Expression, which each of its packs must repeat.
    license: str


class SolutionRootError(RuntimeError):
    """A solution root cannot be read, so no licence the catalogue would print is certain.

    Always names the distribution, so the operator knows what to reinstall or remove.
    """


@dataclass(frozen=True)
class Refusal:
    """A pack directory the catalogue will not offer, and the named error why."""

    distribution: str
    path: Path
    reason: str


@dataclass(frozen=True)
class Shadowed:
    """A template or journey not offered because an earlier root offers the same id."""

    #: "template" or "journey".
    kind: str
    id: str
    #: The distribution whose copy is hidden.
    distribution: str
    #: The distribution whose copy is offered instead.
    kept_from: str


@dataclass(frozen=True)
class Catalogue:
    """Everything offered from every root, and what was refused.

    Read once per command, so the wizard and `solutions` report the same thing.
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
    """One required string value of a pack.toml, stripped."""
    if key not in raw:
        raise PackManifestError(f"{path}: declares no '{key}'")
    value = raw[key]
    if not isinstance(value, str):
        raise PackManifestError(f"{path}: '{key}' must be a string, not {type(value).__name__}")
    if not value.strip() and key != "notice":
        raise PackManifestError(f"{path}: '{key}' is empty")
    return value.strip()


def _check_notice(pack_dir: Path, notice: str, path: Path) -> None:
    """A notice names a file inside the pack, so it travels wherever the pack is copied."""
    target = (pack_dir / notice).resolve()
    if not target.is_relative_to(pack_dir.resolve()) or not target.is_file():
        raise PackManifestError(f"{path}: notice {notice!r} is not a file inside the pack")


def _unencodable(text: str) -> str:
    """The codepoints in `text` with no ASCII spelling, joined, or "" when there are none."""
    return ", ".join(sorted({f"U+{ord(c):04X}" for c in text if not c.isascii()}))


def _terminal_text(value: str, key: str, path: Path) -> str:
    """`value` folded to ASCII, or refused when a character has no ASCII spelling."""
    folded = _fold(value)
    if found := _unencodable(folded):
        raise PackManifestError(
            f"{path}: '{key}' carries characters a console may not encode: {found}",
        )
    return folded


def read_pack_manifest(pack_dir: Path, distribution_licence: str) -> PackManifest:
    """Read and check `pack_dir/pack.toml`, or raise `PackManifestError`.

    `distribution_licence` is the License-Expression of the distribution the
    pack was found in. A pack may not claim a different one, so the licence a
    listing shows is the one the installed package was published under.
    """
    path = pack_dir / PACK_MANIFEST
    if not path.is_file():
        raise PackManifestError(
            f"{pack_dir}: no {PACK_MANIFEST}; every pack declares its id, title, "
            "summary and licence there",
        )
    try:
        # utf-8-sig: an editor on Windows may save a byte-order mark, which TOML does not allow.
        raw = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise PackManifestError(f"{path}: not UTF-8: {exc.reason} at byte {exc.start}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise PackManifestError(f"{path}: not valid TOML: {exc}") from exc
    unknown = sorted(set(raw) - set(_MANIFEST_KEYS))
    if unknown:
        raise PackManifestError(f"{path}: unknown key(s) {unknown}")
    values = {key: _manifest_string(raw, key, path) for key in _MANIFEST_KEYS}
    if values["id"] != pack_dir.name:
        raise PackManifestError(
            f"{path}: id {values['id']!r} is not the directory name {pack_dir.name!r}",
        )
    if values["license"] != distribution_licence:
        raise PackManifestError(
            f"{path}: license {values['license']!r} differs from {distribution_licence!r}, "
            "the License-Expression of the distribution that ships it",
        )
    origin = values["origin"]
    derived = _ORIGIN_DERIVED.fullmatch(origin)
    if origin != ORIGIN_OWN and derived is None:
        raise PackManifestError(
            f"{path}: origin {origin!r} is not {ORIGIN_OWN!r}, "
            "'<organisation>-released' or '<organisation>-held'",
        )
    if derived is not None and derived.group(1) == "released" and not values["notice"]:
        raise PackManifestError(
            f"{path}: origin {origin!r} needs a notice file carrying the release terms",
        )
    if values["notice"]:
        _check_notice(pack_dir, values["notice"], path)
    return PackManifest(
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
    """Every directory under `root` with a schema at the family standard's path.

    That keeps a stray directory (a leftover `build/`, an editor's backup) from
    appearing in the picker as a template the user can choose and then fail
    to deploy.
    """
    if not root.is_dir():
        return []
    return [
        path.parent.parent
        for path in sorted(root.glob(f"*/{SCHEMA_RELPATH.as_posix()}"))
        if path.parent.parent.name not in _NOT_A_SOLUTION
    ]


def _build(family: Path, source: SolutionRoot) -> Solution:
    """One pack, described by its pack.toml. Raises `PackManifestError`."""
    manifest = read_pack_manifest(family, source.license)
    lists, prefix = _mapping_facts(family / MAPPING_RELPATH)
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
    roots: list[SolutionRoot],
) -> tuple[list[Solution], list[Refusal], list[Shadowed]]:
    """Every pack in every root, in root order then by id; a repeated id is hidden."""
    solutions: list[Solution] = []
    refused: list[Refusal] = []
    shadowed: list[Shadowed] = []
    kept: dict[str, str] = {}
    for source in roots:
        for family in _family_dirs(source.root):
            try:
                solution = _build(family, source)
            except PackManifestError as exc:
                refused.append(Refusal(source.distribution, family, str(exc)))
                continue
            if solution.id in kept:
                shadowed.append(
                    Shadowed("template", solution.id, source.distribution, kept[solution.id]),
                )
                continue
            kept[solution.id] = source.distribution
            solutions.append(solution)
    return solutions, refused, shadowed


def available_solutions() -> list[Solution]:
    """Every template offered, core's first, each root's ordered by id.

    A refused pack is left out; `read_catalogue` says which and why.
    """
    return _gather_solutions(solution_roots())[0]


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
    for key, text in shown.items():
        # Rendered into the same terminal table as a pack's title, so held to the same rule.
        if found := _unencodable(text):
            raise ValueError(
                f"{path}: '{key}' carries characters a console may not encode: {found}",
            )
    return Journey(
        id=path.stem,
        title=shown["title"],
        summary=shown["summary"],
        solution_ids=tuple(solutions),
        path=path,
        distribution=distribution,
    )


def _gather_journeys(roots: list[SolutionRoot]) -> tuple[list[Journey], list[Shadowed]]:
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
            except ValueError as exc:
                # Core's journeys are guarded by its tests; a provider's reach the operator.
                if source.distribution == CORE_DISTRIBUTION:
                    raise
                raise SolutionRootError(f"{source.distribution}: {exc}") from exc
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
    return _gather_journeys(solution_roots())[0]


def _declared_licence(distribution: str, declared: str | None) -> str:
    """The License-Expression a distribution publishes, or `SolutionRootError`."""
    if not declared:
        raise SolutionRootError(
            f"{distribution} declares no License-Expression in its metadata, so the "
            "licence of its packs cannot be checked",
        )
    return declared


def _core_root() -> SolutionRoot:
    """Core's own packs. `SOLUTIONS_DIR` is read here so a test can point it elsewhere."""
    try:
        declared = metadata(CORE_DISTRIBUTION).get("License-Expression")
    except PackageNotFoundError as exc:
        raise SolutionRootError(
            f"{CORE_DISTRIBUTION} is not installed, so the licence of its packs cannot "
            "be read; install it (uv sync, or uvx) rather than importing a source tree",
        ) from exc
    return SolutionRoot(
        CORE_DISTRIBUTION, SOLUTIONS_DIR, _declared_licence(CORE_DISTRIBUTION, declared),
    )


def _provider_root(point: EntryPoint) -> SolutionRoot:
    """One provider's root, checked, or `SolutionRootError` naming the distribution."""
    if point.dist is None:
        raise SolutionRootError(
            f"entry point {point.name} ({point.value}) in {SOLUTION_ROOTS_GROUP} belongs "
            "to no distribution, so its packs have no licence to check",
        )
    distribution = point.dist.name
    licence = _declared_licence(distribution, point.dist.metadata.get("License-Expression"))
    # Any failure inside a provider's own code is that provider's, and named as such.
    try:
        root: object = point.load()()
    except Exception as exc:
        raise SolutionRootError(
            f"{distribution}: {point.value} failed to load: {type(exc).__name__}: {exc}",
        ) from exc
    if not isinstance(root, Path):
        kind = f"{type(root).__module__}.{type(root).__qualname__}"
        raise SolutionRootError(
            f"{distribution}: {point.value} returned a {kind}, not a directory on disk. "
            "Packs are copied and built as real files, so install the distribution unpacked",
        )
    if not root.is_dir():
        raise SolutionRootError(f"{distribution}: {root} is not a directory")
    return SolutionRoot(distribution, root, licence)


def solution_roots() -> list[SolutionRoot]:
    """Where packs are read from: core first, then each provider by distribution name.

    Raises `SolutionRootError` when any root cannot be read. A provider that is
    installed but unreadable makes every licence the catalogue would print
    uncertain, so nothing is offered until it is fixed or removed.
    """
    providers = [_provider_root(point) for point in entry_points(group=SOLUTION_ROOTS_GROUP)]
    return [_core_root(), *sorted(providers, key=lambda root: root.distribution)]


def read_catalogue() -> Catalogue:
    """Every root's templates and journeys, what was refused, and what was hidden.

    Raises `SolutionRootError` when a root cannot be read or a provider's
    journey is malformed, and `ValueError` for a malformed journey of core's own.
    """
    roots = solution_roots()
    solutions, refused, hidden = _gather_solutions(roots)
    journeys, hidden_journeys = _gather_journeys(roots)
    return Catalogue(
        solutions=tuple(solutions),
        journeys=tuple(journeys),
        refused=tuple(refused),
        shadowed=(*hidden, *hidden_journeys),
    )


def notices(found: Catalogue) -> list[str]:
    """What an interface prints once per run: each refused pack, then each hidden group.

    Hidden ids are grouped by package, so a provider that repeats every core
    pack costs one line rather than one per pack.
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
