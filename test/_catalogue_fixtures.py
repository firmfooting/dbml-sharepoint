"""Pack directories and pack.toml text for the catalogue tests, written to tmp_path."""

import json
from dataclasses import dataclass
from importlib.metadata import EntryPoint, PathDistribution, metadata
from pathlib import Path

import pytest

from dbml_sharepoint import catalogue
from dbml_sharepoint.catalogue import (
    CORE_DISTRIBUTION,
    JOURNEYS_DIRNAME,
    PACK_MANIFEST,
    SOLUTION_ROOTS_GROUP,
)

#: Core's licence as its installed metadata declares it; test_pack_manifest ties it to pyproject.
CORE_LICENSE = metadata(CORE_DISTRIBUTION)["License-Expression"]


def manifest_text(pack_id: str, overrides: dict[str, str] | None = None) -> str:
    """A valid pack.toml for `pack_id` under core's licence, with any value replaced."""
    values = {
        "id": pack_id,
        "title": pack_id.replace("-", " ").capitalize(),
        "summary": "A pack written for a test.",
        "license": CORE_LICENSE,
        "origin": "firmfooting",
        "notice": "",
        "min_core": ">=0.5,<1",
    } | (overrides or {})
    # json.dumps writes a valid TOML basic string, escapes included.
    return "".join(f"{key} = {json.dumps(value)}\n" for key, value in values.items())


def without(text: str, key: str) -> str:
    """`text` with the line assigning `key` removed."""
    return "".join(
        line for line in text.splitlines(keepends=True) if not line.startswith(f"{key} =")
    )


def write_family(parent: Path, pack_id: str, overrides: dict[str, str] | None = None) -> Path:
    """A minimal pack: an empty schema, a one-entity mapping, a release and a pack.toml."""
    root = parent / pack_id
    (root / "10-design").mkdir(parents=True)
    (root / "10-design" / "schema.dbml").write_text("", encoding="utf-8")
    (root / "20-configure").mkdir()
    (root / "20-configure" / "mapping.yaml").write_text(
        'prefix: "X_"\nentities:\n  Thing: {}\n', encoding="utf-8", newline="\n",
    )
    (root / "20-configure" / "release.yaml").write_text("", encoding="utf-8")
    (root / PACK_MANIFEST).write_text(
        manifest_text(pack_id, overrides), encoding="utf-8", newline="\n",
    )
    return root


def write_journey(root: Path, journey_id: str, members: list[str]) -> Path:
    """A journey file under `root/journeys/` naming `members` in order."""
    directory = root / JOURNEYS_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{journey_id}.md"
    path.write_text(
        f"---\ntitle: {journey_id}\nsummary: A journey for a test.\n"
        f"solutions: [{', '.join(members)}]\n---\n",
        encoding="utf-8", newline="\n",
    )
    return path


#: What each fake provider's entry point returns, keyed by the function it names.
_ROOTS: dict[str, object] = {}

#: The entry-point targets, one per provider a test may install.
_TARGETS = ("first_root", "second_root")


def _returned(value: object) -> object:
    """`value`, or raised when it is an exception, as a broken provider would."""
    if isinstance(value, BaseException):
        raise value
    return value


def first_root() -> object:
    """The target of the first installed provider's entry point."""
    return _returned(_ROOTS["first_root"])


def second_root() -> object:
    """The target of the second installed provider's entry point."""
    return _returned(_ROOTS["second_root"])


@dataclass(frozen=True)
class Provider:
    """One installed distribution registering a solution root."""

    name: str
    #: What the entry point returns; an exception instance is raised instead.
    root: object
    #: None writes metadata with no License-Expression at all.
    licence: str | None = "BUSL-1.1"


def install(monkeypatch: pytest.MonkeyPatch, site: Path, *providers: Provider) -> None:
    """Make exactly `providers` visible to the catalogue, each through real dist-info metadata."""
    points: list[EntryPoint] = []
    for target, provider in zip(_TARGETS[: len(providers)], providers, strict=True):
        monkeypatch.setitem(_ROOTS, target, provider.root)
        dist_info = site / f"{provider.name.replace('-', '_')}-1.0.dist-info"
        dist_info.mkdir(parents=True)
        fields = ["Metadata-Version: 2.4", f"Name: {provider.name}", "Version: 1.0"]
        if provider.licence is not None:
            fields.append(f"License-Expression: {provider.licence}")
        (dist_info / "METADATA").write_text("\n".join(fields) + "\n", encoding="utf-8")
        (dist_info / "entry_points.txt").write_text(
            f"[{SOLUTION_ROOTS_GROUP}]\npacks = _catalogue_fixtures:{target}\n",
            encoding="utf-8",
        )
        points.extend(PathDistribution(dist_info).entry_points.select(group=SOLUTION_ROOTS_GROUP))

    def installed(*, group: str) -> list[EntryPoint]:
        return points if group == SOLUTION_ROOTS_GROUP else []

    monkeypatch.setattr(catalogue, "entry_points", installed)
