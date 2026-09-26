"""The project's inputs: finding them, loading them, and refusing a bad one.

Everything here is what a command needs BEFORE it can do anything: the three
config files, the extension a mapping declares, the site facts that name a
target, and the `dbml-sharepoint.env` defaults file. Split out of `cli.py` so
`wizard.py` can borrow the same validators without importing the module that
imports it, which was a real cycle rather than a lazy-loading choice (#171).

Refusals are still `typer` exceptions. The exit codes are the documented
contract -- 2 for misuse, 1 for a refused build -- and a second vocabulary
for the same failures would have to be translated back at every call site.
"""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, NoReturn
from urllib.parse import urlparse, urlunparse

import typer
import yaml
from pyparsing.exceptions import ParseBaseException

from dbml_sharepoint.analysis.limits import MAX_DISPLAY_TITLE
from dbml_sharepoint.analysis.timezones import is_known_zone, unknown_zone_message
from dbml_sharepoint.extension import (
    DeploymentExtension,
    UnknownExtensionError,
    resolve_extension,
)
from dbml_sharepoint.model.env_file import (
    CHANGE_LOG_LIST_PARAMETER,
    DEPLOYMENT_CHANGE_LOG_LIST_PARAMETER,
    DEPLOYMENT_LOG_LIST_PARAMETER,
    DEPLOYMENT_LOG_SITE_PARAMETER,
    ENTERPRISE_READER_PARAMETER,
    ENV_FILENAME,
    ENV_SETTINGS,
    NO_ENV_FILE,
    TIME_ZONE_KEY,
    TIME_ZONE_PARAMETER,
    EnvFileError,
    EnvProvenance,
    EnvValue,
    read_env_file,
)
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import MappingBundle
from dbml_sharepoint.model.parser import Schema, parse_dbml
from dbml_sharepoint.model.release import Release, load_release

# A bad config file fails as one of these. Deliberately not `Exception`:
# an unexpected error is a bug in the tool and must keep its traceback.
CONFIG_ERRORS = (ValueError, KeyError, OSError, yaml.YAMLError, ParseBaseException)


def config_error(what: str, path: Path | None, exc: Exception) -> NoReturn:
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


def load_config(
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
    except CONFIG_ERRORS as exc:
        config_error("schema", schema, exc)
    try:
        bundle = load_mapping(mapping)
    except CONFIG_ERRORS as exc:
        config_error("mapping", mapping, exc)
    try:
        release_obj = load_release(release) if release is not None else None
    except CONFIG_ERRORS as exc:
        config_error("release", release, exc)
    return parsed_schema, bundle, release_obj


def resolve_extension_or_refuse(
    extension: str | None, bundle: MappingBundle, mapping: Path,
) -> DeploymentExtension:
    """Resolve the extension name, reporting an unknown one as a message.

    `resolve_extension` raises `ValueError`, which `CONFIG_ERRORS` already
    covers, but every call sat one line outside `load_config`'s boundary,
    so a typo in `--extension` or in a mapping's `extension:` key reached
    the operator as a rich traceback rather than as the refusal the CLI
    prints for any other bad input. The wrapper lives here rather than
    inside `load_config` because that helper is about reading the three
    config files, and an extension name is not one of them.
    """
    try:
        return resolve_extension(extension or bundle.mapping.extension)
    except UnknownExtensionError as exc:
        # Only the unknown name. A broken plugin, whose entry-point load or
        # constructor raises, keeps its traceback rather than being reported
        # as a typo in the operator's own mapping.
        # No `--extension` means the name came from the mapping, so name that file.
        config_error("extension", None if extension else mapping, exc)


def project_input(
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


def require_known_site_role(bundle: MappingBundle, site_role: str) -> None:
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
    and say so; see `site_url_notice`.
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


def site_url_notice(given: str, used: str) -> str:
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


#: Where an operator finds the site's zone, and how to spell it. Shared by
#: the two refusals below so they send people to the same place.
_HOW_TO_FIND_THE_ZONE = (
    "The site's zone is under Site settings > Regional settings > Time zone, "
    "which names a city; pass that city's IANA name, such as "
    "Australia/Melbourne or Europe/London. Python lists every name with "
    "`python -c \"import zoneinfo; print(sorted(zoneinfo.available_timezones()))\"`."
)


def validate_time_zone(time_zone: str) -> str:
    """Refuse a ``--time-zone`` the IANA database does not declare.

    The reporting pack derives the site's daylight-saving transitions from
    the name, so a name the database does not declare has nothing to derive
    from, and a name that is merely close (`Melbourne`, `australia/melbourne`)
    is refused with the spelling it probably meant rather than guessed at.
    Shared by `build`, `report` and the wizard, so the three cannot come to
    disagree about what a usable zone is. Raises ``typer.BadParameter``
    (exit 2) on failure, the same contract as `validate_site_url`.

    Returned unchanged when it passes: nothing about a zone name needs
    cleaning, and a silent rewrite of what somebody typed is the defect
    `site_url_notice` exists to report.
    """
    if is_known_zone(time_zone):
        return time_zone
    raise typer.BadParameter(
        f"--time-zone: {unknown_zone_message(time_zone)} {_HOW_TO_FIND_THE_ZONE}",
    )


def missing_time_zone() -> typer.BadParameter:
    """The refusal for a run that named no zone anywhere.

    Not a typer-level required option, because `dbml-sharepoint.env` may
    supply it (`DBMLSP_TIME_ZONE`), so "required" here means "required
    after the file has been read". A run that reached this far has been
    told nothing about the site's zone, and the pack cannot convert a
    timestamp by a zone it was never given. Shared by `build` and `report`,
    which read the zone the same way.
    """
    return typer.BadParameter(
        f"--time-zone is required: the reporting pack converts every "
        f"timestamp by the site's time zone, and a zone is a fact about the "
        f"site rather than the mapping, so it has to be given. Pass "
        f"--time-zone, or set {TIME_ZONE_KEY} in {ENV_FILENAME}. "
        f"{_HOW_TO_FIND_THE_ZONE}",
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


def resolve_env_file(env_file: Path | None) -> Path | None:
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


def _relative_env_path(env_file: Path) -> str:
    """Render for the provenance record and the printed report: relative to
    the current directory, never absolute, so a build run on Windows and one
    run on Linux describe the same file the same way. `resolve_env_file`
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
    """An `ENV_SETTINGS` entry whose `parameter` `resolve_env_settings`
    does not know how to apply.

    Not a build-time failure a consumer's file can cause -- this fires only
    when a contributor adds a registry entry without also teaching
    `resolve_env_settings` how to use it, so it is a programming error, not
    an `EnvFileError`. It is still raised rather than logged and swallowed:
    a contributor who adds the second entry gets a loud failure the moment a
    build actually exercises the key, rather than a build that succeeds
    while quietly discarding what the file asked for.
    """


def validate_list_title(value: str, flag: str) -> None:
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


def validate_site_name(value: str, flag: str) -> None:
    """Refuse a central-logging SITE name that cannot address a web.

    A site name is not a list title: it is the last segment of
    `/sites/<name>`, interpolated by `crossWebApi`, so the display-title
    length limit is the wrong rule and a space is fatal rather than merely
    confusing. What matters is that the segment stays one segment -- a
    leading or trailing slash would produce `/sites//name` or a trailing
    empty segment, and an embedded slash would silently address a different
    web than the operator named.

    The empty string is NOT validated here: `--deployment-log-site ''` is the
    documented disable, checked by the caller before this runs.
    """
    if not value or value != value.strip():
        raise typer.BadParameter(f"{flag} must not be empty, padded, or whitespace.")
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in value):
        raise typer.BadParameter(f"{flag} must not contain control characters.")
    if any(c.isspace() for c in value):
        raise typer.BadParameter(
            f"{flag} names a site's URL segment, which contains no spaces "
            f"(got {value!r}). Use the name as it appears in /sites/<name>.",
        )
    if value.startswith("/") or value.endswith("/"):
        raise typer.BadParameter(
            f"{flag} must be the site's name alone, with no leading or "
            f"trailing '/' (got {value!r}).",
        )


def resolve_env_settings(
    env_file: Path | None,
    enterprise_reader: str | EnterpriseReaderDeclined | None,
    deployment_log_list: str | None,
    deployment_log_change_list: str | None,
    deployment_log_site: str | None,
    change_log_list: str | None,
    time_zone: str | None,
) -> tuple[
    str | EnterpriseReaderDeclined | None,
    str | None, str | None, str | None, str | None, str | None,
    EnvProvenance,
]:
    """Apply a resolved dbml-sharepoint.env file, honouring anything already
    supplied explicitly. Builds the `EnvProvenance` in the same pass that
    decides what is used, so the record can never drift from the decision it
    describes -- there is exactly one place this precedence is applied.

    Precedence: an explicit value -- a flag, or the wizard's declined
    sentinel -- always wins over the file; the file wins over the built-in
    default of nothing supplied at all.

    `env_file` is a path already resolved by the caller (`resolve_env_file`
    for `build`); this function does no discovery of its own, only parsing.

    The four list-name settings resolve to ``None`` ONLY when neither a flag
    nor the file supplied anything (so the template can distinguish "the
    operator turned the external log off" from "nothing was said"): the
    build's own flags carry defaults, so in practice a plain build always
    names its defaults here. The time zone has no default at all: ``None``
    after this is a build that must refuse, see `missing_time_zone`.
    """
    if env_file is None:
        return (
            enterprise_reader, deployment_log_list, deployment_log_change_list,
            deployment_log_site, change_log_list, time_zone, NO_ENV_FILE,
        )

    try:
        file_settings, digest = read_env_file(env_file)
    except EnvFileError as exc:
        # `path=None`: the exception message already names `env_file` (every
        # `EnvFileError` does, see `_refuse` in `model/env_file.py`), so
        # passing it again here just printed it twice.
        config_error("env file", None, exc)

    # Declared as a STR-typed mapping for the four list-name settings and
    # the zone, and a separate variable for the reader, because the reader
    # carries the declined sentinel and the others do not. One precedence
    # loop, one shapes-problem avoided.
    resolved: dict[str, str | None] = {
        DEPLOYMENT_LOG_LIST_PARAMETER: deployment_log_list,
        DEPLOYMENT_CHANGE_LOG_LIST_PARAMETER: deployment_log_change_list,
        DEPLOYMENT_LOG_SITE_PARAMETER: deployment_log_site,
        CHANGE_LOG_LIST_PARAMETER: change_log_list,
        TIME_ZONE_PARAMETER: time_zone,
    }
    resolved_reader = enterprise_reader
    values: list[EnvValue] = []
    for setting in ENV_SETTINGS:
        file_value = file_settings.get(setting.key)
        if file_value is None:
            continue
        if setting.parameter != ENTERPRISE_READER_PARAMETER and setting.parameter not in resolved:
            raise UnwiredEnvSettingError(
                f"{setting.key} sets execute_build's {setting.parameter!r} "
                "parameter, which resolve_env_settings does not know how "
                "to apply. Wire it in here before adding it to ENV_SETTINGS.",
            )
        # ONE precedence rule for every setting: a flag given at all --
        # including '' = off -- beats the file; the file beats nothing-said.
        # `override` records the value that won so the transcript can name
        # the losing candidate.
        current = (
            resolved_reader if setting.parameter == ENTERPRISE_READER_PARAMETER
            else resolved[setting.parameter]
        )
        if current is None:
            if setting.parameter == ENTERPRISE_READER_PARAMETER:
                resolved_reader = file_value
            else:
                resolved[setting.parameter] = file_value
            values.append(EnvValue(setting=setting, value=file_value, used=True, override=None))
        else:
            override = current if isinstance(current, str) else repr(current)
            values.append(EnvValue(
                setting=setting, value=file_value,
                used=False, override=override,
            ))

    provenance = EnvProvenance(
        path=_relative_env_path(env_file), digest=digest, values=tuple(values),
    )
    return (
        resolved_reader,
        resolved[DEPLOYMENT_LOG_LIST_PARAMETER],
        resolved[DEPLOYMENT_CHANGE_LOG_LIST_PARAMETER],
        resolved[DEPLOYMENT_LOG_SITE_PARAMETER],
        resolved[CHANGE_LOG_LIST_PARAMETER],
        resolved[TIME_ZONE_PARAMETER],
        provenance,
    )


def resolve_env_time_zone(
    env_file: Path | None, time_zone: str | None,
) -> tuple[str | None, EnvProvenance]:
    """The zone for a command that consumes the file's zone and nothing else.

    `report` wants the precedence `build` applies -- a flag beats the file,
    the file beats nothing said -- without inheriting the other five
    settings, so this runs the one resolver and narrows the record to the
    key it actually used. Reporting the rest would have a `report` run say
    it applied an enterprise reader it never reads.
    """
    (
        _reader, _log_list, _change_list, _log_site, _change_log,
        resolved, provenance,
    ) = resolve_env_settings(env_file, None, None, None, None, None, time_zone)
    return resolved, replace(
        provenance,
        values=tuple(
            value for value in provenance.values
            if value.setting.parameter == TIME_ZONE_PARAMETER
        ),
    )


def echo_env_provenance(provenance: EnvProvenance) -> None:
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
