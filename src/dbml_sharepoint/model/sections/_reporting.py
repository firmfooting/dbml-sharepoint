# src/dbml_sharepoint/model/sections/_reporting.py
"""`reporting` and `derived_columns`, the two sections the reporting pack reads.

The deploy reads neither, which is why this is the family
`reporting_source` may move to a file beside the mapping: the seam is what
consumes a section rather than how long it is.
"""

from typing import Any

from dbml_sharepoint.analysis.derived import DERIVED_AGGREGATES, DERIVED_TYPES
from dbml_sharepoint.model._keys import _reject_unknown_keys, _require_mapping
from dbml_sharepoint.model.mapping_types import DerivedColumn, ReportingOptions
from dbml_sharepoint.model.sections.context import SectionContext

_DERIVED_KEYS: dict[str, frozenset[str]] = {
    "expr": frozenset({
        "kind", "name", "type", "m", "hidden", "description", "replace",
    }),
    "lookup": frozenset({
        "kind", "from", "via", "key", "pick", "types", "hidden",
        "description",
    }),
    "count": frozenset({
        "kind", "from", "via", "name", "aggregate", "column", "where",
        "type", "hidden", "description",
    }),
}


def read(sc: SectionContext) -> dict[str, Any]:
    derived_columns = _parse_derived_columns(sc.block("derived_columns"))
    reporting = _parse_reporting(sc.block("reporting"))
    return {"reporting": reporting, "derived_columns": derived_columns}


#: The message a mapping still carrying `reporting.time_zone` gets. Named
#: so the test that pins the wording reads the same string the loader
#: raises, rather than a copy that can drift from it.
REMOVED_TIME_ZONE_KEY_MESSAGE = (
    "reporting.time_zone has been replaced by the --time-zone build input: "
    "pass --time-zone to `build` and `report`, or set DBMLSP_TIME_ZONE in "
    "dbml-sharepoint.env. A time zone is a fact about the site a pack is "
    "built for, not about the solution, so it does not belong in a mapping. "
    "Remove the key; the AsSiteDate and AsSiteDateTime helpers and the "
    "derived columns that call them are unchanged."
)


def _parse_reporting(block: Any) -> ReportingOptions:
    section = _require_mapping(block, "reporting")
    # Refused by name, before the generic unknown-key check can call it a
    # typo: the key existed, and the author needs to know where it went.
    if "time_zone" in section:
        raise ValueError(REMOVED_TIME_ZONE_KEY_MESSAGE)
    switches = ("system_columns", "users_table")
    _reject_unknown_keys(section, set(switches), "reporting")
    values: dict[str, bool] = {}
    for name in switches:
        value = section.get(name, False)
        # YAML reads "yes" and 1 as truthy, so anything but a real boolean
        # would switch the feature on by accident and never say so.
        if not isinstance(value, bool):
            raise ValueError(
                f"reporting.{name}: expected true or false, got {value!r}",
            )
        values[name] = value
    return ReportingOptions(**values)


def _derived_text(item: dict[str, Any], key: str, where: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{where}: {key} must be a non-empty string, got {value!r}",
        )
    return value


def _parse_derived_column(item: Any, where: str) -> DerivedColumn:
    """One `derived_columns` entry, refused rather than defaulted.

    SHAPE ONLY. Whether the entity exists, whether `via` really is a lookup
    and whether an `m` expression names a column the query produces are
    SEMANTIC questions, and they belong to the validator, which can say them
    all at once with locations rather than aborting on the first.
    """
    item = _require_mapping(item, where)
    kind = item.get("kind")
    if kind not in _DERIVED_KEYS:
        raise ValueError(
            f"{where}: kind must be one of "
            f"{', '.join(sorted(_DERIVED_KEYS))}, got {kind!r}. `filter` is "
            f"deliberately absent: a reporting column may not drop rows, "
            f"because every audit and count beside it assumes the query "
            f"carries the list.",
        )
    _reject_unknown_keys(item, _DERIVED_KEYS[kind], where)
    hidden = bool(item.get("hidden", False))
    description = str(item.get("description", ""))
    if kind == "expr":
        declared_type = _derived_text(item, "type", where)
        if declared_type not in DERIVED_TYPES:
            raise ValueError(
                f"{where}: type must be one of "
                f"{', '.join(sorted(DERIVED_TYPES))}, got {declared_type!r}",
            )
        return DerivedColumn(
            kind="expr",
            name=_derived_text(item, "name", where),
            type=declared_type,
            m=_derived_text(item, "m", where),
            hidden=hidden,
            description=description,
            replace=bool(item.get("replace", False)),
        )
    if kind == "lookup":
        via = str(item.get("via", ""))
        join_key = str(item.get("key", ""))
        if bool(via) == bool(join_key):
            raise ValueError(
                f"{where}: a lookup joins EITHER on `via`, a lookup column "
                f"whose key the generator derives, OR on `key`, a key "
                f"column this query already carries. Exactly one, and "
                f"{'both were given' if via else 'neither was'}.",
            )
        pick = _require_mapping(item.get("pick"), f"{where}.pick")
        types = _require_mapping(item.get("types"), f"{where}.types")
        if not pick:
            raise ValueError(f"{where}: pick must name at least one column")
        for new_name, source in pick.items():
            if not isinstance(source, str) or not source.strip():
                raise ValueError(
                    f"{where}.pick.{new_name} must be a non-empty string, "
                    f"got {source!r}",
                )
            declared = types.get(new_name)
            if declared not in DERIVED_TYPES:
                # Every picked column is typed, so none can reach the query
                # as `type any` and load as an Error in every populated cell.
                raise ValueError(
                    f"{where}.types.{new_name} must be one of "
                    f"{', '.join(sorted(DERIVED_TYPES))}, got {declared!r}",
                )
        unknown = set(types) - set(pick)
        if unknown:
            raise ValueError(
                f"{where}.types names {', '.join(sorted(unknown))}, which "
                f"pick does not produce",
            )
        return DerivedColumn(
            kind="lookup",
            from_entity=_derived_text(item, "from", where),
            via=via,
            key=join_key,
            pick={str(k): str(v) for k, v in pick.items()},
            types={str(k): str(v) for k, v in types.items()},
            hidden=hidden,
            description=description,
        )
    aggregate = _derived_text(item, "aggregate", where)
    if aggregate not in DERIVED_AGGREGATES:
        raise ValueError(
            f"{where}: aggregate must be one of "
            f"{', '.join(sorted(DERIVED_AGGREGATES))}, got {aggregate!r}",
        )
    declared_type = _derived_text(item, "type", where)
    if declared_type not in DERIVED_TYPES:
        raise ValueError(
            f"{where}: type must be one of "
            f"{', '.join(sorted(DERIVED_TYPES))}, got {declared_type!r}",
        )
    column = str(item.get("column", ""))
    if aggregate != "count" and not column:
        raise ValueError(
            f"{where}: aggregate {aggregate!r} reads a column of the child "
            f"rows, so `column` is required. Only `count` needs none.",
        )
    if aggregate == "count" and column:
        raise ValueError(
            f"{where}: aggregate `count` counts rows and reads no column, "
            f"so `column` must be absent, got {column!r}",
        )
    return DerivedColumn(
        kind="count",
        from_entity=_derived_text(item, "from", where),
        via=_derived_text(item, "via", where),
        name=_derived_text(item, "name", where),
        aggregate=aggregate,
        column=column,
        where=str(item.get("where", "")),
        type=declared_type,
        hidden=hidden,
        description=description,
    )


def _parse_derived_columns(raw: Any) -> dict[str, list[DerivedColumn]]:
    """The `derived_columns` section: {entity: [column, ...]}."""
    out: dict[str, list[DerivedColumn]] = {}
    for entity, items in _require_mapping(raw, "derived_columns").items():
        if not isinstance(items, list):
            raise ValueError(
                f"derived_columns.{entity} must be a list of columns, "
                f"got {items!r}",
            )
        out[entity] = [
            _parse_derived_column(item, f"derived_columns.{entity}[{i}]")
            for i, item in enumerate(items)
        ]
    return out
