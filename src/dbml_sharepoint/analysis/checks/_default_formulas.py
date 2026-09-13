# src/dbml_sharepoint/analysis/checks/_default_formulas.py
"""`default_formulas`: a SharePoint DefaultFormula per column.

A default formula runs when a row is created, before the row exists, so it
may read the clock and constants and nothing else. The rules here fail
closed on whatever has not been measured, and the measurements are cited
beside the constants they admit.
"""

from collections.abc import Collection

from dbml_sharepoint.analysis.checks.context import ValidationContext
from dbml_sharepoint.analysis.column_refs import formula_column_refs, formula_function_names
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.rendered_columns import rendered_columns
from dbml_sharepoint.analysis.typemap import (
    CALCULATED_TYPES,
    choice_enum_for,
    is_hyperlink,
    is_multi_value,
    is_person,
)
from dbml_sharepoint.model.parser import Column, Table

#: The type class of a single-value enum column. Its DBML type is the enum's
#: own name, so the set below cannot list it by spelling; `_type_class`
#: answers this token for one instead.
ENUM = "enum"

#: The DBML column types a default formula may be declared on. ONE constant,
#: widened by editing this line once a live probe has measured the type.
#:
#: MEASURED, not inferred. `date` and `datetime` rest on a date column filled
#: through a REST item create (`formula.datetime.today-function-default-value`,
#: `field.date.dynamic-default-rest-fill`). `int`, `number` and a single-value
#: enum were measured 2026-09-13 by test/manual/library-guards-probe.js,
#: revision c445a55c: a POST to /fields carrying `DefaultFormula` on
#: SP.FieldNumber and on SP.FieldChoice was accepted and read back exactly as
#: sent, on a generic list and on a document library
#: (`field.default-formula.number-property-reads-back`,
#: `field.default-formula.choice-property-reads-back`), and an item POST
#: carrying only Title read back the computed year and quarter
#: (`field.default-formula.number-fills-on-item-create`,
#: `field.default-formula.choice-fills-on-item-create`).
DEFAULT_FORMULA_TYPES: frozenset[str] = frozenset({"date", "datetime", "int", "number", ENUM})

#: Types a probe is expected to admit and none has measured yet. Refused
#: today with a finding that says the measurement is pending, rather than
#: that the type is wrong. The 2026-09-13 run measured Number and Choice and
#: not Text.
PENDING_DEFAULT_FORMULA_TYPES: frozenset[str] = frozenset({"nvarchar"})

#: The functions a default formula may call, in exactly these spellings. Any
#: other name is refused, a lower-case one included, because nothing has
#: measured what SharePoint does with it.
DEFAULT_FORMULA_FUNCTIONS: frozenset[str] = frozenset({
    "TODAY", "YEAR", "MONTH", "DAY", "ROUNDUP", "ROUNDDOWN", "MOD", "TEXT",
    "IF", "AND", "OR",
})


def check(vc: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    enum_names = set(vc.enum_by_name)
    for entity, formulas in vc.bundle.mapping.default_formulas.items():
        table = vc.tables_by_name.get(entity)
        if table is None:
            findings.append(Finding(
                FindingCode.UNKNOWN_ENTITY,
                f"default_formulas: unknown entity {entity!r}.",
                location=Location(Section.DEFAULT_FORMULAS, entity=entity),
            ))
            continue
        rendered = rendered_columns(table, vc.cross_site_columns(entity))
        columns_by_name = {col.name: col for col in table.columns}
        for name, formula in formulas.items():
            findings += _one(vc, table, name, formula, rendered, columns_by_name, enum_names)
    return findings


def _one(
    vc: ValidationContext,
    table: Table,
    name: str,
    formula: str,
    rendered: set[str],
    columns_by_name: dict[str, Column],
    enum_names: Collection[str],
) -> list[Finding]:
    """One declaration: the formula's text, then the column it fills."""
    at = Location(Section.DEFAULT_FORMULAS, entity=table.name, column=name)
    findings = _formula_text(at, table.name, name, formula)
    col = columns_by_name.get(name)
    # Asked before the rendered check: a cross-site column is declared and
    # never created, and the reason belongs in the message.
    if (table.name, name) in vc.cross_site_pairs:
        findings.append(_kind(
            at, table.name, name,
            "a cross-site reference column, deployed as a Choice and URL pair",
        ))
        return findings
    if col is None or name not in rendered:
        findings.append(Finding(
            FindingCode.DEFAULT_FORMULA_UNKNOWN_COLUMN,
            f"default_formulas.{table.name}.{name}: {name!r} is not a column "
            f"the deploy creates on {table.name}.",
            location=at,
        ))
        return findings
    if col.default is not None:
        # Nothing has measured which of the two SharePoint honours when a
        # field carries both, so a column declares one or the other.
        findings.append(Finding(
            FindingCode.DEFAULT_FORMULA_BESIDE_A_DEFAULT_VALUE,
            f"default_formulas.{table.name}.{name}: the column also declares "
            f"`default: {col.default!r}` in the DBML. A column takes a default "
            f"value or a default formula, not both; remove one.",
            location=at,
        ))
    reason = _unsupported_kind(col, enum_names)
    if reason is not None:
        findings.append(_kind(at, table.name, name, reason))
        return findings
    findings += _type(at, table.name, col, enum_names)
    return findings


def _formula_text(at: Location, entity: str, name: str, formula: str) -> list[Finding]:
    """What the formula says, independent of the column it is declared on."""
    findings: list[Finding] = []
    if not formula.startswith("="):
        findings.append(Finding(
            FindingCode.DEFAULT_FORMULA_MISSING_EQUALS,
            f"default_formulas.{entity}.{name}: a default formula must start "
            f"with '='.",
            location=at,
        ))
    refs = formula_column_refs(formula)
    if refs:
        findings.append(Finding(
            FindingCode.DEFAULT_FORMULA_REFERENCES_A_COLUMN,
            f"default_formulas.{entity}.{name}: the formula names "
            f"[{'], ['.join(sorted(refs))}]. A default formula runs before the "
            f"row exists, so it can read no column; compute from TODAY() and "
            f"constants instead.",
            location=at,
        ))
    unsupported = sorted(formula_function_names(formula) - DEFAULT_FORMULA_FUNCTIONS)
    if unsupported:
        findings.append(Finding(
            FindingCode.DEFAULT_FORMULA_FUNCTION_UNSUPPORTED,
            f"default_formulas.{entity}.{name}: the formula calls "
            f"{', '.join(unsupported)}, which is not in the allowed set "
            f"({', '.join(sorted(DEFAULT_FORMULA_FUNCTIONS))}). Function names "
            f"are matched as spelled.",
            location=at,
        ))
    return findings


def _kind(at: Location, entity: str, name: str, reason: str) -> Finding:
    return Finding(
        FindingCode.DEFAULT_FORMULA_COLUMN_KIND_UNSUPPORTED,
        f"default_formulas.{entity}.{name}: {name!r} is {reason}, which cannot "
        f"carry a default formula.",
        location=at,
    )


def _unsupported_kind(col: Column, enum_names: Collection[str]) -> str | None:
    """Why this column can never take a default formula, or None if it may."""
    if col.name == "Title":
        return "the built-in Title column, which is provisioned through its own patch"
    if col.type in CALCULATED_TYPES:
        return "a calculated column, whose value SharePoint computes itself"
    if is_multi_value(col.type):
        return "a multi-value column"
    if is_person(col.type):
        return "a Person column"
    if is_hyperlink(col.type):
        return "a Hyperlink column"
    # The resolver's own order: an enum is a Choice before its `ref` is read.
    if col.ref is not None and choice_enum_for(col.type, enum_names) is None:
        return "a Lookup column"
    return None


def _type_class(col: Column, enum_names: Collection[str]) -> str:
    """The name `DEFAULT_FORMULA_TYPES` knows this column's type by."""
    return ENUM if choice_enum_for(col.type, enum_names) is not None else col.type


def _type(
    at: Location, entity: str, col: Column, enum_names: Collection[str],
) -> list[Finding]:
    """The column's type against what has been measured."""
    type_class = _type_class(col, enum_names)
    if type_class in DEFAULT_FORMULA_TYPES:
        if type_class != ENUM:
            return []
        # MEASURED 2026-09-13 (library-guards-probe.js c445a55c,
        # `field.default-formula.choice-non-member-result`): a Choice formula
        # whose result was outside the choice set stored the literal "Q13".
        # The build cannot evaluate the clock, so it can only warn.
        return [Finding(
            FindingCode.DEFAULT_FORMULA_CHOICE_RESULT_UNCHECKED,
            f"default_formulas.{entity}.{col.name}: the formula's result must "
            f"be a member of {col.type} at run time. A result the enum does not "
            f"list is stored as a literal the column does not offer, not "
            f"refused and not left blank.",
            location=at,
        )]
    if type_class in PENDING_DEFAULT_FORMULA_TYPES:
        return [Finding(
            FindingCode.DEFAULT_FORMULA_TYPE_UNMEASURED,
            f"default_formulas.{entity}.{col.name}: a default formula on a "
            f"{col.type} column has not been measured on a live site yet, so "
            f"it is refused until the probe that measures it lands.",
            location=at,
        )]
    return [Finding(
        FindingCode.DEFAULT_FORMULA_TYPE_UNSUPPORTED,
        f"default_formulas.{entity}.{col.name}: a default formula is not "
        f"supported on a {col.type} column. Supported: "
        f"{', '.join(sorted(DEFAULT_FORMULA_TYPES - {ENUM}))} and a "
        f"single-value enum.",
        location=at,
    )]
