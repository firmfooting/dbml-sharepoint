# src/dbml_sharepoint/generators/verifygen.py
"""verify.js.txt: each clock cell a pack uses, exercised on a scratch list.

The deploy writes a rule and reads the bytes back; it cannot see whether
SharePoint evaluates the rule the way the mapping meant. This script can.
For every clock cell the pack uses (`analysis/clock_usage.py`) it puts one
column carrying that cell's exact rendering on a hidden scratch list, saves
at the boundaries the cell promises, queries with the elements a view would,
and reports whether the site kept the promise.

The checks are cells, not the pack's rules: the same handful of columns and
cases verify any pack, and the table in `analysis/clock_cells.py` is what
both the build and the check read.
"""
from __future__ import annotations

import re
from typing import Any

from dbml_sharepoint.analysis.clock_cells import cell_for
from dbml_sharepoint.analysis.clock_usage import clock_usage
from dbml_sharepoint.analysis.condition_rendering import to_caml, to_validation
from dbml_sharepoint.analysis.list_description import VERIFY_LIST_TITLE, verify_marker
from dbml_sharepoint.analysis.ordering import site_tables_in_order
from dbml_sharepoint.analysis.save_rules import joined_list_validation
from dbml_sharepoint.model.conditions import Group, Leaf
from dbml_sharepoint.model.mapping_types import ColumnValidation, MappingBundle
from dbml_sharepoint.model.parser import Schema
from dbml_sharepoint.model.release import Release
from dbml_sharepoint.templating import script_env

#: SharePoint's DisplayFormat for a DateTime field: 0 date only, 1 date and time.
DATE_ONLY = 0
DATE_AND_TIME = 1
HOUR = 3600
_VALUE_ELEMENT = re.compile(r"<Value [^>]*>.*?</Value>")
_QUERY_TYPES = {"CD": "date", "CC": "calculated_date", "CW": "datetime"}


def _midnight(days: int) -> dict[str, Any]:
    return {"kind": "midnight", "days": days}


def _instant(seconds: int) -> dict[str, Any]:
    return {"kind": "instant", "seconds": seconds}


def _case(
    case_id: str, op: str, value: dict[str, Any], expect: str, *, on: str | None = None,
) -> dict[str, Any]:
    case = {"id": case_id, "op": op, "value": value, "expect": expect}
    if on is not None:
        case["on"] = on
    return case


def _suffix(offset: int) -> str:
    """`30` for +30, `M1` for -1: a column name cannot carry a sign."""
    return f"M{-offset}" if offset < 0 else str(offset)


def _spelling(offset: int) -> str:
    if offset == 0:
        return "today"
    return f"today+{offset}" if offset > 0 else f"today-{-offset}"


class _Targets:
    """Accumulates columns, rows and checks while the cells are walked."""

    def __init__(self) -> None:
        self.columns: dict[str, dict[str, Any]] = {}
        self.rows: dict[str, dict[str, Any]] = {}
        self.checks: list[dict[str, Any]] = []

    def column(self, name: str, kind: str, display_format: int, **extra: Any) -> str:
        spec = {"name": name, "kind": kind, "display_format": display_format, **extra}
        self.columns.setdefault(name, spec)
        return name

    def row(self, row_id: str, column: str, value: dict[str, Any], *, day: int | None) -> None:
        self.rows.setdefault(row_id, {"id": row_id, "column": column, "value": value, "day": day})

    # ---- validation cells -------------------------------------------------
    def save_check(self, cell_id: str, offset: int) -> None:
        if cell_id.split("/")[1] == "date":
            self._date_save_check(cell_id, offset)
        else:
            self._datetime_save_check(cell_id, offset)

    def _date_save_check(self, cell_id: str, offset: int) -> None:
        if offset == 0:
            name, key = "VDT", "validation_date_today"
            cases = [
                _case("yesterday", "create", _midnight(-1), "save"),
                _case("today", "create", _midnight(0), "save"),
                _case("tomorrow", "create", _midnight(1), "refuse"),
                _case("update-today", "update", _midnight(0), "save", on="today"),
                _case("update-tomorrow", "update", _midnight(1), "refuse", on="today"),
            ]
        else:
            name = f"VDO{_suffix(offset)}"
            key = f"validation_date_today_offset_{_suffix(offset)}"
            cases = [
                _case(f"day-{offset}", "create", _midnight(offset), "save"),
                _case(f"day-{offset + 1}", "create", _midnight(offset + 1), "refuse"),
                _case(f"day-{offset - 1}", "create", _midnight(offset - 1), "save"),
            ]
        self._save(cell_id, key, name, "date", DATE_ONLY, _spelling(offset), cases, info=False)

    def _datetime_save_check(self, cell_id: str, offset: int) -> None:
        if cell_id.endswith("/now"):
            cases = [
                _case("hour-ago", "create", _instant(-HOUR), "save"),
                _case("hour-ahead", "create", _instant(HOUR), "refuse"),
                _case("update-now", "update", _instant(-5), "save", on="hour-ago"),
            ]
            self._save(
                cell_id, "validation_datetime_now", "VWN", "datetime", DATE_AND_TIME, "now",
                cases, info=False,
            )
            return
        # The one emitted cell that still reads the formula clock: recorded, not judged.
        name = f"VWO{_suffix(offset)}"
        key = f"validation_datetime_today_offset_{_suffix(offset)}"
        cases = [
            _case("now", "create", _instant(0), "info"),
            _case(f"day-{offset}", "create", _midnight(offset), "info"),
        ]
        self._save(
            cell_id, key, name, "datetime", DATE_AND_TIME, _spelling(offset), cases, info=True,
        )

    def _save(
        self, cell_id: str, key: str, name: str, kind: str, display_format: int,
        value: str, cases: list[dict[str, Any]], *, info: bool,
    ) -> None:
        self.column(name, kind, display_format)
        leaf = {"field": name, "op": "leq", "value": value}
        clause = to_validation(Group("all_of", (Leaf(**leaf),)), {name: kind})
        self.checks.append({
            "kind": "save", "key": key, "cell": cell_id, "info": info,
            "column": self.columns[name], "clause": clause, "leaf": leaf,
            "message": f"{name} is after the save instant.", "cases": cases,
        })

    # ---- caml cells -------------------------------------------------------
    def query_check(self, cell_id: str, offset: int) -> None:
        _, kind, sentinel = cell_id.split("/")
        if kind == "datetime":
            field = self.column("CW", "datetime", DATE_AND_TIME)
            self._datetime_rows()
            if sentinel != "now":
                self.row(f"cw-day-{offset}", "CW", _midnight(offset), day=offset)
        else:
            field = self.column("CD", "date", DATE_ONLY)
            if kind == "calculated_date":
                field = self.column("CC", "calculated_date", DATE_ONLY, formula="=[CD]")
            self._date_rows()
            if sentinel != "now":
                self.row(f"cd-day-{offset}", "CD", _midnight(offset), day=offset)
        if sentinel == "now":
            op, spelling = "Leq", "now"
        elif kind == "datetime":
            op, spelling = "Lt", _spelling(offset)
        else:
            op, spelling = "Eq", _spelling(offset)
        rendered = to_caml(
            Group("all_of", (Leaf(field=field, op=op.lower(), value=spelling),)),
            {field: _QUERY_TYPES[field]},
        )
        element = _VALUE_ELEMENT.search(rendered)
        if element is None:
            raise ValueError(f"no <Value> element in the CAML rendering: {rendered}")
        prefix = "cw-" if field == "CW" else "cd-"
        candidates = [row for row in self.rows.values() if row["id"].startswith(prefix)]
        if sentinel == "now":
            expect = [r["id"] for r in candidates if _not_after_now(r)]
        elif op == "Lt":
            expect = [r["id"] for r in candidates if r["day"] is not None and r["day"] < offset]
        else:
            expect = [
                r["id"] for r in candidates
                if r["day"] == offset and r["value"]["kind"] == "midnight"
            ]
        if sentinel == "now":
            key_suffix = "now"
        else:
            key_suffix = "today" if offset == 0 else f"today_offset_{_suffix(offset)}"
        self.checks.append({
            "kind": "query", "key": f"caml_{kind}_{key_suffix}", "cell": cell_id,
            "field": field, "op": op, "element": element.group(0), "expect": sorted(expect),
        })

    def _date_rows(self) -> None:
        for day in (-1, 0, 1):
            self.row(f"cd-day-{day}", "CD", _midnight(day), day=day)

    def _datetime_rows(self) -> None:
        self.row("cw-day--1", "CW", _midnight(-1), day=-1)
        self.row("cw-past", "CW", _instant(-HOUR), day=0)
        self.row("cw-future", "CW", _instant(HOUR), day=0)

    # ---- defaults and the clock ------------------------------------------
    def default_check(self, kind: str) -> None:
        if kind == "date":
            self.column("DD", "date", DATE_ONLY, default_value="[today]")
            self.row("dd-bare", "DD", {"kind": "none"}, day=None)
            self.checks.append({
                "kind": "default", "key": "default_date", "cell": "default/date",
                "column": self.columns["DD"], "row": "dd-bare", "method": "today-query",
            })
        else:
            self.column("DW", "datetime", DATE_AND_TIME, default_value="[today]")
            self.row("dw-bare", "DW", {"kind": "none"}, day=None)
            self.checks.append({
                "kind": "default", "key": "default_datetime", "cell": "default/datetime",
                "column": self.columns["DW"], "row": "dw-bare", "method": "within-minutes",
            })

    def lag_check(self) -> None:
        self.column("LT", "date", DATE_ONLY, default_formula="=TODAY()")
        self.row("lt-bare", "LT", {"kind": "none"}, day=None)
        self.checks.append({
            "kind": "lag", "key": "formula_clock_lag", "cell": "formula-clock",
            "column": self.columns["LT"], "row": "lt-bare",
        })


def _not_after_now(row: dict[str, Any]) -> bool:
    value = row["value"]
    if value["kind"] == "instant":
        return bool(value["seconds"] <= 0)
    return value["kind"] == "midnight" and row["day"] is not None and row["day"] <= 0


def verify_targets(schema: Schema, bundle: MappingBundle, site_role: str) -> dict[str, Any]:
    """The data the verify script loops over, derived from the pack's clock use."""
    mapping = bundle.mapping
    table_names = list(site_tables_in_order(schema, mapping.entities, site_role))
    usage = clock_usage(schema, mapping, table_names)
    targets = _Targets()
    for cell_id in sorted(usage.cells):
        cell = cell_for(*reversed(cell_id.split("/")))
        if cell.status == "refused":
            continue  # the build refuses it; nothing is deployed to verify
        for offset in sorted(usage.cells[cell_id]):
            if cell.target == "validation":
                targets.save_check(cell_id, offset)
            elif cell.target == "caml":
                targets.query_check(cell_id, offset)
    for kind in sorted({default.column_kind for default in usage.today_defaults}):
        targets.default_check("date" if kind != "datetime" else "datetime")
    if targets.checks:
        targets.lag_check()

    save_checks = [c for c in targets.checks if c["kind"] == "save"]
    rule = None
    if save_checks:
        joined = joined_list_validation(None, [
            (c["column"]["name"], ColumnValidation(when=Leaf(**c["leaf"]), message=c["message"]))
            for c in save_checks
        ])
        if joined is None:
            raise ValueError("save checks joined to no list rule")
        types = {c["column"]["name"]: c["column"]["kind"] for c in save_checks}
        rule = {"formula": f"={to_validation(joined.when, types)}", "message": joined.message}
    return {
        "list_title": VERIFY_LIST_TITLE,
        "marker": verify_marker(),
        "columns": [targets.columns[name] for name in sorted(targets.columns)],
        "rows": [{k: v for k, v in row.items() if k != "day"} for row in targets.rows.values()],
        "checks": targets.checks,
        "rule": rule,
    }


def _render(template_name: str, **context: Any) -> str:
    return script_env().get_template(template_name).render(**context)


def generate_verify_js(
    *,
    schema: Schema,
    bundle: MappingBundle,
    release: Release,
    site_url: str,
    site_role: str,
    source_dbml: str,
    generated_at: str,
) -> str:
    return _render(
        "verify.js.j2",
        site_url=site_url,
        site_role=site_role,
        release=release,
        source_dbml=source_dbml,
        generated_at=generated_at,
        targets=verify_targets(schema, bundle, site_role),
    )
