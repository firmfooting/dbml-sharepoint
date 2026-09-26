# src/dbml_sharepoint/analysis/checks/_loading.py
"""Facts the loader recorded while reading the mapping.

The loader has no findings of its own, so what it notices without refusing
travels on the mapping and is reported here.
"""

from dbml_sharepoint.analysis.checks.context import ValidationContext
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section


def check(vc: ValidationContext) -> list[Finding]:
    return [
        Finding(
            FindingCode.BLANK_KEY_TOOK_DEFAULT,
            f"{blank.path} is written with no value, so it takes its default "
            f"{blank.default!r}. Remove the key to take the default without this "
            f"warning, or give it a value.",
            location=_location(blank.path),
        )
        for blank in vc.bundle.mapping.blank_defaults
    ]


def _location(path: str) -> Location:
    """The section a dotted key path starts in, and the rest of the path as `sub`.

    A head that names no section keeps the whole path, so nothing is lost.
    """
    head = path.split(".", 1)[0].split("[", 1)[0]
    # `policies` is the head of every path in retention-policies.yaml.
    if head == "policies":
        return Location(Section.RETENTION, sub=path)
    try:
        section = Section(head)
    except ValueError:
        return Location(Section.MAPPING, sub=path)
    return Location(section, sub=path.removeprefix(head).removeprefix(".") or None)
