"""Command-line interface for dbml-sharepoint."""

import datetime as dt
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
from textwrap import wrap
from typing import Any, Final, NoReturn
from urllib.parse import urlparse, urlunparse

import typer
import yaml
from pyparsing.exceptions import ParseBaseException

from dbml_sharepoint import __version__
from dbml_sharepoint.analysis.demo_marker import DEMO_TITLE_PREFIX
from dbml_sharepoint.analysis.finding_help import FINDING_HELP, RETIRED_FINDINGS
from dbml_sharepoint.analysis.findings import Finding
from dbml_sharepoint.analysis.limits import MAX_DISPLAY_TITLE
from dbml_sharepoint.analysis.sidecars import (
    CHANGE_LOG_TITLE,
    EXTERNAL_LOG_DEFAULT,
)
from dbml_sharepoint.analysis.validator import validate_all
from dbml_sharepoint.bundle import (
    REPORT_DICTIONARY,
    REPORT_GUIDE,
    REPORT_VIEWS_SQL,
    SeedRequiresDemoItemsError,
    clear_generated,
    emit_bundle,
    write_artifact,
)
from dbml_sharepoint.catalogue import (
    MAPPING_RELPATH,
    RELEASE_RELPATH,
    SCHEMA_RELPATH,
)
from dbml_sharepoint.extension import (
    BaseExtension,
    SiteContext,
    UnknownExtensionError,
    resolve_extension,
)
from dbml_sharepoint.extract.emit import DEFAULT_PREFIX
from dbml_sharepoint.extract.folder import (
    README_FILENAME,
    folder_for,
    folder_for_download,
    seed,
)
from dbml_sharepoint.extract.list_url import ListUrlError, parse_list_url
from dbml_sharepoint.extract.run import (
    NOTES_RELPATH,
    check_identifier,
    entity_name_for,
    extraction_from,
)
from dbml_sharepoint.extract.run import write as write_extraction
from dbml_sharepoint.extract.sources import load_source
from dbml_sharepoint.extract.wizard import run_extract_wizard
from dbml_sharepoint.generators.extractgen import EXTRACT_SCRIPT, download_name
from dbml_sharepoint.generators.jsgen import build_schema_json
from dbml_sharepoint.generators.maintaingen import (
    COLUMNS_SCRIPT,
    PROTECTION_SCRIPT,
    generate_columns_js,
    generate_protection_js,
)
from dbml_sharepoint.generators.manifestgen import generate_manifest
from dbml_sharepoint.generators.reportgen import (
    generate_data_dictionary,
    generate_dictionary_powerquery,
    generate_dictionary_sql,
    generate_powerquery,
    generate_reporting_md,
    generate_sql_views,
)
from dbml_sharepoint.model.env_file import (
    CHANGE_LOG_LIST_PARAMETER,
    DEPLOYMENT_LOG_LIST_PARAMETER,
    ENTERPRISE_READER_PARAMETER,
    ENV_FILENAME,
    ENV_SETTINGS,
    NO_ENV_FILE,
    EnvFileError,
    EnvProvenance,
    EnvValue,
    read_env_file,
)
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import MappingBundle
from dbml_sharepoint.model.parser import Schema, parse_dbml
from dbml_sharepoint.model.release import Release, load_release
from dbml_sharepoint.wizard import run_wizard, stdin_is_interactive

app = typer.Typer(
    name="dbml-sharepoint",
    # ASCII "->" rather than an arrow. This string is rendered by rich to a
    # console whose encoding the locale decides, and a cp1252 console cannot
    # encode U+2192 -- which made a bare `--help`, the first command anybody
    # runs, raise UnicodeEncodeError instead of printing. rich already
    # substitutes ASCII box-drawing on a legacy console; it does not
    # substitute our own text. Guarded by
    # test_help_text_survives_a_legacy_windows_code_page.
    help="Generic DBML -> SharePoint browser-paste deploy.js.txt generator.",
    # Not `no_args_is_help`: a bare invocation runs the wizard. The help
    # fallback moved into the callback below, which can tell an interactive
    # terminal from a pipe -- `no_args_is_help` cannot.
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Run the interactive wizard when invoked with no subcommand.

    Every documented flag still works exactly as before: `build`, `report`
    and `version` are untouched, and this callback returns immediately when
    one of them was named.

    A bare invocation only prompts when stdin AND stdout are both a
    terminal. In CI, a cron job, a Dockerfile or a pipe it prints help and
    exits 0, which is what a bare invocation did before the wizard existed
    -- so nothing that scripted `dbml-sharepoint` changes behaviour.
    """
    if ctx.invoked_subcommand is not None:
        return
    if not stdin_is_interactive():
        typer.echo(ctx.get_help())
        raise typer.Exit(code=0)
    raise typer.Exit(code=run_wizard())


@app.command()
def new() -> None:
    """Interactively copy a solution template into a new project.

    The same wizard a bare `dbml-sharepoint` runs, named so it can be asked
    for explicitly and so it appears in `--help`.
    """
    raise typer.Exit(code=run_wizard())

# Empty schema view used to render a findings-only manifest when validation
# fails: build_schema_json cannot run safely on an invalid schema.
_EMPTY_SCHEMA_JSON: dict[str, Any] = {
    "lists": [],
    "phase2_lookups": [],
    "indexed_columns": [],
    "views": [],
    "form_formatting": [],
    "permission_levels": [],
    "groups": [],
    "list_assignments": [],
    "requires_manage_permissions": False,
    "seed_items": [],
}


# A bad config file fails as one of these. Deliberately not `Exception`:
# an unexpected error is a bug in the tool and must keep its traceback.
_CONFIG_ERRORS = (ValueError, KeyError, OSError, yaml.YAMLError, ParseBaseException)

# Includes the pre-normalisation names for the same reason `bundle`'s
# _LEGACY_ARTIFACTS does: `report` clears its previous output so a query
# for a list that has left the schema cannot outlive it, and a name this
# command used to write is exactly that kind of survivor. Note the old
# DATA-DICTIONARY.md spelling was unique to THIS command -- `build` has
# always written reporting/data-dictionary.md -- which is the
# inconsistency the rename closed.
_REPORT_FILES = (
    REPORT_GUIDE,
    REPORT_DICTIONARY,
    # Superseded names, newest first. `reporting.md` existed only briefly
    # between the case normalisation and this rename, but "briefly" is not
    # "never" for anyone tracking main.
    "reporting.md",
    "REPORTING.md",
    "DATA-DICTIONARY.md",
)
# (subdirectory, glob) pairs naming everything `report` writes below `out`.
_REPORT_DIRECTORY_CONTENTS = (("powerquery", "*.pq"), ("sql", REPORT_VIEWS_SQL))


def _clear_report_output(out: Path) -> None:
    """Remove the artifacts this command writes, and nothing else.

    Deliberately not `rmtree` on powerquery/ and sql/. Those names are
    generic, `--out` is routinely aimed at a directory the operator also
    keeps their own work in, and a hand-written migration sitting beside
    views.sql is not this command's to delete. Remove by the names `report`
    generates, then drop each directory only if emptying it left nothing
    behind.

    `*.pq` is the one broad pattern, and it is deliberate: a stale query
    from a list that has left the schema is indistinguishable from a
    hand-written one, and leaving it is the worse failure, because it
    documents a list that no longer exists. The docs say so; `--out` is not the place
    to keep your own .pq files.
    """
    for dirname, pattern in _REPORT_DIRECTORY_CONTENTS:
        directory = out / dirname
        for path in sorted(directory.glob(pattern)):
            if path.is_file():
                path.unlink()
        with suppress(OSError):
            directory.rmdir()  # refuses when the operator left anything here
    for filename in _REPORT_FILES:
        (out / filename).unlink(missing_ok=True)


def _echo_warnings(findings: list[Finding]) -> None:
    """Say what the build warned about, on the terminal, or say nothing.

    A build that raised warnings used to print one cheerful success line and
    leave them in the manifest. The manifest is not optional reading and the
    docs say so, but the terminal was teaching the opposite: success means
    there is nothing to look at. The one time it matters, the habit is
    already formed -- and `unique without not_null` is precisely the finding
    discovered in production, by a duplicate.

    Printed in full rather than counted. Warnings are few by construction,
    and a build that raises dozens is itself the signal.

    Silence when clean is deliberate. A "0 warnings" line on every build is
    noise that makes the non-zero case LESS visible, which is the opposite
    of the point; `test_a_clean_build_says_nothing_about_warnings` pins it.

    stderr, matching the error path: this is diagnostic output, and a
    pipeline capturing stdout wants the bundle message, not this.
    """
    warnings = [f for f in findings if f.severity == "warning"]
    if not warnings:
        return
    plural = "" if len(warnings) == 1 else "s"
    typer.echo(f"{len(warnings)} validation warning{plural}:", err=True)
    for f in warnings:
        typer.echo(f"  [WARNING] {f.detail}", err=True)


def _project_input(
    explicit: Path | None, relpath: Path, flag: str, *, from_the_project: bool = True,
) -> Path:
    """The path the operator gave, or the family standard's, or a refusal.

    `catalogue` declares where a project keeps its three inputs and
    `test_template_standard` enforces it across every shipped family,
    so inside a scaffolded project these paths are an already-proven fact
    rather than a guess. Making the operator retype them on every rebuild --
    the most repeated action in the tool, since the intended workflow is
    edit-mapping, rebuild, re-paste -- was asking for something we already
    had.

    An explicit flag always wins. A default that cannot be overridden is a
    trap, and pointing `--schema` at a scratch copy while the rest of the
    project stays put is an ordinary thing to want.

    Defaulting from a LAYOUT is safe in a way that defaulting a site URL
    would not be: being wrong here means a file that is not there, and this
    refuses. Being wrong about a target means a bundle armed for someone
    else's tenant, with only the wrong-site guard between that and a
    mispaste -- so `--site-url` stays required and is not treated the same
    way.

    The refusal names the standard path, because for anyone outside a
    project that message is the entire feature. "Missing option '--schema'"
    is true and teaches nothing.

    `from_the_project=False` withdraws the default for an input whose
    provenance is only implied by the others -- `build` passes it for
    `--release` when the schema or mapping was named explicitly. A release
    is not self-describing: nothing ties a release.yaml to the schema it
    documents, so borrowing one across projects produces confident, wrong
    provenance rather than an obviously missing one. The paths themselves
    need no such guard; they name the file they load.
    """
    if explicit is not None:
        return explicit
    if relpath.is_file() and from_the_project:
        return relpath
    if not from_the_project:
        raise typer.BadParameter(
            f"{flag} was not given. It defaults to {relpath} only when the "
            f"other inputs also come from this project, and they do not -- so "
            f"defaulting it would stamp this project's release onto somebody "
            f"else's schema. Pass {flag} explicitly.",
        )
    raise typer.BadParameter(
        f"{flag} was not given, and there is no {relpath} in the current "
        f"directory. Run this from a project directory (`dbml-sharepoint new` "
        f"creates one), or pass {flag} explicitly.",
    )


def _env_file_help() -> str:
    """The `--env-file` option's help text, with every registry key spelled
    out so the file's vocabulary is discoverable from `build --help` alone.

    Built from `ENV_SETTINGS` rather than hand-listing today's one entry, so
    a second key added to the registry is picked up here for free.
    """
    keys = "; ".join(f"{setting.key} ({setting.help})" for setting in ENV_SETTINGS)
    return (
        f"Path to a {ENV_FILENAME} defaults file. Default: {ENV_FILENAME} "
        "in the current directory, when present. A flag given on the command "
        f"line always wins over a value the file supplies. Accepted keys: {keys}"
    )


def _resolve_env_file(env_file: Path | None) -> Path | None:
    """The env file `build` should read, or None when there is nothing to.

    An explicit --env-file must exist, so a typo cannot silently build
    without the settings the operator asked for. At the default location an
    absent file is ordinary and not an error, but something present that is
    not a readable file is refused rather than treated as absent.
    """
    if env_file is not None:
        if not env_file.is_file():
            raise typer.BadParameter(f"--env-file {env_file} does not exist.")
        return env_file
    default = Path(ENV_FILENAME)
    if not default.exists():
        return None
    if not default.is_file():
        raise typer.BadParameter(
            f"{ENV_FILENAME} exists but is not a file. Remove it, or pass "
            "--env-file with the path to a real one.",
        )
    return default


def _require_known_site_role(bundle: MappingBundle, site_role: str) -> None:
    """Refuse a role the mapping does not declare.

    The vocabulary is data-driven -- the valid roles are whatever the
    entities declare, never a hardcoded list -- because a misspelled role
    would otherwise be silently filtered to an empty entity set and exit 0,
    reporting success for a build that would provision nothing.

    Shared by `build`, `report` and `validate` rather than spelled three
    times: three commands disagreeing about which roles exist is exactly
    the kind of drift that makes a `--dry-run` pass and the real build
    refuse.
    """
    known_roles = {e.site_role for e in bundle.mapping.entities.values()}
    if site_role in known_roles:
        return
    typer.echo(
        f"Invalid --site-role {site_role!r}; the mapping declares: "
        f"{', '.join(sorted(known_roles)) or '(none)'}.",
        err=True,
    )
    raise typer.Exit(code=2)


def _config_error(what: str, path: Path | None, exc: Exception) -> NoReturn:
    detail = f"missing required key {exc}" if isinstance(exc, KeyError) else str(exc)
    # `path=None` when `exc` already names the path, as every `EnvFileError`
    # does; prepending it again printed "[ERROR] env file X: X: line 3: ...".
    where = f" {path}" if path is not None else ""
    typer.echo(f"[ERROR] {what}{where}: {detail}", err=True)
    # 1, not 2. The documented contract reserves 2 for the usage errors
    # typer raises BEFORE the pipeline runs (a missing option, an unknown
    # --site-role), and gives 1 to "the build refused", which explicitly
    # includes an unreadable or invalid input file. A bad config is a
    # refused build, not a misuse of the command line, and a CI gate keying
    # on the documented table would have mis-classified it.
    raise typer.Exit(code=1) from exc


def _load_config(
    schema: Path, mapping: Path, release: Path | None,
) -> tuple[Schema, MappingBundle, Release | None]:
    """Load the three config files, reporting a bad one as a message.

    Any of these can fail on a typo in a file the operator edited by hand,
    and an unhandled exception rendered ~20 lines of loader internals above
    the single sentence saying what is wrong. The person who hits it is a
    SharePoint admin editing YAML: not one frame of that stack is
    actionable, and the semantic (post-load) errors beside it are already
    clean one-liners, so the contrast made a config typo look like a crash
    in the tool rather than a mistake in the file.

    This CLI has no verbosity flag, so the traceback is not tucked behind
    one. Inventing `--traceback` here would advertise an option the rest of
    the interface does not have.
    """
    try:
        parsed_schema = parse_dbml(schema)
    except _CONFIG_ERRORS as exc:
        _config_error("schema", schema, exc)
    try:
        bundle = load_mapping(mapping)
    except _CONFIG_ERRORS as exc:
        _config_error("mapping", mapping, exc)
    try:
        release_obj = load_release(release) if release is not None else None
    except _CONFIG_ERRORS as exc:
        _config_error("release", release, exc)
    return parsed_schema, bundle, release_obj


def _resolve_extension(
    extension: str | None, bundle: MappingBundle, mapping: Path,
) -> BaseExtension:
    """Resolve the extension name, reporting an unknown one as a message.

    `resolve_extension` raises `ValueError`, which `_CONFIG_ERRORS` already
    covers, but every call sat one line outside `_load_config`'s boundary,
    so a typo in `--extension` or in a mapping's `extension:` key reached
    the operator as a rich traceback rather than as the refusal the CLI
    prints for any other bad input. The wrapper lives here rather than
    inside `_load_config` because that helper is about reading the three
    config files, and an extension name is not one of them.
    """
    try:
        return resolve_extension(extension or bundle.mapping.extension)
    except UnknownExtensionError as exc:
        # Only the unknown name. A broken plugin, whose entry-point load or
        # constructor raises, keeps its traceback rather than being reported
        # as a typo in the operator's own mapping.
        # No `--extension` means the name came from the mapping, so name that file.
        _config_error("extension", None if extension else mapping, exc)


#: Inputs a wizard must not offer a default for. Being wrong about a target
#: means a bundle armed for someone else's tenant, with only the wrong-site
#: guard between that and a mispaste, which is why `--site-url` is required.
NO_SAFE_DEFAULT: Final = frozenset({"site_url"})


def validate_site_url(site_url: str) -> str:
    """Reject a malformed or non-https ``--site-url``, and return it cleaned.

    The URL is interpolated into the generated deploy.js.txt (as ``SITE_URL`` and in
    the site-match preflight comparison), so it must be a well-formed absolute
    ``https://`` URL with a host. Catches typos (``http://``, a bare path, a
    missing host) before the operator pastes into a privileged console. Shared
    by the core CLI and any extension project CLIs that compose it. Raises
    ``typer.BadParameter`` (exit 2) on failure.

    RETURNS the URL with any query or fragment removed, rather than refusing
    it. SharePoint's own **Copy link** puts `?web=1` on the clipboard, so the
    most common paste carried one, and nothing downstream stripped it: the
    reporting pack bakes this value into the Power Query `SiteRoot` and the
    SQLCMD `SiteUrl`, producing endpoints like
    `https://tenant/sites/X?web=1/_api/web`. Every consumer reads the value
    `execute_build` holds after this call, so cleaning it once here reaches
    all of them.

    Normalising rather than refusing follows the precedent already on this
    branch -- `_SITE_ROOT_M` trims a pasted LIST url back to the site root
    rather than making the operator edit it. But a silent rewrite of what
    somebody typed is its own defect, so the caller is expected to compare
    and say so; see `_site_url_notice`.
    """
    parsed = urlparse(site_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise typer.BadParameter(
            f"--site-url must be an absolute https:// URL with a host "
            f"(got {site_url!r}).",
        )
    if not parsed.query and not parsed.fragment:
        return site_url
    return urlunparse(parsed._replace(query="", fragment=""))


def _site_url_notice(given: str, used: str) -> str:
    """What to tell the operator when the site URL was cleaned, or "".

    A rewrite nobody is told about is indistinguishable from a rewrite that
    went wrong. Returned rather than printed so the CLI and the wizard can
    each render it in their own voice.
    """
    if given == used:
        return ""
    return (
        f"Ignoring the query or fragment on the site URL: building against "
        f"{used} rather than {given}."
    )


@dataclass(frozen=True)
class EnterpriseReaderDeclined:
    """Sentinel: the operator was asked and chose nobody.

    `execute_build`'s `enterprise_reader` parameter carries three states, not
    two -- unset (no flag, no wizard answer, ``None``), this sentinel
    (explicitly nobody), and a UPN (``str``). Only the unset state is a
    default a future ``dbml-sharepoint.env`` may fill; this one must survive
    untouched, because it is what the wizard sends for a deliberate blank
    answer at `_ask_enterprise_reader`. A bare `object()` would work at
    runtime but repr as an unreadable address; this dataclass gives it a
    name instead.
    """

    def __repr__(self) -> str:
        return "ENTERPRISE_READER_DECLINED"


#: The one instance every caller shares -- see `EnterpriseReaderDeclined`.
ENTERPRISE_READER_DECLINED: Final = EnterpriseReaderDeclined()


def validate_enterprise_reader(address: str) -> None:
    """Refuse anything that is not a plain UPN.

    The `|` check is the one doing real work. A claims login name --
    `i:0#.f|membership|svc@example.org` -- contains an `@` and would pass a
    naive check, then hand `web/ensureuser` a principal other than the user
    it appears to name. Refusing the character outright is cheaper than
    parsing claims, and no legitimate UPN contains one.
    """
    if address != address.strip() or not address:
        raise typer.BadParameter(
            "--enterprise-reader must not be empty or padded with whitespace.",
        )
    if address.count("@") != 1:
        raise typer.BadParameter(
            f"--enterprise-reader must be a single UPN with one '@' "
            f"(got {address!r}).",
        )
    if any(c.isspace() for c in address) or "|" in address:
        raise typer.BadParameter(
            f"--enterprise-reader must be a plain UPN with no whitespace and "
            f"no '|' (got {address!r}). A claims login name is not accepted.",
        )
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in address):
        raise typer.BadParameter(
            "--enterprise-reader must not contain control characters.",
        )


@app.command()
def build(
    schema: Path | None = typer.Option(
        None, help=f"Path to the DBML schema file. Default: {SCHEMA_RELPATH}",
    ),
    mapping: Path | None = typer.Option(
        None, help=f"Path to the mapping YAML. Default: {MAPPING_RELPATH}",
    ),
    release: Path | None = typer.Option(
        None, help=f"Path to release.yaml. Default: {RELEASE_RELPATH}",
    ),
    site_url: str = typer.Option(..., help="Target SharePoint site URL."),
    site_role: str = typer.Option(
        "default", help="Site role; must match a site_role declared by the mapping's entities.",
    ),
    out: Path = typer.Option(Path("./build"), help="Output directory."),
    dry_run: bool = typer.Option(False, help="Validate only; no JS output."),
    seed: bool = typer.Option(
        False,
        "--seed",
        help="Also emit demo-data.js.txt from the mapping's demo_items -- "
        f"'{DEMO_TITLE_PREFIX}'-marked sample rows pasted after deploy.js.txt.",
    ),
    enterprise_reader: str | None = typer.Option(
        None,
        help="UPN of a reporting service account to enrol, read-only, into "
        f"the mapping's enterprise-reader group. Omitted, this falls back to "
        f"{ENV_FILENAME}'s DBMLSP_ENTERPRISE_READER when that file supplies "
        "one, and otherwise enrols nobody.",
    ),
    extension: str | None = typer.Option(
        None,
        help="Extension name; overrides the mapping's `extension:` key. Resolved via entry points.",
    ),
    env_file: Path | None = typer.Option(
        None,
        "--env-file",
        help=_env_file_help(),
    ),
    deployment_log_list: str | None = typer.Option(
        None,
        "--deployment-log-list",
        help="Title of an existing list to stamp deployment start, stop and "
        "provenance rows into. Probed, never created. Default: probes "
        f"'{EXTERNAL_LOG_DEFAULT}' unless {ENV_FILENAME} names another; "
        "pass '' to disable the external stamps.",
    ),
    change_log_list: str | None = typer.Option(
        None,
        "--change-log-list",
        help="Title of the hidden change log the deploy writes type-2 "
        "rows into (old value, new value, effective window). Created if "
        f"absent, owned by marker. Default: {CHANGE_LOG_TITLE}, or what "
        f"{ENV_FILENAME} names.",
    ),
    no_sidecars: bool = typer.Option(
        False,
        "--no-sidecars",
        help="Skip both built-in sidecar lists (the run log and the change "
        "log) entirely: no lists created, no stamps, no change rows.",
    ),
) -> None:
    """Generate deploy.js.txt + manifest from the DBML schema and mapping.

    Resolves the three input paths here rather than inside `execute_build`:
    the defaults are a convenience for a person at a terminal, and
    `execute_build` is the programmatic entry point the wizard and extension
    CLIs compose. Those callers know exactly which files they mean, and a
    path that silently came from the working directory would be a surprise
    in a library call.
    """
    # The same rule `report` applies, and for a sharper reason: this command
    # emits the bundle somebody pastes into a tenant. Defaulting the release
    # is only safe when the schema and mapping came from the project too.
    # Otherwise `build --schema ../other/... --mapping ../other/...` run from
    # a project directory stamps THIS project's release tag and schema
    # version into a deploy bundle describing somebody else's schema --
    # measured at "Release tag: 1.0.0" on a bundle built from a schema whose
    # own release said 0.1.0-test. Nothing links a release.yaml to the schema
    # it describes, so the only safe inference is that all three came from
    # the same place.
    #
    # Refuses rather than skipping the stamp: a release is REQUIRED here, so
    # unlike `report` there is no unstamped mode to fall back to. That higher
    # cost is why the threshold is BOTH inputs, not either -- `report` can
    # afford `schema is None and mapping is None` because being wrong there
    # only loses a stamp, while the same rule here would outlaw pointing
    # `--schema` at a scratch copy with the rest of the project left in
    # place, which `_project_input` documents as an ordinary thing to want
    # and `test_an_explicit_path_beats_the_project_default` pins.
    #
    # One foreign input plus one from the project is the case this lets
    # through. It is the combination that mostly cannot validate anyway --
    # another project's schema against this project's mapping -- whereas
    # both-foreign is unambiguous, and is exactly what was measured.
    from_the_project = schema is None or mapping is None
    execute_build(
        schema=_project_input(schema, SCHEMA_RELPATH, "--schema"),
        mapping=_project_input(mapping, MAPPING_RELPATH, "--mapping"),
        release=_project_input(
            release, RELEASE_RELPATH, "--release", from_the_project=from_the_project,
        ),
        site_url=site_url,
        site_role=site_role,
        out=out,
        dry_run=dry_run,
        seed=seed,
        extension=extension,
        enterprise_reader=enterprise_reader,
        env_file=_resolve_env_file(env_file),
        deployment_log_list=deployment_log_list,
        change_log_list=change_log_list,
        no_sidecars=no_sidecars,
    )


def _relative_env_path(env_file: Path) -> str:
    """Render for the provenance record and the printed report: relative to
    the current directory, never absolute, so a build run on Windows and one
    run on Linux describe the same file the same way. `_resolve_env_file`
    already decided WHICH file this is; this only decides how to spell it.

    Falls back to the path as given when there is no relative form at all --
    an explicit `--env-file` on a different Windows drive than the current
    directory -- rather than letting a display nicety crash the build.
    """
    cwd = Path.cwd()
    absolute = env_file if env_file.is_absolute() else cwd / env_file
    try:
        return absolute.relative_to(cwd, walk_up=True).as_posix()
    except ValueError:
        return env_file.as_posix()


class UnwiredEnvSettingError(RuntimeError):
    """An `ENV_SETTINGS` entry whose `parameter` `_resolve_env_settings`
    does not know how to apply.

    Not a build-time failure a consumer's file can cause -- this fires only
    when a contributor adds a registry entry without also teaching
    `_resolve_env_settings` how to use it, so it is a programming error, not
    an `EnvFileError`. It is still raised rather than logged and swallowed:
    a contributor who adds the second entry gets a loud failure the moment a
    build actually exercises the key, rather than a build that succeeds
    while quietly discarding what the file asked for.
    """


def _validate_list_title(value: str, flag: str) -> None:
    """Refuse a list title that cannot survive the emitted script.

    The empty string is NOT validated here: `--deployment-log-list ''` is a
    deliberate disable, checked by the caller before this runs, and a padded
    or control-bearing variant of it still lands here and is refused.

    Titles are interpolated into `getbytitle('...')` URLs through
    `odataName`, which escapes quotes but cannot escape a newline; and a
    title padded with spaces would silently name a different list than the
    operator sees in the UI.
    """
    if not value or value != value.strip():
        raise typer.BadParameter(f"{flag} must not be empty, padded, or whitespace.")
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in value):
        raise typer.BadParameter(f"{flag} must not contain control characters.")
    if len(value) > MAX_DISPLAY_TITLE:
        raise typer.BadParameter(
            f"{flag} must be at most {MAX_DISPLAY_TITLE} characters.",
        )


def _resolve_env_settings(
    env_file: Path | None,
    enterprise_reader: str | EnterpriseReaderDeclined | None,
    deployment_log_list: str | None,
    change_log_list: str | None,
) -> tuple[str | EnterpriseReaderDeclined | None, str | None, str | None, EnvProvenance]:
    """Apply a resolved dbml-sharepoint.env file, honouring anything already
    supplied explicitly. Builds the `EnvProvenance` in the same pass that
    decides what is used, so the record can never drift from the decision it
    describes -- there is exactly one place this precedence is applied.

    Precedence: an explicit value -- a flag, or the wizard's declined
    sentinel -- always wins over the file; the file wins over the built-in
    default of nothing supplied at all.

    `env_file` is a path already resolved by the caller (`_resolve_env_file`
    for `build`); this function does no discovery of its own, only parsing.

    The two list-name settings resolve to ``None`` ONLY when neither a flag
    nor the file supplied anything (so the template can distinguish "the
    operator turned the external log off" from "nothing was said"): the
    build's own flags carry defaults, so in practice a plain build always
    names its defaults here.
    """
    if env_file is None:
        return enterprise_reader, deployment_log_list, change_log_list, NO_ENV_FILE

    try:
        file_settings, digest = read_env_file(env_file)
    except EnvFileError as exc:
        # `path=None`: the exception message already names `env_file` (every
        # `EnvFileError` does, see `_refuse` in `model/env_file.py`), so
        # passing it again here just printed it twice.
        _config_error("env file", None, exc)

    resolved_reader = enterprise_reader
    resolved_external = deployment_log_list
    resolved_change = change_log_list
    values: list[EnvValue] = []
    for setting in ENV_SETTINGS:
        file_value = file_settings.get(setting.key)
        if file_value is None:
            continue
        explicit = {
            ENTERPRISE_READER_PARAMETER: enterprise_reader,
            DEPLOYMENT_LOG_LIST_PARAMETER: deployment_log_list,
            CHANGE_LOG_LIST_PARAMETER: change_log_list,
        }
        if setting.parameter not in explicit:
            raise UnwiredEnvSettingError(
                f"{setting.key} sets execute_build's {setting.parameter!r} "
                "parameter, which _resolve_env_settings does not know how "
                "to apply. Wire it in here before adding it to ENV_SETTINGS.",
            )
        # One value per setting carries the flag through to provenance; the
        # second list setting rides the same EnvValue shape so the manifest
        # reports it identically. `wins` is the flag's value when the flag
        # was given, else None, else the file value.
        if setting.parameter == ENTERPRISE_READER_PARAMETER:
            if resolved_reader is None:
                resolved_reader = file_value
                values.append(EnvValue(setting=setting, value=file_value, used=True, override=None))
            else:
                override = (
                    resolved_reader
                    if isinstance(resolved_reader, str)
                    else repr(resolved_reader)
                )
                values.append(EnvValue(
                    setting=setting, value=file_value,
                    used=False, override=override,
                ))
        elif setting.parameter == DEPLOYMENT_LOG_LIST_PARAMETER:
            # A flag given at all (including '' = off) beats the file.
            if resolved_external is None:
                resolved_external = file_value
                values.append(EnvValue(setting=setting, value=file_value, used=True, override=None))
            else:
                values.append(EnvValue(
                    setting=setting, value=file_value,
                    used=False, override=resolved_external,
                ))
        elif setting.parameter == CHANGE_LOG_LIST_PARAMETER:
            if resolved_change is None:
                resolved_change = file_value
                values.append(EnvValue(setting=setting, value=file_value, used=True, override=None))
            else:
                values.append(EnvValue(
                    setting=setting, value=file_value,
                    used=False, override=resolved_change,
                ))

    provenance = EnvProvenance(
        path=_relative_env_path(env_file), digest=digest, values=tuple(values),
    )
    return resolved_reader, resolved_external, resolved_change, provenance


def _echo_env_provenance(provenance: EnvProvenance) -> None:
    """Say what was read, and what won. An absent line here is
    indistinguishable from a feature that did not run, so the no-file case
    is stated explicitly rather than left silent."""
    if provenance.path is None:
        typer.echo("No dbml-sharepoint.env file was read.")
        return
    typer.echo(f"Read {provenance.path} (sha256 {provenance.digest}).")
    for value in provenance.values:
        if value.used:
            typer.echo(f"  {value.setting.key} = {value.value} (from the file)")
        else:
            typer.echo(
                f"  {value.setting.key} = {value.value} (from the file; overridden, "
                f"using {value.override})",
            )


def execute_build(
    *,
    schema: Path,
    mapping: Path,
    release: Path,
    site_url: str,
    site_role: str,
    out: Path = Path("./build"),
    dry_run: bool = False,
    seed: bool = False,
    extension: str | None = None,
    enterprise_reader: str | EnterpriseReaderDeclined | None = None,
    env_file: Path | None = None,
    deployment_log_list: str | None = None,
    change_log_list: str | None = None,
    no_sidecars: bool = False,
) -> None:
    """The `build` pipeline, callable without going through typer.

    Extracted so the wizard can run exactly the same build the documented
    flags run, rather than growing a second implementation that drifts. The
    wizard is a different front end onto this, not a different builder.

    Still raises `typer.Exit` on refusal: the exit codes are the documented
    contract (2 for misuse, 1 for a refused build), and re-mapping them to
    an exception of its own here would give the wizard a second vocabulary
    for the same failures. The wizard catches it.

    `enterprise_reader` carries three states: ``None`` (unset -- no flag was
    given), `EnterpriseReaderDeclined` (the operator was asked and said
    nobody), or a UPN. `env_file`, when given, is a `dbml-sharepoint.env`
    ALREADY resolved to a path by the caller (`build` resolves the default
    location the same way it resolves `--schema`, `--mapping` and
    `--release`; this function does no discovery of its own). When the file
    supplies a value for a setting that is still unset, that value is used;
    an explicit `enterprise_reader` -- a flag or the declined sentinel --
    always wins over the file, because both mean the operator already
    decided.
    """
    # Reassigned, not merely checked: everything below -- SiteContext, the
    # manifest, and the reporting pack's `SiteRoot` and SQLCMD `SiteUrl` --
    # reads this variable, so cleaning it here is what keeps a pasted
    # `?web=1` out of every generated endpoint.
    cleaned_site_url = validate_site_url(site_url)
    if notice := _site_url_notice(site_url, cleaned_site_url):
        typer.echo(notice, err=True)
    site_url = cleaned_site_url
    parsed_schema, bundle, release_obj = _load_config(schema, mapping, release)
    if release_obj is None:  # unreachable: --release is a required option
        raise typer.BadParameter("--release is required for `build`.")
    ext = _resolve_extension(extension, bundle, mapping)

    if ext.requires_project_cli:
        typer.echo(
            f"Extension {ext.name!r} requires its project-specific CLI; "
            "the generic `dbml-sharepoint build` command cannot supply its "
            "required project inputs. Use the extension's project CLI instead.",
            err=True,
        )
        raise typer.Exit(code=2)

    _require_known_site_role(bundle, site_role)

    enterprise_reader, resolved_external, resolved_change, env_provenance = _resolve_env_settings(
        env_file, enterprise_reader, deployment_log_list, change_log_list,
    )
    _echo_env_provenance(env_provenance)
    # Post-resolution defaults, and the three states the external log name
    # carries. Nothing said anywhere -- no flag, no file -- means the
    # built-in sidecar names, applied AFTER precedence so a file naming
    # another list is a plain "used", never an override of a default the
    # operator never gave. The defaults themselves carry no provenance:
    # nothing was decided, so nothing is reported.
    #
    # The empty string is the DOCUMENTED DISABLE for the external log (flag
    # or file) and must survive as a state of its own: collapsing it to
    # None here would let the default below put the probe straight back.
    # A padded variant is not the disable and is refused by the title
    # validation, so nothing invisible can turn the feature off.
    if resolved_external is not None and resolved_external != "":
        _validate_list_title(resolved_external, "--deployment-log-list")
    if resolved_change is not None:
        _validate_list_title(resolved_change, "--change-log-list")
    external_log = (
        EXTERNAL_LOG_DEFAULT
        if resolved_external is None
        else resolved_external  # '' stays '' (off); a title stays itself
    )
    change_log = resolved_change if resolved_change is not None else CHANGE_LOG_TITLE

    # `isinstance`, not `is not None`: the declined sentinel means nobody is
    # enrolled and must skip validation and the group check just as `None` does.
    if isinstance(enterprise_reader, str):
        validate_enterprise_reader(enterprise_reader)
        perms = bundle.mapping.permissions
        targets = [
            g for g in (perms.groups if perms else [])
            if g.enroll_enterprise_reader
        ]
        if not targets:
            # Fail closed rather than emitting a bundle that quietly enrols
            # nobody. The operator would not find out until a report came
            # back short, weeks later. `MULTIPLE_ENTERPRISE_READER_GROUPS`
            # (a validator rule) already refuses more than one such group,
            # so there is nothing to re-check on that side here.
            raise typer.BadParameter(
                "--enterprise-reader was given but the mapping declares no "
                "group with enroll_enterprise_reader: true.",
            )

    # Everything above this line is a pure read that can refuse: a malformed
    # URL, an unreadable input file, an extension needing its own CLI, a role
    # the mapping does not declare. None of them has made anything in `out`
    # stale, and `--out` is routinely the directory holding the bundle the
    # operator is part-way through pasting -- so a refusal that learnt nothing
    # must not destroy it. `report` has always drawn the line here; `build`
    # used to clear as its first statement and disagreed.
    #
    # From here the build is committed to writing, so every later refusal DOES
    # clear. That is what the guarantee is actually for: a `deploy.js.txt`
    # describing a schema this run rejected is the stale script an operator
    # could paste.
    clear_generated(out, reporting=True)

    findings = validate_all(parsed_schema, bundle, ext)
    errors = [f for f in findings if f.severity == "error"]

    site_context = SiteContext(
        site_url=site_url,
        site_role=site_role,
        release=release_obj,
        output_dir=out,
        extension_args={},
    )

    # Only render the schema view when the schema is valid: build_schema_json
    # calls map_column(), which raises on unsupported/legacy types that
    # validate() already flags. On error we still emit a manifest documenting
    # the findings (using an empty schema view), then abort below.
    schema_json = (
        _EMPTY_SCHEMA_JSON
        if errors
        else build_schema_json(
            parsed_schema,
            bundle,
            site_role,
            site_url=site_url,
            release=release_obj,
            extension=ext,
            site_context=site_context,
        )
    )

    generated_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    source_mtime = dt.datetime.fromtimestamp(
        schema.stat().st_mtime, dt.UTC,
    ).isoformat(timespec="seconds")

    # Narrowed here rather than by reassigning the parameter above, which
    # would erase the unset/declined distinction before anything consumes it.
    resolved_enterprise_reader = (
        enterprise_reader if isinstance(enterprise_reader, str) else None
    )

    manifest_md = generate_manifest(
        schema_json=schema_json,
        findings=findings,
        bundle=bundle,
        release=release_obj,
        site_url=site_url,
        site_role=site_role,
        source_dbml=schema.name,
        source_mtime=source_mtime,
        generated_at=generated_at,
        manifest_extras=ext.manifest_extras(bundle, parsed_schema),
        # The manifest is read BEFORE the paste, so this is where the
        # permanent-membership warning has to be. Rendered even on the
        # error path below: a build that refuses still writes a manifest,
        # and the operator reading it should see what the flag would have
        # done once the errors are fixed.
        enterprise_reader=resolved_enterprise_reader,
        env_provenance=env_provenance,
        sidecar_run_log_title=None if no_sidecars else "dbml Local Log",
        sidecar_change_log_title=None if no_sidecars else change_log,
        deployment_log_list=external_log or "",
    )
    write_artifact(out / "deploy-manifest.md", manifest_md)

    if errors:
        typer.echo(f"Validation produced {len(errors)} error(s); aborting JS generation.", err=True)
        for f in errors:
            typer.echo(f"  [ERROR] {f.detail}", err=True)
        # Warnings too, before the exit. A build that refuses has ALSO found
        # everything else wrong with the mapping, and printing only the
        # errors hides that until the errors are fixed -- so the operator
        # fixes, rebuilds, and meets a second list they could have seen the
        # first time. This is the one path where suppressing them costs an
        # extra round trip rather than nothing.
        _echo_warnings(findings)
        raise typer.Exit(code=1)

    if dry_run:
        typer.echo(f"Dry run complete. Manifest written to {out / 'deploy-manifest.md'}.")
        _echo_warnings(findings)
        return

    try:
        message = emit_bundle(
            out,
            schema=parsed_schema,
            mapping_bundle=bundle,
            release=release_obj,
            site_url=site_url,
            site_role=site_role,
            schema_name=schema.name,
            mapping_name=mapping.name,
            source_mtime=source_mtime,
            generated_at=generated_at,
            seed=seed,
            extension=ext,
            site_context=site_context,
            enterprise_reader=resolved_enterprise_reader,
            env_provenance=env_provenance,
            deployment_log_list=external_log or "",
            change_log_list=None if no_sidecars else change_log,
            no_sidecars=no_sidecars,
        )
    except SeedRequiresDemoItemsError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2) from exc
    typer.echo(message)
    _echo_warnings(findings)


@app.command()
def validate(
    schema: Path | None = typer.Option(
        None, help=f"Path to the DBML schema file. Default: {SCHEMA_RELPATH}",
    ),
    mapping: Path | None = typer.Option(
        None, help=f"Path to the mapping YAML. Default: {MAPPING_RELPATH}",
    ),
    site_role: str = typer.Option(
        "default",
        help="Site role; must match one the mapping declares. Does NOT narrow "
             "what is checked -- validation is always project-wide.",
    ),
    extension: str | None = typer.Option(
        None,
        help="Extension name; overrides the mapping's `extension:` key. Resolved via entry points.",
    ),
) -> None:
    """Check the schema and mapping. No site URL, no output, no release.

    `validate_all` takes a schema, a mapping bundle and an extension --
    not a site URL and not a release. Answering "is this correct?" through
    `build --dry-run` therefore cost an invented tenant URL, on the tightest
    loop in the tool: edit the mapping, check, edit again.

    Deliberately NOT the same thing as `build --dry-run`, which keeps its
    contract unchanged. The two answer different questions:

    * `validate` -- is my schema and mapping correct?
    * `build --dry-run` -- what would this build do against that site,
      without emitting JS?

    The second is a run sheet for a named target. `deploy-manifest.md` does
    not merely stamp the site URL in a header; step 3 of its run sequence
    sends the operator to `<site_url>/_layouts/15/settings.aspx`. Rendering
    that with a not-supplied marker would produce an artifact whose own
    instructions are fiction, which is why this command writes no manifest
    rather than `--dry-run` learning to omit the target.

    Writes nothing at all, and takes no `--out`. A question, not an artifact.

    `--site-role` does NOT scope the check, and must not. `validate_all`
    takes no role and `build` calls it identically, so validation has always
    been project-wide -- this reports exactly what a build would. Narrowing
    it would hide an error under `admin` from anyone validating `default`,
    which means the mapping reads clean until the deploy that breaks. The
    flag's job here is to reject a role the mapping does not declare, moving
    a typo's discovery earlier. Pinned by
    `test_validate_checks_every_role_not_just_the_selected_one`.
    """
    schema = _project_input(schema, SCHEMA_RELPATH, "--schema")
    mapping = _project_input(mapping, MAPPING_RELPATH, "--mapping")
    parsed_schema, bundle, _ = _load_config(schema, mapping, None)
    ext = _resolve_extension(extension, bundle, mapping)
    _require_known_site_role(bundle, site_role)

    findings = validate_all(parsed_schema, bundle, ext)
    for f in findings:
        typer.echo(f"  [{f.severity.upper()}] {f.code}: {f.message}", err=True)

    errors = sum(1 for f in findings if f.severity == "error")
    warnings = len(findings) - errors
    typer.echo(
        f"{schema}: {errors} error(s), {warnings} warning(s).",
        err=errors > 0,
    )
    if errors:
        raise typer.Exit(code=1)


@app.command()
def explain(
    code: str = typer.Argument(
        "",
        help="A finding code, as printed beside a build's findings. "
        "Omit to list every code.",
    ),
) -> None:
    """Say what a finding code means, without leaving the terminal.

    The code is a finding's identity -- stable, and what the catalogue is
    keyed by -- while the message beside it is prose that may be reworded in
    any release. So the code is the only part worth looking up, and until
    now the only place to look it up was a website.

    Reads `FINDING_HELP`, which ships inside the package. The published
    reference at `reference/findings.md` is generated from the same data, so
    the two cannot disagree.
    """
    if not code:
        for member in sorted(FINDING_HELP):
            typer.echo(f"  {member.severity:<7}  {member}")
        typer.echo(
            f"\n{len(FINDING_HELP)} codes. "
            "Run `dbml-sharepoint explain <code>` for any one of them.",
        )
        return

    # Tolerate the token exactly as a build prints it. Findings render as
    # `[ERROR] unknown_column_type: schema[Project].Sponsor: ...`, and the obvious
    # thing to do is select the code and paste it -- which brings the colon.
    wanted = code.strip().rstrip(":").lower()
    found = next((c for c in FINDING_HELP if str(c) == wanted), None)
    if found is None and wanted in RETIRED_FINDINGS:
        # A code an older build printed stays answerable after its rule goes.
        typer.echo(f"{wanted}  [retired]\n")
        for line in wrap(RETIRED_FINDINGS[wanted], width=76):
            typer.echo(line)
        return
    if found is None:
        near = get_close_matches(wanted, [str(c) for c in FINDING_HELP], n=3, cutoff=0.6)
        suggestion = f" Did you mean: {', '.join(near)}?" if near else ""
        typer.echo(
            f"No finding code {wanted!r}.{suggestion}\n"
            "Run `dbml-sharepoint explain` with no argument to list them all.",
            err=True,
        )
        raise typer.Exit(code=2)

    # Severity off the code, meaning off the catalogue: the two facts have
    # one home each, and this is just the place they are printed together.
    typer.echo(f"{found}  [{found.severity}]\n")
    for line in wrap(FINDING_HELP[found], width=76):
        typer.echo(line)


@app.command()
def report(
    schema: Path | None = typer.Option(
        None, help=f"Path to the DBML schema file. Default: {SCHEMA_RELPATH}",
    ),
    mapping: Path | None = typer.Option(
        None, help=f"Path to the mapping YAML. Default: {MAPPING_RELPATH}",
    ),
    site_role: str = typer.Option(
        "default", help="Site role; must match a site_role declared by the mapping's entities.",
    ),
    out: Path = typer.Option(Path("./reports"), help="Output directory."),
    release: Path | None = typer.Option(
        None,
        help="Optional release.yaml; stamps release metadata into "
        f"data-dictionary.md. Default: {RELEASE_RELPATH} when it exists.",
    ),
) -> None:
    """Generate reporting queries (Power Query M + SQL views) from the schema.

    Emits one .pq file per list, a SQLCMD views script, guide.md with
    usage instructions and the Power BI relationship table, and a
    data-dictionary.md companion. Assumes a schema that `build` accepts;
    run `build --dry-run` first if unsure.
    """
    # Whether this run is reporting on the project in the working directory,
    # or on files somebody named explicitly. It decides the release default
    # below, so it has to be read BEFORE the paths are resolved.
    from_the_project = schema is None and mapping is None

    schema = _project_input(schema, SCHEMA_RELPATH, "--schema")
    mapping = _project_input(mapping, MAPPING_RELPATH, "--mapping")
    # Not through `_project_input`: this option is genuinely optional and its
    # absence is a supported mode (an unstamped dictionary), so a missing
    # release.yaml must not refuse the way a missing schema does. Picking it
    # up when it IS there means running `report` inside a project stamps the
    # provenance it could always have had.
    #
    # Only when the schema and mapping came from the project too. Otherwise
    # `report --schema ../other/schema.dbml --mapping ../other/mapping.yaml`
    # run from a project directory would stamp THIS project's release tag and
    # schema version onto a data dictionary describing somebody else's
    # schema -- provenance that is not merely missing but wrong, and wrong in
    # a way the output looks confident about. Nothing links a release.yaml to
    # the schema it describes, so the only safe inference is that all three
    # came from the same place.
    if release is None and from_the_project and RELEASE_RELPATH.is_file():
        release = RELEASE_RELPATH
    parsed_schema, bundle, release_obj = _load_config(schema, mapping, release)

    _require_known_site_role(bundle, site_role)

    generated_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    dictionary_kwargs: dict[str, Any] = dict(
        release=release_obj,
        generated_at=generated_at,
        source_schema=schema.name,
        source_mapping=mapping.name,
    )

    # Render everything before writing anything. This command does not
    # validate, documenting the contract as "assumes a schema that `build`
    # accepts", so the generators are the first thing to meet a schema
    # mistake, and they signal one by raising: an unmapped column type, a
    # composite DBML index. Unhandled, that printed a traceback for a typo
    # in a file the operator hand-edited, which is exactly what
    # `_config_error` exists to prevent on the loading side. Generating up
    # front also keeps a failure from leaving a half-written report set
    # behind, where the stale files outlive the error on the terminal.
    try:
        queries = generate_powerquery(parsed_schema, bundle, site_role)
        queries.update(
            generate_dictionary_powerquery(
                parsed_schema, bundle, site_role, **dictionary_kwargs,
            ),
        )
        views_sql = (
            generate_sql_views(parsed_schema, bundle, site_role)
            + "\n"
            + generate_dictionary_sql(
                parsed_schema, bundle, site_role, **dictionary_kwargs,
            )
        )
        reporting_md = generate_reporting_md(parsed_schema, bundle, site_role)
        dictionary_md = generate_data_dictionary(
            parsed_schema, bundle, site_role, **dictionary_kwargs,
        )
    except ValueError as exc:
        # The schema was read and refused, so whatever is in `out` describes
        # a schema that no longer exists. Clear it rather than leave a stale
        # set looking current. Only reachable once the config loaded and the
        # role resolved: a mistyped --schema path or an unknown --site-role
        # never learns anything about the report, and must not destroy the
        # last good one on its way out.
        _clear_report_output(out)
        typer.echo(
            f"[ERROR] schema {schema}: {exc}\n"
            "Run `build --dry-run` for the full validation report.",
            err=True,
        )
        raise typer.Exit(code=1) from exc

    # Drop the previous set so a list removed from the schema does not leave
    # its .pq file behind, outliving the schema that justified it.
    _clear_report_output(out)

    pq_dir = out / "powerquery"
    sql_dir = out / "sql"
    pq_dir.mkdir(parents=True, exist_ok=True)
    sql_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in queries.items():
        write_artifact(pq_dir / filename, content)
    write_artifact(sql_dir / REPORT_VIEWS_SQL, views_sql)
    write_artifact(out / REPORT_GUIDE, reporting_md)
    write_artifact(out / REPORT_DICTIONARY, dictionary_md)
    typer.echo(
        f"Generated {len(queries)} Power Query file(s), sql/{REPORT_VIEWS_SQL}, "
        f"{REPORT_GUIDE} and {REPORT_DICTIONARY} in {out}.",
    )


@app.command("extract-script")
def extract_script(
    url: str = typer.Argument(
        ...,
        help="The list's URL, copied from the browser address bar with the "
        "list open, e.g. https://contoso.sharepoint.com/sites/Risk/Lists/"
        "RG_Project/AllItems.aspx",
    ),
    out: Path | None = typer.Option(
        None,
        help="Where to write the script, with the readme beside it. Default: "
        f"<list name>/{EXTRACT_SCRIPT}",
    ),
) -> None:
    """Generate the read-only browser-paste script that reads a live list.

    Takes the whole list URL, because that is the one string the browser
    address bar already holds: the site and the list title are split out of
    it rather than asked for separately. One list per script.

    The script and a readme are written into a folder named after the list,
    which is where `dbml-sharepoint extract` then writes the draft schema
    and mapping, so both halves of the flow keep one directory.

    Paste the emitted file into the browser console on that site. It
    downloads the list's field definitions as JSON; feed that JSON to
    `dbml-sharepoint extract` to get a draft schema and mapping.

    Every request the script makes is a GET. It carries no write helpers.
    """
    try:
        target = parse_list_url(url)
    except ListUrlError as exc:
        raise typer.BadParameter(str(exc)) from exc
    # Still asked of `validate_site_url`, which owns what a usable site URL
    # is, so the split half meets the same rule an operator-typed one does.
    used = validate_site_url(target.site_url)

    generated_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    seeded = seed(
        list_title=target.list_title,
        list_path=target.list_path,
        site_url=used,
        generated_at=generated_at,
        script=out,
    )
    typer.echo(f"Reading the list at {target.list_path!r} on {used}.")
    typer.echo(
        f"Wrote {seeded.script}. Open it, copy all of it, and paste it into the "
        f"browser console on {used}. It makes no changes.",
    )
    if seeded.readme is not None:
        typer.echo(f"Wrote {seeded.readme}, which has the rest of the procedure.")
    else:
        typer.echo(f"Left the {README_FILENAME} already in {seeded.folder} alone.")
    download = download_name([target.list_title])
    typer.echo(
        f"The script downloads {download}. Save it into {seeded.folder}, then "
        f"run: dbml-sharepoint extract {seeded.folder / download}",
    )



_LIST_URL_HELP = (
    "The list's URL, copied from the browser address bar with the list open, "
    "e.g. https://contoso.sharepoint.com/sites/Risk/Lists/RG_Project/AllItems.aspx"
)


def _maintenance_script(
    url: str,
    out: Path | None,
    *,
    script_name: str,
    render: Callable[..., str],
    does: str,
) -> None:
    """Write one list-maintenance script from a pasted list URL.

    The site and the list's server-relative path are split out of the one
    string the address bar holds, then the site half meets the same rule an
    operator-typed `--site-url` does.

    THE SCRIPT RESOLVES BY PATH, NOT BY THE SLUG. A list renamed in place
    keeps the slug it was created with, so on any site that has been through a
    `renamed_from` migration the slug is not the list's title and a by-title
    script 404s on its first read. The slug still names the output folder,
    which is where `extract-script` writes too, so one list's scripts stay
    together.
    """
    try:
        target = parse_list_url(url)
    except ListUrlError as exc:
        raise typer.BadParameter(str(exc)) from exc
    used = validate_site_url(target.site_url)
    generated_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    path = out if out is not None else folder_for(target.list_title) / script_name
    write_artifact(path, render(
        site_url=used, list_title=target.list_title,
        list_path=target.list_path, generated_at=generated_at,
    ))
    # The PATH is echoed, because that is what the script resolves and what an
    # operator can check against the address bar. Its title may differ.
    typer.echo(f"Wrote {path} for the list at {target.list_path!r} on {used}.")
    typer.echo(
        "Open it, copy all of it, and paste it into the browser console on "
        f"{used} from a classic page such as _layouts/15/settings.aspx. It {does}",
    )


@app.command("protection-script")
def protection_script(
    url: str = typer.Argument(..., help=_LIST_URL_HELP),
    out: Path | None = typer.Option(
        None, help=f"Where to write the script. Default: <list name>/{PROTECTION_SCRIPT}",
    ),
) -> None:
    """Generate the browser-paste script that locks, unlocks, seals or unseals one list.

    The script prints the list's deletion lock and the Sealed flag on each
    custom column, then takes one word at a time: lock or unlock sets
    AllowDeletion, seal or unseal sets Sealed on every custom column not
    already in that state. Every write is read back, and a readback that
    disagrees stops the run. It deletes nothing.
    """
    _maintenance_script(
        url, out, script_name=PROTECTION_SCRIPT, render=generate_protection_js,
        does="prompts for each action and reads every write back.",
    )


@app.command("columns-script")
def columns_script(
    url: str = typer.Argument(..., help=_LIST_URL_HELP),
    out: Path | None = typer.Option(
        None, help=f"Where to write the script. Default: <list name>/{COLUMNS_SCRIPT}",
    ),
) -> None:
    """Generate the browser-paste script that enumerates and deletes one list's custom columns.

    The script prints the custom columns and asks for one by internal name,
    never by position. Built-in and hidden fields never appear. Every item is
    read to see whether the column holds a value: an empty column needs its
    internal name typed again after that scan, and one with values, or whose
    values cannot be read, needs
    DELETE NON-EMPTY typed. A sealed column is unsealed and read back before
    the delete, and the column is read back after it and must be gone. The
    table is printed again after each delete; a blank answer finishes.

    Deleting a column removes its values from every item, and nothing goes
    to the recycle bin.
    """
    _maintenance_script(
        url, out, script_name=COLUMNS_SCRIPT, render=generate_columns_js,
        does="asks for a typed confirmation before every delete.",
    )


@app.command()
def extract(
    source: Path | None = typer.Argument(
        None,
        help="The JSON extract.js.txt downloaded from the site. Omit it to be "
        "walked through the whole flow, starting from the list's URL.",
    ),
    out: Path | None = typer.Option(
        None,
        help="Project directory to write into. Default: a folder named after "
        "the list, which is the one extract-script wrote the script into.",
    ),
    entity: str | None = typer.Option(
        None,
        help="DBML table name for the extracted list. Default: derived from the "
        "list title. Only valid when the source describes one list.",
    ),
    prefix: str = typer.Option(
        DEFAULT_PREFIX,
        help="The mapping's list-name prefix. An extraction cannot know the "
        f"deploying project's, so it defaults to {DEFAULT_PREFIX!r}.",
    ),
    project: str | None = typer.Option(
        None, help="DBML Project name. Default: the first entity name, lowercased.",
    ),
    force: bool = typer.Option(
        False, help="Overwrite an existing schema.dbml, mapping.yaml or release.yaml.",
    ),
) -> None:
    """Recover a draft schema.dbml and mapping.yaml from an existing list.

    Takes the JSON `dbml-sharepoint extract-script` produced and you pasted
    into the browser console. That read is the only input; nothing here is
    recovered from an export.

    With no argument it runs interactively instead, asking for the list's
    URL, writing the script, waiting while you paste it, and extracting the
    download when you say it has landed. The same two commands do the work
    either way.

    This is a SCAFFOLDING tool, not a lossless round-trip. What the read
    carries is recovered; everything else is itemised in the
    EXTRACTION-NOTES.md written beside the output. Read that file before
    editing the schema, and again before deploying anything.
    """
    if source is None:
        if out is not None:
            raise typer.BadParameter(
                "--out has no download to write from. Name the JSON to "
                "extract, or drop --out and be asked for the list's URL; the "
                "interactive flow always writes into the list's own folder.",
            )
        if not stdin_is_interactive():
            # Same rule the wizard callback applies: never block on a prompt
            # nobody can answer. A pipe or a CI job that ran `extract` with no
            # argument meant to name a file, so this is a usage error rather
            # than a help screen.
            typer.echo(
                "[ERROR] no download named, and there is no terminal to ask "
                "at. Pass the JSON that extract.js.txt downloaded.",
                err=True,
            )
            raise typer.Exit(code=2)
        raise typer.Exit(code=run_extract_wizard(
            entity=entity, prefix=prefix, project=project, force=force,
        ))
    execute_extraction(
        source, out=out, entity=entity, prefix=prefix, project=project, force=force,
    )


def execute_extraction(
    source: Path,
    *,
    out: Path | None = None,
    entity: str | None = None,
    prefix: str = DEFAULT_PREFIX,
    project: str | None = None,
    force: bool = False,
) -> None:
    """One extraction, from a download to a written project directory.

    Shared by the `extract` command and the interactive flow, for the same
    reason `execute_build` is shared with the template wizard: the wizard
    must not be able to produce anything the documented flags could not.
    Refusals leave through `typer.Exit`, which both callers understand.
    """
    try:
        loaded = load_source(source)
    except _CONFIG_ERRORS as exc:
        _config_error("extraction source", source, exc)

    if entity is not None and len(loaded.lists) > 1:
        raise typer.BadParameter(
            f"--entity names one table, but the source describes "
            f"{len(loaded.lists)} lists. Extract them one at a time, or drop "
            "the flag and let each be named from its list title.",
        )
    try:
        entity_names = {
            source_list.title: (
                check_identifier(entity, "--entity")
                if entity is not None
                else entity_name_for(source_list.title)
            )
            for source_list in loaded.lists
        }
        extraction = extraction_from(loaded, entity_names=entity_names)
    except _CONFIG_ERRORS as exc:
        _config_error("extraction source", source, exc)

    if project is not None:
        check_identifier(project, "--project")
    # The FIRST list's title. A download this tool generates carries exactly
    # one, and a hand-assembled one carrying several has no single folder it
    # could be named after; `--out` is the answer there.
    root = out if out is not None else folder_for_download(
        source, loaded.lists[0].title,
    )
    _refuse_existing_project(root, force=force)

    generated_at = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    written = write_extraction(
        extraction,
        root,
        generated_at=generated_at,
        prefix=prefix,
        project=project or "",
    )

    columns = sum(len(e.columns) for e in extraction.entities)
    # A run from inside the list's own folder derives `.` as its root, and
    # "into ." names nothing. Resolve that one case.
    destination = written.root if written.root.name else written.root.resolve()
    typer.echo(
        f"Extracted {len(extraction.entities)} list(s), {columns} column(s) and "
        f"{len(extraction.enums)} enum(s) from {loaded.kind} into {destination}",
    )
    typer.echo(f"  {written.schema}\n  {written.mapping}\n  {written.release}")
    for path in written.preserved:
        typer.echo(f"  {path}")
    typer.echo(
        f"\n{len(extraction.unrecovered)} thing(s) could not be recovered. "
        f"Read {written.notes} before you edit or deploy anything.",
    )


def _refuse_existing_project(out: Path, *, force: bool) -> None:
    """Refuse to write over a project that is already there.

    Applied to the derived default directory as well as to an explicit
    `--out`: one folder per list makes a second run of the same extraction
    land on the first one's output, which is where a hand-edited schema
    would be lost. An extraction produces a DRAFT, so
    overwriting real work with one is the worst outcome this command has;
    it is refused by name rather than guarded by a prompt, because the
    command must behave the same in a pipe.
    """
    if force:
        return
    present = [
        out / relpath
        for relpath in (SCHEMA_RELPATH, MAPPING_RELPATH, RELEASE_RELPATH, NOTES_RELPATH)
        if (out / relpath).exists()
    ]
    if not present:
        return
    typer.echo(
        "[ERROR] refusing to overwrite an existing project. These already "
        "exist:\n" + "\n".join(f"  {path}" for path in present)
        + "\nPass --out with an empty directory, or --force to overwrite them.",
        err=True,
    )
    raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Print the deployer version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
