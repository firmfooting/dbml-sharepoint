# src/dbml_sharepoint/model/help_guides.py
"""The help-link settings: a base URL and a file mapping guide keys to page names.

Both come from `dbml-sharepoint.env`, never from the mapping, because the hub's
address is a fact about a deployment and a mapping is shared between them. A
banner rule's `help:` key names a guide; this module turns the pair of settings
into key-to-URL, or into a finding saying why it cannot. A half-set pair or a
placeholder address is refused, so no dead link reaches a deployed header.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import SplitResult, quote, urlsplit

from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.model.env_file import HELP_BASE_URL_KEY, HELP_GUIDES_KEY
from dbml_sharepoint.model.yamlio import PARSE_ERRORS, safe_load

_HOST = re.compile(r"[A-Za-z0-9.-]+")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_PLACEHOLDERS = ("<", ">", "replace-me", "replace_with", "replace-with")


@dataclass(frozen=True)
class HelpSettings:
    """The two raw env values, and the folder a relative guides path resolves against."""

    base_url: str | None
    guides_file: str | None
    env_dir: Path | None


@dataclass(frozen=True)
class HelpGuides:
    """Guide key to absolute URL."""

    urls: Mapping[str, str]


def _refuse(code: FindingCode, message: str) -> tuple[None, list[Finding]]:
    return None, [Finding(code, message, location=Location(Section.FORM_FORMATTING))]


def _authority_problem(parts: SplitResult) -> str | None:
    try:
        parts.port  # noqa: B018 -- reading it is the check: a non-numeric port raises
    except ValueError:
        return "has a port that is not a number in range"
    if "@" in parts.netloc:
        return "must not carry a user name or password"
    if not _HOST.fullmatch(parts.hostname or ""):
        return "must have a host of letters, digits, dots and hyphens (no IDNA hosts)"
    return None


def _base_problem(base: str) -> str | None:
    try:
        parts = urlsplit(base)
        host = parts.hostname
    except ValueError:
        return "is not a URL"
    if parts.scheme != "https" or not host:
        return "must be an https URL with a host"
    if parts.query or parts.fragment:
        return "must not have a query or a fragment"
    if (problem := _authority_problem(parts)) is not None:
        return problem
    if (
        any(mark in base.lower() for mark in _PLACEHOLDERS)
        or host.endswith(".invalid") or host.startswith("example.") or ".example." in host
    ):
        return "is still a placeholder"
    return None


def _read_pages(path: Path) -> dict[str, str] | str:
    """The guide key to page name map, or the reason it cannot be used."""
    try:
        raw = safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        return f"{path}: could not read: {exc}"
    except PARSE_ERRORS as exc:
        return f"{path}: not valid YAML: {exc}"
    if not isinstance(raw, dict) or not raw:
        return f"{path}: must be a non-empty mapping of guide key to page name."
    pages: dict[str, str] = {}
    for key, leaf in raw.items():
        if not isinstance(key, str) or not key:
            return f"{path}: guide key {key!r} must be text."
        if (
            not isinstance(leaf, str) or leaf.strip() in ("", ".", "..")
            or "/" in leaf or _SCHEME.match(leaf)
        ):
            return (
                f"{path}: guide '{key}' must name a page in the base folder, "
                f"with no slash or scheme (got {leaf!r})."
            )
        pages[key] = leaf
    return pages


def load_help_guides(settings: HelpSettings) -> tuple[HelpGuides | None, list[Finding]]:
    """`(None, [])` when both keys are unset, `(None, [error])` when refused."""
    base, file = settings.base_url, settings.guides_file
    if base is None and file is None:
        return None, []
    if base is None or file is None:
        missing = HELP_BASE_URL_KEY if base is None else HELP_GUIDES_KEY
        return _refuse(
            FindingCode.FORM_HELP_SETTING_INCOMPLETE,
            f"help links need both {HELP_BASE_URL_KEY} and {HELP_GUIDES_KEY}; "
            f"{missing} is not set.",
        )
    if (problem := _base_problem(base)) is not None:
        return _refuse(
            FindingCode.FORM_HELP_BASE_URL_INVALID, f"{HELP_BASE_URL_KEY} {problem}: {base!r}.",
        )
    path = Path(file)
    if not path.is_absolute() and settings.env_dir is not None:
        path = settings.env_dir / path
    pages = _read_pages(path)
    if isinstance(pages, str):
        return _refuse(FindingCode.FORM_HELP_PAGE_INVALID, pages)
    parts = urlsplit(base)
    # The path lands in a single-quoted formatter literal, so quote it as the pages are.
    prefix = f"{parts.scheme}://{parts.netloc}{quote(parts.path.rstrip('/'), safe='/:%')}/"
    return HelpGuides({key: prefix + quote(leaf) for key, leaf in pages.items()}), []
