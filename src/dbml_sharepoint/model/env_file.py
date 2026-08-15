# src/dbml_sharepoint/model/env_file.py
"""Parser for dbml-sharepoint.env, a KEY=value file of build defaults.

A consumer can put build parameters beside their solution instead of
retyping flags on every invocation, starting with the enterprise-reader UPN.
The registry (`ENV_SETTINGS`) names every key this build understands; the
parser (`read_env_file`) is deliberately strict about everything else.

The failure class this project exists to close, per `AGENTS.md`, is a change
that saves, reads back clean, and does nothing on the far side. A permissive
parser that silently skipped a misspelled key or a stray `export` would build
clean and enrol nobody, and nothing downstream could ever see the difference.
Refusing outright is the only way a mistake here is not silent. The strict
rules are fair specifically because the filename is ours: this is not a
`.env` a consumer already has conventions for, so refusing the ones this file
does not need (`export`, interpolation, shell quoting edge cases) costs
nothing a consumer was relying on.
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


# Deliberately no `validate` field. An earlier draft gave each entry the
# validator its CLI flag uses (`validate_enterprise_reader`), but that
# validator lives in `cli.py` and raises `typer.BadParameter` -- importing it
# here would create a real import cycle (cli -> model.env_file -> cli) and
# would drag typer into `model/`, which nothing else there imports. It is
# also unnecessary: the typer option has no `callback`, so validation already
# happens inside `execute_build`. A value resolved from this file and passed
# as the same keyword takes the same code path as a flag value and is
# refused for the same reasons with the same message. Do not add the field
# back; if a future setting needs bespoke checking, that check belongs where
# the parameter is consumed, not here.
ENV_SETTINGS: Final[tuple[EnvSetting, ...]] = (
    EnvSetting(
        key="DBMLSP_ENTERPRISE_READER",
        parameter="enterprise_reader",
        help="UPN of the enterprise-reader service account to enrol.",
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


# The provenance every artefact defaults to when a caller passes none: no
# file was read. A single shared instance rather than each call site
# spelling out `EnvProvenance(path=None, digest=None, values=())` -- the
# three artefacts that render this (the manifest, index.md, the deploy
# transcript) and `_resolve_env_settings`'s own no-file return all mean the
# same thing, and should say so with the same object.
NO_ENV_FILE: Final[EnvProvenance] = EnvProvenance(path=None, digest=None, values=())


def describe_env_provenance(provenance: EnvProvenance) -> str:
    """One line describing what dbml-sharepoint.env a build read, for an
    artefact that is not the terminal the build ran in: the manifest,
    index.md and the deploy transcript's `log()` line.

    An absent line is indistinguishable from a feature that did not run, so
    the no-file case is its own explicit sentence rather than nothing.
    """
    if provenance.path is None:
        return "No dbml-sharepoint.env file was read."
    used_keys = ", ".join(value.setting.key for value in provenance.values if value.used)
    suffix = f" Used: {used_keys}." if used_keys else ""
    return f"Read {provenance.path} (sha256 {provenance.digest}).{suffix}"


class EnvFileError(Exception):
    """Base class for anything wrong with a dbml-sharepoint.env file."""


class EnvFileSyntaxError(EnvFileError):
    """A line does not parse as KEY=value under this file's rules."""


class UnknownEnvKeyError(EnvFileError):
    """A DBMLSP_-prefixed key that is not in ENV_SETTINGS."""


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

    The digest is sha256 of the raw bytes, not of the parsed content, so a
    whitespace-only edit still moves it -- and it is computed from the same
    bytes the parser reads, because a caller comparing a recorded digest
    against the file it was told was parsed needs that to be true. Hence one
    function returning both, rather than a digest helper a caller might call
    against a file that changed between the two reads.
    """
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()[:12]
    known_keys = tuple(setting.key for setting in ENV_SETTINGS)
    settings: dict[str, str] = {}
    for line_no, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            _refuse(path, line_no, stripped, "export is not supported; this is not a shell script")
        if "=" not in stripped:
            _refuse(path, line_no, stripped, "expected KEY=value")
        key_part, _, value_part = stripped.partition("=")
        key = key_part.strip()
        value = _unquote(path, line_no, stripped, value_part.strip())
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
