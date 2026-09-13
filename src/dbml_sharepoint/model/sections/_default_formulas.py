# src/dbml_sharepoint/model/sections/_default_formulas.py
"""`default_formulas`: a SharePoint default formula per column.

Shape only: entity, then column, then one formula string. Whether the
entity and the column exist, and whether the column's type may carry a
formula, is the validator's question (`analysis/checks/_default_formulas.py`).
"""

from typing import Any

from dbml_sharepoint.model._keys import _require_mapping
from dbml_sharepoint.model.sections.context import SectionContext


def read(sc: SectionContext) -> dict[str, Any]:
    default_formulas: dict[str, dict[str, str]] = {}
    for entity, cols in _require_mapping(
        sc.block("default_formulas"), "default_formulas",
    ).items():
        formulas: dict[str, str] = {}
        for column, formula in _require_mapping(
            cols, f"default_formulas.{entity}",
        ).items():
            # Not coerced with str(): a bare `2026` or `true` is a value, and
            # a value belongs in the DBML `default:` setting, not here.
            if not isinstance(formula, str):
                raise ValueError(
                    f"default_formulas.{entity}.{column}: expected a formula "
                    f"string such as \"=TODAY()\", got {formula!r}",
                )
            formulas[str(column)] = formula
        default_formulas[str(entity)] = formulas
    return {"default_formulas": default_formulas}
