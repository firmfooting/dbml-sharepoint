# test/test_list_title_convention.py
"""No shipped list title carries a space.

MEASURED on a live site 2026-09-06: SharePoint does not strip a space from a
list title when it derives the URL. `dbml Local Log` is served at
`/Lists/dbml Local Log`, percent-encoded in every real URL, while `dbml_Logs`
is served at `/Lists/dbml_Logs`. The slug is frozen at creation, so a title
chosen with a space is a URL nobody can clean up later.

Groups and permission levels are deliberately not covered: they have no URL.
"""

import pytest
import yaml
from _paths import SOLUTION_TEMPLATES

from dbml_sharepoint.analysis import sidecars

SIDECAR_TITLES = (
    sidecars.RUN_LOG_TITLE,
    sidecars.CHANGE_LOG_TITLE,
    sidecars.EXTERNAL_LOG_DEFAULT,
    sidecars.EXTERNAL_CHANGE_LOG_DEFAULT,
)


@pytest.mark.parametrize("title", SIDECAR_TITLES)
def test_a_sidecar_list_title_has_no_space(title: str) -> None:
    assert " " not in title, f"{title!r} would be percent-encoded in its URL"


def _family_list_titles() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for mapping_path in sorted(SOLUTION_TEMPLATES.glob("*/20-configure/mapping.yaml")):
        raw = yaml.safe_load(mapping_path.read_text(encoding="utf-8")) or {}
        prefix = raw.get("prefix", "")
        for entity in (raw.get("entities") or {}):
            found.append((mapping_path.parent.parent.name, f"{prefix}{entity}"))
    return found


def test_every_shipped_family_list_title_has_no_space() -> None:
    offenders = [
        f"{family}: {title!r}" for family, title in _family_list_titles() if " " in title
    ]
    assert not offenders, "list titles carrying a space: " + "; ".join(offenders)
