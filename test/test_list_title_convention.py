# test/test_list_title_convention.py
"""No shipped list URL carries a space; its display title may.

MEASURED on a live site 2026-09-06: SharePoint does not strip a space from a
list title when it derives the URL. `dbml Local Log` is served at
`/Lists/dbml Local Log`, percent-encoded in every real URL. The slug is frozen
at creation, so a list whose title has a space declares its URL separately
(`internal_name` in a mapping; the sidecars take the title minus its spaces).

Groups and permission levels are deliberately not covered: they have no URL.
"""

import pytest
from _narrow import as_dict
from _paths import SOLUTION_TEMPLATES

from dbml_sharepoint.analysis import sidecars
from dbml_sharepoint.model import yamlio

SIDECAR_TITLES = (
    sidecars.RUN_LOG_TITLE,
    sidecars.CHANGE_LOG_TITLE,
    sidecars.EXTERNAL_LOG_DEFAULT,
    sidecars.EXTERNAL_CHANGE_LOG_DEFAULT,
)


@pytest.mark.parametrize("title", SIDECAR_TITLES)
def test_a_sidecar_title_has_a_space_and_its_url_slug_does_not(title: str) -> None:
    assert " " in title, f"{title!r} is shown in Site contents"


def _family_list_urls() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for mapping_path in sorted(SOLUTION_TEMPLATES.glob("*/20-configure/mapping.yaml")):
        raw = as_dict(yamlio.safe_load(mapping_path.read_text(encoding="utf-8")) or {})
        prefix = raw.get("prefix", "")
        for entity, spec in as_dict(raw.get("entities") or {}).items():
            fields = as_dict(spec)
            title = str(fields.get("title") or f"{prefix}{entity}")
            url = str(fields.get("internal_name") or title)
            found.append((mapping_path.parent.parent.name, url))
    return found


def test_every_shipped_family_list_url_has_no_space() -> None:
    offenders = [f"{family}: {url!r}" for family, url in _family_list_urls() if " " in url]
    assert not offenders, "list URLs carrying a space: " + "; ".join(offenders)
