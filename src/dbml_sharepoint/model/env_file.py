# src/dbml_sharepoint/model/env_file.py
"""Parser for dbml-sharepoint.env, a KEY=value file of build defaults.

A consumer can keep build parameters beside their solution instead of
retyping flags. `ENV_SETTINGS` names every key this build understands, and
`read_env_file` refuses everything else.

Refusing is the point. A permissive parser that skipped a misspelled key or
a stray `export` would build clean, enrol nobody, and leave nothing
downstream able to see the difference. The strictness costs a consumer
nothing, because the filename is ours and no existing `.env` conventions
apply to it.
"""

import hashlib
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
from typing import Final, NoReturn

ENV_FILENAME: Final = "dbml-sharepoint.env"


@dataclass(frozen=True)
class EnvSetting:
    """One key this file is allowed to set.

    `key` is the `DBMLSP_`-prefixed name read from the file; `parameter` is
    the `execute_build` keyword it supplies; `help` is one line, listed by
    `build --help` in a later task.
    """

    key: str
    parameter: str
    help: str


# Named rather than repeated as literals: three call sites re-derived the key
# by scanning ENV_SETTINGS for this parameter.
ENTERPRISE_READER_KEY: Final = "DBMLSP_ENTERPRISE_READER"
ENTERPRISE_READER_PARAMETER: Final = "enterprise_reader"

DEPLOYMENT_LOG_LIST_KEY: Final = "DBMLSP_DEPLOY_LOG_LIST"
DEPLOYMENT_LOG_LIST_PARAMETER: Final = "deployment_log_list"

DEPLOYMENT_LOG_SITE_KEY: Final = "DBMLSP_DEPLOY_LOG_SITE"
DEPLOYMENT_LOG_SITE_PARAMETER: Final = "deployment_log_site"

CHANGE_LOG_LIST_KEY: Final = "DBMLSP_CHANGE_LOG_LIST"
CHANGE_LOG_LIST_PARAMETER: Final = "change_log_list"

# No `validate` field: `execute_build` already validates what it consumes, and
# importing `cli.py`'s validators here would cycle and drag typer into `model/`.
ENV_SETTINGS: Final[tuple[EnvSetting, ...]] = (
    EnvSetting(
        key=ENTERPRISE_READER_KEY,
        parameter=ENTERPRISE_READER_PARAMETER,
        help="UPN of the enterprise-reader service account to enrol.",
    ),
    EnvSetting(
        key=DEPLOYMENT_LOG_LIST_KEY,
        parameter=DEPLOYMENT_LOG_LIST_PARAMETER,
        help=(
            "Title of the central deployment log list to stamp start/stop/"
            "provenance rows into. Probed on the central logging site, never "
            "created; empty disables the stamps."
        ),
    ),
    EnvSetting(
        key=DEPLOYMENT_LOG_SITE_KEY,
        parameter=DEPLOYMENT_LOG_SITE_PARAMETER,
        help=(
            "Title of the central logging site the deployment log list "
            "lives on. Probed, never created by a deploy (the "
            "deploy-central-log sidecar creates site and list); empty "
            "disables the stamps."
        ),
    ),
    EnvSetting(
        key=CHANGE_LOG_LIST_KEY,
        parameter=CHANGE_LOG_LIST_PARAMETER,
        help=(
            "Title of the hidden change log the deploy writes type-2 rows "
            "into. Default: the tool's own dbml_Logs sidecar."
        ),
    ),
)


@dataclass(frozen=True)
class EnvValue:
    """One resolved setting, and whether a CLI flag overrode it.

    `used` is False when a flag passed on the command line won; `override`
    then carries the value that won, for reporting.
    """

    setting: EnvSetting
    value: str
    used: bool
    override: str | None


@dataclass(frozen=True)
class EnvProvenance:
    """What was read, for the build to report. `path` is None when no env
    file was found; the caller renders it relative rather than absolute."""

    path: str | None
    digest: str | None
    values: tuple[EnvValue, ...]


# One shared instance so every "no file was read" path says it with the same object.
NO_ENV_FILE: Final[EnvProvenance] = EnvProvenance(path=None, digest=None, values=())


def describe_env_provenance(provenance: EnvProvenance) -> str:
    """One line naming the env file a build read, for the manifest, index.md
    and the deploy transcript.

    The no-file case gets its own sentence, because an absent line reads the
    same as a feature that never ran. Overridden keys are named alongside
    used ones, reporting only the value that won, so a losing candidate never
    reaches a written artefact.
    """
    if provenance.path is None:
        return "No dbml-sharepoint.env file was read."
    used = [value for value in provenance.values if value.used]
    overridden = [value for value in provenance.values if not value.used]
    parts = []
    if used:
        parts.append(f"Used: {', '.join(value.setting.key for value in used)}.")
    if overridden:
        described = ", ".join(
            f"{value.setting.key} (using {value.override})" for value in overridden
        )
        parts.append(f"Overridden: {described}.")
    suffix = f" {' '.join(parts)}" if parts else ""
    return f"Read {provenance.path} (sha256 {provenance.digest}).{suffix}"


class EnvFileError(Exception):
    """Base class for anything wrong with a dbml-sharepoint.env file."""


class EnvFileSyntaxError(EnvFileError):
    """A line does not parse as KEY=value under this file's rules."""


class UnknownEnvKeyError(EnvFileError):
    """A DBMLSP_-prefixed key that is not in ENV_SETTINGS."""


class EnvFileReadError(EnvFileError):
    """The file could not be read or decoded.

    Covers `OSError` from `read_bytes` and bytes that are not valid UTF-8.
    Both are wrapped here because every catch site downstream handles only
    `EnvFileError`, and an unwrapped one would print a raw traceback.
    """


def _refuse(path: Path, line_no: int, text: str, reason: str) -> NoReturn:
    raise EnvFileSyntaxError(f"{path}: line {line_no}: {reason}: {text!r}")


def _unquote(path: Path, line_no: int, text: str, value: str) -> str:
    """Strip matching outer quotes; refuse a value that starts one but does
    not close it, rather than passing the stray quote character through."""
    if not value or value[0] not in "'\"":
        return value
    quote = value[0]
    if len(value) < 2 or value[-1] != quote:
        _refuse(path, line_no, text, "mismatched quotes")
    return value[1:-1]


def read_env_file(path: Path) -> tuple[dict[str, str], str]:
    """Parsed settings and the digest, from ONE read of the bytes.

    The digest is sha256 of the raw bytes, so a whitespace-only edit moves
    it. One function returns both, rather than a separate digest helper a
    caller could run against a file that changed between the two reads.
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise EnvFileReadError(f"{path}: could not read: {exc}") from exc
    digest = hashlib.sha256(raw).hexdigest()[:12]
    known_keys = tuple(setting.key for setting in ENV_SETTINGS)
    settings: dict[str, str] = {}
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EnvFileReadError(f"{path}: not valid UTF-8: {exc}") from exc
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            _refuse(path, line_no, stripped, "export is not supported; this is not a shell script")
        if "=" not in stripped:
            _refuse(path, line_no, stripped, "expected KEY=value")
        key_part, _, value_part = stripped.partition("=")
        key = key_part.strip()
        raw_value = value_part.strip()
        # Refuse rather than keep the comment in the value: a key whose
        # consumer does not validate would otherwise take it silently.
        if raw_value[:1] not in "'\"" and " #" in raw_value:
            _refuse(
                path,
                line_no,
                stripped,
                "a comment must start its own line; quote the value to keep a literal ' #'",
            )
        value = _unquote(path, line_no, stripped, raw_value)
        if not key.startswith("DBMLSP_"):
            _refuse(path, line_no, stripped, f"key {key!r} must start with DBMLSP_")
        if key not in known_keys:
            near = get_close_matches(key, known_keys, n=3, cutoff=0.6)
            suggestion = f" Did you mean: {', '.join(near)}?" if near else ""
            raise UnknownEnvKeyError(f"{path}: line {line_no}: unknown key {key!r}.{suggestion}")
        if key in settings:
            _refuse(path, line_no, stripped, f"key {key!r} is repeated; last-wins is not supported")
        settings[key] = value
    return settings, digest
