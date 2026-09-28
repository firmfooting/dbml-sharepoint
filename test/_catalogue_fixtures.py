"""Pack directories and pack.toml text for the catalogue tests, written to tmp_path."""

import json
from importlib.metadata import metadata
from pathlib import Path

from dbml_sharepoint.catalogue import CORE_DISTRIBUTION, PACK_MANIFEST

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
    """A minimal pack: an empty schema, a one-entity mapping and a pack.toml."""
    root = parent / pack_id
    (root / "10-design").mkdir(parents=True)
    (root / "10-design" / "schema.dbml").write_text("", encoding="utf-8")
    (root / "20-configure").mkdir()
    (root / "20-configure" / "mapping.yaml").write_text(
        'prefix: "X_"\nentities:\n  Thing: {}\n', encoding="utf-8", newline="\n",
    )
    (root / PACK_MANIFEST).write_text(
        manifest_text(pack_id, overrides), encoding="utf-8", newline="\n",
    )
    return root
