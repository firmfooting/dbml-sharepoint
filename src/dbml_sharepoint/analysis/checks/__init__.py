# src/dbml_sharepoint/analysis/checks/__init__.py
"""Mapping checks, one module per family.

``validate_against_mapping`` was a single function of about 1,200 lines
covering eighteen unrelated concerns. Each family now lives in its own
module behind the same ``check(vc) -> list[Finding]`` signature, so a
reader looking for one rule opens one file.

CHECK_FAMILIES is ordered, and the order is part of the contract: findings
are reported in it, and tests assert on the sequence. Later families also
rely on earlier ones having reported structural problems. The formatting
checks skip an unknown entity rather than re-report it, because _structure
has already errored on it. Append rather than reorder.
"""

from collections.abc import Callable

from dbml_sharepoint.analysis.checks import (
    _demo,
    _formatting,
    _naming,
    _permissions,
    _provenance,
    _retirement,
    _sources,
    _structure,
    _views,
)
from dbml_sharepoint.analysis.checks._context import ValidationContext
from dbml_sharepoint.analysis.validator import Finding

CHECK_FAMILIES: tuple[Callable[[ValidationContext], list["Finding"]], ...] = (
    _structure.check,
    _views.check,
    _demo.check,
    _formatting.check,
    _retirement.check,
    _naming.check,
    _sources.check,
    _permissions.check,
    _provenance.check,
)

__all__ = ["CHECK_FAMILIES", "ValidationContext"]
